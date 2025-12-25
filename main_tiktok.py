import time
import random
import re
import requests
import pandas as pd
import os
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from webdriver_manager.firefox import GeckoDriverManager 
from selenium.webdriver.common.action_chains import ActionChains
from pymongo import MongoClient

# =============================================================================
# 1. CẤU HÌNH
# =============================================================================
# --- Cấu hình Selenium ---
MY_PROFILE_PATH = r"C:\Users\lihoang14\AppData\Roaming\Mozilla\Firefox\Profiles\nsrlolhq.default-release"
FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"
GECKO_PATH = r"D:\Khanh\hoc\ma nguon mo\New folder\PPK_OSDS_Khanh\geckodriver.exe"

IMAGE_FOLDER = r"D:\Khanh\hoc\ma nguon mo\New folder\IMAGE_FOLDER"
if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)
# MY_PROFILE_PATH = r"c:\Users\Admin\AppData\Roaming\Mozilla\Firefox\Profiles\3k9cekk1.default-release"
# GECKO_PATH = r"C:\Users\Admin\Desktop\TANPHAT\Manguonmotrongkhoahocjdulieu\DOAN_MNM\tiktok\geckodriver.exe"
# FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"


# --- Cấu hình MongoDB [NEW] ---
MONGO_URI = "mongodb://localhost:27017/"  
DB_NAME = "tiktok_ads_db"                
COLLECTION_NAME = "creators_vn1"           

TARGET_NEW_ITEMS = 10000 # Số lượng muốn lấy

# =============================================================================
# 2. KẾT NỐI MONGODB
# =============================================================================
try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    print(f"--- Đã kết nối MongoDB: {DB_NAME}.{COLLECTION_NAME} ---")
    
    # [UPGRADE] Load toàn bộ ID đã có vào bộ nhớ để check nhanh
    existing_ids = set(doc["_id"] for doc in collection.find({}, {"_id": 1}))
    print(f"--- Đã load {len(existing_ids)} creators có sẵn trong DB để tránh trùng ---")
    
except Exception as e:
    print(f"Lỗi kết nối MongoDB: {e}")
    exit()

# =============================================================================
# 3. CÁC HÀM HỖ TRỢ
# =============================================================================

def random_sleep(min_s=2, max_s=4):
    time.sleep(random.uniform(min_s, max_s))

def safe_click(driver, xpath, retries=3):
    """Hàm click an toàn, tự scroll tới phần tử"""
    for i in range(retries):
        try:
            element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", element)
            return True
        except:
            time.sleep(1)
    return False

def human_scroll(driver):
    """
    [UPGRADE] Scroll kiểu người dùng: Xuống một đoạn, thỉnh thoảng nhích lên tí
    """
    scroll_amount = random.randint(400, 800)
    driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
    
    # 20% cơ hội scroll ngược lên một chút để đánh lừa bot detection
    if random.random() < 0.2:
        time.sleep(1)
        driver.execute_script("window.scrollBy(0, -100);")

def get_creator_id_only(card_section):
    """
    Hàm nhỏ chỉ lấy ID để check trùng trước khi cào chi tiết
    """
    try:
        id_elm = card_section.find_element(By.XPATH, ".//div[contains(@class, 'text-black') and contains(@class, 'font-semibold')]//div[contains(@class, 'truncated__text-single')]")
        return id_elm.text.strip()
    except:
        return "N/A"

def download_avatar(url, creator_id):
    """
    Tải ảnh từ URL -> Lưu vào folder 'downloaded_avatars' -> Trả về đường dẫn file
    """
    if not url or url == "":
        return ""
    
    try:
        # 1. Tạo đường dẫn file
        safe_id = "".join([c for c in creator_id if c.isalnum() or c in ('-','_','.')])
        filename = f"{safe_id}.jpg"
        file_path = os.path.join(IMAGE_FOLDER, filename)
        
        # Nếu file đã có và > 0KB thì không tải lại
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            # print(f" [Skip] Ảnh đã tồn tại: {filename}")
            return file_path

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.tiktok.com/",
            "Origin": "https://www.tiktok.com",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
        }

        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(response.content)
            return file_path
        else:
            return "" # Lỗi tải
    except Exception as e:
        # print(f"Lỗi tải ảnh {creator_id}: {e}")
        return ""


