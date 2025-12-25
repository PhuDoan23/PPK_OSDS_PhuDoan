import base64
import requests
import time
import os
from datetime import datetime
from pymongo import MongoClient

# ===============================
# CONFIG
# ===============================
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "tiktok_ads_db"

SOURCE_COLLECTION = "creators_vn1"
TARGET_COLLECTION = "creator_avatar"
IMAGE_FOLDER = r"D:\Khanh\hoc\ma nguon mo\New folder\IMAGE_FOLDER"
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
def local_file_to_base64(file_path: str) -> str | None:
    """Đọc file local và chuyển thành Base64"""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception:
        return None

# ===============================
# MAIN WORKER
# ===============================
def run_worker_combine(limit: int | None = None):
    # Lấy danh sách creator từ nguồn để có được URL gốc
    query = {"avatar_url": {"$ne": ""}}
    cursor = src_col.find(query)

    processed = 0
    skipped = 0
    missing_file = 0

    print("--- BẮT ĐẦU XỬ LÝ ---")

    for doc in cursor:
        creator_id = doc.get("_id")
        original_url = doc.get("avatar_url") # <--- 1. LẤY URL TỪ DB

        if not creator_id:
            continue

        # Kiểm tra xem record này đã xử lý chưa (để resume nếu chạy lại)
        # Nếu muốn cập nhật đè lên thì bỏ đoạn check này đi
        if avatar_col.find_one({"_id": creator_id}):
            skipped += 1
            continue

        # 2. XÁC ĐỊNH FILE TƯƠNG ỨNG TRONG Ổ CỨNG
        # Lưu ý: Bạn cần chắc chắn đuôi file mình đã lưu là .jpg, .png hay gì đó.
        # Ở đây tôi ví dụ là .jpg, và tên file chính là _id
        filename = f"{creator_id}.jpg" 
        file_path = os.path.join(IMAGE_FOLDER, filename)

        # 3. ĐỌC FILE VÀ MÃ HÓA
        b64 = local_file_to_base64(file_path)

        if not b64:
            # Có thông tin trong DB nhưng không thấy file trong ổ cứng
            # print(f"⚠️ Missing file for ID: {creator_id}")
            missing_file += 1
            continue

        # 4. LƯU CẢ HAI VÀO TARGET COLLECTION
        avatar_col.update_one(
            {"_id": creator_id},
            {
                "$set": {
                    "avatar_base64": b64,        # Dữ liệu ảnh từ ổ cứng
                    "avatar_url": original_url,  # Dữ liệu link từ DB nguồn
                    "updated_at": time.time()
                }
            },
            upsert=True
        )

        print(f"✅ Saved: {creator_id} | URL: {original_url[:30]}...")
        processed += 1

        if limit and processed >= limit:
            break

    print("\n=== KẾT THÚC ===")
    print(f"Đã xử lý: {processed}")
    print(f"Đã có sẵn (bỏ qua): {skipped}")
    print(f"Không tìm thấy file ảnh: {missing_file}")

if __name__ == "__main__":
    run_worker_combine()