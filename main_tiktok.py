from src.db_connector import MongoDBConnector
from src.bot_engine import TikTokBot

def main():
    print("   TIKTOK CREATOR MARKETPLACE CRAWLER    ")
   
    # 1. Kết nối Database
    try:
        db = MongoDBConnector()
    except Exception:
        print("Không thể kết nối CSDL. Dừng chương trình.")
        return

    # 2. Khởi tạo và chạy Bot
    bot = TikTokBot(db_connector=db)
    bot.run()

if __name__ == "__main__":
    main()