def extract_full_details(card_section, creator_id):
    """Logic trích xuất thông tin """
    data = {
        "_id": creator_id,
         "ID": creator_id,
        "Name": "N/A",
        "Country": "N/A",
        "Collab Score": "N/A",
        "Broadcast Score": "N/A",
        "Followers": "N/A",
        "Median Views": "N/A",
        "Engagement": "N/A",
        "Start Price": "N/A",
        "Tags": "",
        "avatar_url": "",      # Link gốc 
        "avatar_local_path": "", #  Đường dẫn file trên máy 
    }
    
    try:
        # 1. ID 
        # Tìm div chứa class text-black và font-semibold
        # try:
        #     id_elm = card_section.find_element(By.XPATH, ".//div[contains(@class, 'text-black') and contains(@class, 'font-semibold')]//div[contains(@class, 'truncated__text-single')]")
        #     data["ID"] = id_elm.text.strip()
        # except: pass

        # 1. Tên 
        try:
            name_elm = card_section.find_element(By.XPATH, ".//div[contains(@class, 'text-neutral-onFillLow')]//div[contains(@class, 'truncated__text-single')]")
            data["Name"] = name_elm.text.strip()
        except: pass

        # 2. Quốc gia
        try:
            country_elm = card_section.find_element(By.XPATH, ".//div[contains(@class, 'truncated__text-single') and text()='Việt Nam']")
            data["Country"] = country_elm.text.strip()
        except: data["Country"] = "Unknown"

        # 3. Điểm số (Collab Score)
        try:
            # Tìm thẻ chứa text "Điểm cộng tác" và lấy nội dung ẩn
            collab_elm = card_section.find_element(By.XPATH, ".//*[contains(text(), 'Điểm cộng tác')]")
            data["Collab Score"] = collab_elm.get_attribute("innerText").replace("Điểm cộng tác tổng thể:", "").strip()
        except: pass

        try:
            broad_elm = card_section.find_element(By.XPATH, ".//*[contains(text(), 'Điểm phát sóng')]")
            data["Broadcast Score"] = broad_elm.get_attribute("innerText").replace("Điểm phát sóng cao:", "").strip()
        except: pass

        # 4. SỐ LIỆU (Followers, Views, Engagement)
        try:
            # Tìm TẤT CẢ các thẻ có class "text-base font-semibold" trong Card này.
            # Đây là class đặc trưng của số liệu, khác với class của ID (text-sm).
            metrics = card_section.find_elements(By.CSS_SELECTOR, ".text-base.font-semibold")
            
            # Kiểm tra xem tìm được bao nhiêu số
            if len(metrics) >= 3:
                # Theo thứ tự giao diện TikTok: [0]=Followers, [1]=Views, [2]=Engagement
                data["Followers"] = metrics[0].text.strip()
                data["Median Views"] = metrics[1].text.strip()
                data["Engagement"] = metrics[2].text.strip()
            elif len(metrics) > 0:
                # Trường hợp hiếm: Thiếu dữ liệu, lấy tạm cái đầu tiên
                data["Followers"] = metrics[0].text.strip()
        except Exception as e:
            # print(f"Lỗi metrics: {e}")
            pass

        # 5. GIÁ TIỀN (Start Price)
        try:
            # Logic: Tìm chữ "Khởi điểm từ", nhảy lên div cha, tìm div chứa số (text-base)
            price_xpath = ".//span[contains(text(), 'Khởi điểm từ')]/ancestor::div[contains(@class, 'flex-col')]//div[contains(@class, 'text-base')]"
            price_elm = card_section.find_element(By.XPATH, price_xpath)
            # Lấy thêm đơn vị tiền tệ (VND)
            currency = "VND" if "VND" in card_section.get_attribute("innerText") else ""
            data["Start Price"] = f"{price_elm.text.strip()} {currency}"
        except:
            data["Start Price"] = "Thỏa thuận/Chưa đặt"

        # 6. TAGS
        tags = []
        try:
            # Tìm tất cả các phần tử tag text nằm trong rc-overflow
            # Lưu ý: Tìm thẻ div có class 'truncated__text-single' nằm trong 'rc-overflow-item'
            tag_elms = card_section.find_elements(By.XPATH, ".//div[contains(@class, 'rc-overflow')]//div[contains(@class, 'rc-overflow-item')]//div[contains(@class, 'truncated__text-single')]")
            
            for t in tag_elms:
                txt = t.get_attribute("textContent").strip()
                
                if txt and len(txt) > 1 and txt != data["ID"] and txt != data["Name"] and "+" not in txt:
                    tags.append(txt)
                    
        except Exception as e:
            pass
        
        # Loại bỏ trùng lặp và nối chuỗi
        data["Tags"] = ", ".join(list(set(tags)))
        
        # 7. Avatar
        try:
            avatar_img = card_section.find_element(By.XPATH, ".//div[contains(@class,'creator-avatar__wrapper')]//img")
            
            # Ưu tiên lấy data-src (ảnh gốc)
            raw_url = avatar_img.get_attribute("data-src")
            if not raw_url:
                raw_url = avatar_img.get_attribute("src")

            # Gọi hàm tải ảnh
            if raw_url:
                raw_url = raw_url.strip()
            
            data["avatar_url"] = raw_url or ""

            # Gọi hàm tải ảnh MỚI
            if raw_url:
                # Thêm log để biết nó có chui vào đây không
                # print(f" -> Đang thử tải ảnh cho: {creator_id}...") 
                local_path = download_avatar(raw_url, creator_id)
                data["avatar_local_path"] = local_path
            else:
                print(f" [!] Không tìm thấy URL ảnh cho {creator_id}")
                
        except Exception as e:
            print(f"Lỗi phần avatar: {e}")
            pass

    except Exception: pass
    return data

