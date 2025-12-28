from pymongo import MongoClient
from config.settings import MONGO_URI, DB_NAME, COLLECTION_NAME

class MongoDBConnector:
    def __init__(self):
        try:
            self.client = MongoClient(MONGO_URI)
            self.db = self.client[DB_NAME]
            self.collection = self.db[COLLECTION_NAME]
            print(f"--- [DB] Đã kết nối MongoDB: {DB_NAME}.{COLLECTION_NAME} ---")
        except Exception as e:
            print(f"[DB] Lỗi kết nối: {e}")
            raise e

    def get_existing_ids(self):
        """Load toàn bộ ID đã có vào bộ nhớ (Set) để check nhanh"""
        cursor = self.collection.find({}, {"_id": 1})
        existing_ids = set(doc["_id"] for doc in cursor)
        print(f"--- [DB] Đã load {len(existing_ids)} creators có sẵn ---")
        return existing_ids

    def upsert_creator(self, creator_data):
        """Thêm mới hoặc cập nhật creator"""
        try:
            self.collection.update_one(
                {"_id": creator_data["_id"]}, 
                {"$set": creator_data}, 
                upsert=True
            )
            return True
        except Exception as e:
            print(f"[DB] Lỗi lưu dữ liệu: {e}")
            return False