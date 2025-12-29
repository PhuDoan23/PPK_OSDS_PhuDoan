import os

# --- PATHS ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_FOLDER = os.path.join(BASE_DIR, "assets", "avatars")

# Tạo folder ảnh nếu chưa có
if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)

# --- SELENIUM CONFIG ---
# Hãy thay đổi đường dẫn phù hợp với máy của bạn
MY_PROFILE_PATH = r"C:\Users\lihoang14\AppData\Roaming\Mozilla\Firefox\Profiles\nsrlolhq.default-release"
FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"
GECKO_PATH = r"D:\Khanh\hoc\ma nguon mo\New folder\PPK_OSDS_Khanh\geckodriver.exe"

# --- MONGODB CONFIG ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "tiktok_ads_db"
COLLECTION_NAME = "creators_vn1"

# --- CRAWLER CONFIG ---
TARGET_NEW_ITEMS = 10000