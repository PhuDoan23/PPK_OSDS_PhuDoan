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
# ENTRY POINT
# ===============================
if __name__ == "__main__":
    run_worker(limit=None)   # đổi thành số nếu muốn test