# =============================================================================
# 4. CHƯƠNG TRÌNH CHÍNH
# =============================================================================

# Kill Firefox cũ
try:
    os.system("taskkill /f /im firefox.exe")
    time.sleep(2)
except: pass

print("--- KHỞI ĐỘNG FIREFOX ---")
ser = Service(GECKO_PATH)
options = webdriver.firefox.options.Options()
options.binary_location = FIREFOX_BINARY_PATH
options.add_argument("-profile")
options.add_argument(MY_PROFILE_PATH)
# options.add_argument("--headless") # Nếu muốn chạy ngầm sau này thì mở dòng này
options.set_preference("dom.webdriver.enabled", False)
options.set_preference("useAutomationExtension", False)

driver = webdriver.Firefox(options=options, service=ser)
wait = WebDriverWait(driver, 20)
action = ActionChains(driver)

try:
    driver.get("https://ads.tiktok.com/creative/creator/explore?region=row")
    driver.maximize_window()
    time.sleep(5)

    # --- AUTO BỘ LỌC (GIỮ NGUYÊN) ---
    print("\n--- [AUTO] CẤU HÌNH BỘ LỌC ---")
    if safe_click(driver, "//div[contains(@class,'filter-trigger')][1]"):
        time.sleep(1)
        safe_click(driver, "//div[contains(@class, 'truncated__text') and text()='Việt Nam']")
        safe_click(driver, "//button[contains(text(), 'Áp dụng')]")

    time.sleep(3)

    # price_trigger = "//div[contains(@class, 'filter-item-menu-label') and .//p[contains(text(), 'Giá')]]"
    # fallback_trigger = "//p[text()='Giá']/ancestor::div[contains(@class, 'filter-item-menu-label')]"
    # if safe_click(driver, price_trigger) or safe_click(driver, fallback_trigger):
    #     time.sleep(1)
    #     if safe_click(driver, "//ul[contains(@class, 'filter-form-select')]/li[last()]"):
    #          safe_click(driver, "//button[contains(text(), 'Áp dụng')]")
    #     action.move_by_offset(200, 0).click().perform()
    
    time.sleep(5)

    # --- VÒNG LẶP CHÍNH ---
    print("\n--- BẮT ĐẦU CÀO DỮ LIỆU ---")
    
    new_items_count = 0
    consecutive_duplicates = 0 
    last_highest_index = -1
    retry_scroll = 0
    
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-index='0']")))
    except: pass

    while new_items_count < TARGET_NEW_ITEMS:
        #  nghỉ 2 phút giải lao
        if new_items_count > 0 and new_items_count % 100 == 0:
            print(f"\n>>> [ANTI-BAN] Đã lấy {new_items_count} người. Nghỉ giải lao 60 giây...")
            time.sleep(60)
            # fake human
            driver.execute_script("window.scrollBy(0, -200);")
            time.sleep(2)

        visible_rows = driver.find_elements(By.CSS_SELECTOR, "div[data-index]")
        if not visible_rows:
            time.sleep(1)
            continue
            
        current_row_indices = []
        rows_processed_in_view = 0

        for row in visible_rows:
            try:
                row_idx = int(row.get_attribute("data-index"))
                current_row_indices.append(row_idx)
                
                # Tìm các thẻ creator
                creator_cards = row.find_elements(By.TAG_NAME, "section")
                
                for card in creator_cards:
                    # 1. Chỉ lấy ID trước để check
                    c_id = get_creator_id_only(card)
                    
                    if c_id == "N/A": continue
                    
                    # 2. Check xem đã có trong DB chưa
                    if c_id in existing_ids:
                        consecutive_duplicates += 1
                        # Nếu gặp trùng quá nhiều, in dấu chấm để biết đang skip
                        if consecutive_duplicates % 10 == 0:
                            print(".", end="", flush=True) 
                        continue
                    
                    # 3. NẾU LÀ NGƯỜI MỚI -> Cào full và lưu
                    consecutive_duplicates = 0 # Reset biến đếm trùng
                    info = extract_full_details(card, c_id)
                    
                    # Lưu Mongo
                    collection.update_one({"_id": c_id}, {"$set": info}, upsert=True)
                    existing_ids.add(c_id) # Thêm vào cache để lát không check lại
                    new_items_count += 1
                    
                    print(f"\n [NEW #{new_items_count}] {info['ID']} | FL: {info['Followers']} | Price: {info['Start Price']}")

            except StaleElementReferenceException:
                continue

        # --- LOGIC CUỘN TRANG THÔNG MINH ---
        if not current_row_indices: 
            break
        max_row_idx = max(current_row_indices)
        
        if max_row_idx == last_highest_index:
            retry_scroll += 1
            print(f" [Wait load {retry_scroll}]", end="\r")
            if retry_scroll >= 3:
                # Cách 1: Cuộn xuống đáy trang
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            elif retry_scroll >= 5:
                # Cách 2: Cuộn ngược lên một chút rồi cuộn mạnh xuống
                driver.execute_script("window.scrollBy(0, -300);")
                time.sleep(1)
                driver.execute_script("window.scrollBy(0, 1000);")
                
            if retry_scroll > 15:
                break
        else:
            retry_scroll = 0
            last_highest_index = max_row_idx
            
            # Kỹ thuật cuộn: Lấy hàng cuối cùng trong danh sách đã tìm thấy
            try:
                # [FIX]: Dùng ngay visible_rows[-1] thay vì find_element lại
                if visible_rows:
                    last_row = visible_rows[-1]
                    # [FIX]: Dùng 'center' thay vì 'start' để tránh bị che khuất
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", last_row)
                else:
                    # Dự phòng nếu danh sách rỗng
                    driver.execute_script("window.scrollBy(0, 800);")
            except Exception:
                # Nếu lỗi (do phần tử cũ quá), dùng scroll thuần túy
                driver.execute_script("window.scrollBy(0, 800);")
        
        random_sleep(2, 3)

    print(f"\nHoàn tất! Đã thu thập thêm {new_items_count} người mới.")

except Exception as e:
    print(f"Lỗi: {e}")
finally:
    print("Kết thúc.")