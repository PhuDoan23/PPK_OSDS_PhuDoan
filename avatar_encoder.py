import base64
import requests
import time
from datetime import datetime
from pymongo import MongoClient

# ===============================
# CONFIG
# ===============================
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "tiktok_ads_db"

SOURCE_COLLECTION = "creators_vn1"
TARGET_COLLECTION = "creator_avatar"

REQUEST_TIMEOUT = 10
SLEEP_BETWEEN_REQUESTS = 1.5  # anti-ban nhẹ

# ===============================
# MONGO CONNECT
# ===============================
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

src_col = db[SOURCE_COLLECTION]
avatar_col = db[TARGET_COLLECTION]

print(f"Connected MongoDB: {DB_NAME}")
print(f"Source: {SOURCE_COLLECTION}")
print(f"Target: {TARGET_COLLECTION}")

# ===============================
# IMAGE UTILS
# ===============================
def download_image_base64(url: str) -> str | None:
    """
    Download image from URL and encode to base64 string
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "image/*"
        }
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return None

        return base64.b64encode(r.content).decode("utf-8")

    except Exception:
        return None


# ===============================
# MAIN WORKER
# ===============================
def run_worker(limit: int | None = None):
    """
    limit: số lượng avatar muốn xử lý (None = xử lý hết)
    """

    # Chỉ lấy creator:
    # - có avatar_url
    # - chưa có avatar trong collection creator_avatar
    query = {
        "avatar_url": {"$ne": ""}
    }

    cursor = src_col.find(query)

    processed = 0
    skipped = 0

    for doc in cursor:
        creator_id = doc.get("_id")
        avatar_url = doc.get("avatar_url", "")

        if not creator_id or not avatar_url:
            skipped += 1
            continue

        # Nếu avatar đã tồn tại → skip
        if avatar_col.find_one({"_id": creator_id}):
            skipped += 1
            continue

        print(f"[FETCH] {creator_id}")

        b64 = download_image_base64(avatar_url)
        if not b64:
            print(f" Failed image")
            skipped += 1
            continue

        avatar_col.update_one(
            {"_id": creator_id},
            {
                "$set": {
                    "avatar_base64": b64,
                    "avatar_url": avatar_url,
                }
            },
            upsert=True
        )

        print(f"  ✅ Saved avatar ({len(b64)} chars)")
        processed += 1

        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if limit and processed >= limit:
            break

    print("\n=== DONE ===")
    print(f"Processed: {processed}")
    print(f"Skipped:   {skipped}")


# ===============================
# ENTRY POINT
# ===============================
if __name__ == "__main__":
    run_worker(limit=None)   # đổi thành số nếu muốn test
