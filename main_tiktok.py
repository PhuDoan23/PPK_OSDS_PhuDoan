from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
import time
import pandas as pd
import random
import re
import os

# --- 1. CẤU HÌNH --- ( Tinh chỉnh theo cá nhân)
# MY_PROFILE_PATH = "" #cấu hình cookie của máy 
# GECKO_PATH = r"C:\Users\Admin\Desktop\TANPHAT\Manguonmotrongkhoahocjdulieu\DOAN_MNM\tiktok\geckodriver.exe"
# FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"

#cua TanPhat
MY_PROFILE_PATH = r"c:\Users\Admin\AppData\Roaming\Mozilla\Firefox\Profiles\3k9cekk1.default-release"    #Không nên public dòng này 
GECKO_PATH = r"C:\Users\Admin\Desktop\TANPHAT\Manguonmotrongkhoahocjdulieu\DOAN_MNM\tiktok\geckodriver.exe"
FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"

TARGET_CREATOR_COUNT = 3 # Số Creator muốn lấy
OUTPUT_FILE = "tiktok_creators_final.xlsx"   #Phú lưu database đi 
TARGET_URL = "https://ads.tiktok.com/creative/forpartners/creator/explore?region=row"
# MY_PROFILE_PATH = r"C:\Users\lihoang14\AppData\Roaming\Mozilla\Firefox\Profiles\nsrlolhq.default-release"
# FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"
# GECKO_PATH = r"D:\Khanh\hoc\ma nguon mo\New folder\PPK_OSDS_Khanh\geckodriver.exe"
# TARGET_CREATOR_COUNT = 1  # Số lượng muốn lấy
#---------------------------



#Hàm hỗ trợ 
def random_sleep(min_s = 2, max_s = 4):
    time.sleep(random.uniform(min_s, max_s))

def safe_click(driver, xpath, retries=3):
    for i in range(retries):
        try:
            element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, xpath)))
            driver.excute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(1)
            driver.execute_script("argument[0].click();", element)
            return True
        except:
            time.sleep(1)
    return False

def extract_creator_data(card):
    data = {
        "Index": "N/A",
        "ID": "N/A",
        "Name": "N/A",
        "Country": "N/A",
        "Collab Score": "N/A",
        "Broadcast Score": "N/A",
        "Followers": "N/A",
        "Median Views": "N/A",
        "Engagement": "N/A",
        "Start Price": "N/A",
        "Tags": ""
    }

    try:
        try:
        #Lấy index
            data["Index"] = card.get_attribute("data-index")
        except:
            pass


        #ID
        try:
            id_elm = card.find_element(By.XPATH, ".//div[contains(@class, 'text-black') and contains(@class, 'font-semibold')]//div[contains(@class, 'truncated_text-single')]")
            data["ID"] = id_elm.text.strip()
        except:
            pass

        #Tên
        try:
            name_elm = card.find_element(By.XPATH, ".//div[cotains(@class, 'text-neutral-onFillow')]//div[contains(@class, 'truncated_text-single')]")
            data["Name"] = name_elm.text.strip()
        except: 
            pass


        # Quốc gia
        try:
            country_elm = card.find_element(By.XPATH, ".//div[contains(@class, 'truncated_text-single') and text()= 'Việt Nam']")
            data["Country"] = country_elm.text.strip()
        except:
            data["Country"] = "Unknown"
        
        
        
        ## 4. Điểm số
        try:
            collab_elm = card.find_element(By.XPATH, ".//*[contains(text(), 'Điểm cộng tác')]")
            data["Collab Score"] = collab_elm.get_attribute("innerText").replace("Điểm cộng tác tổng thể:", "").strip()
        except: pass


        try:
            broad_elm = card.find_element(By.XPATH, ".//*[contains(text(), 'Điểm phát sóng')]")
            data["Broadcast Score"] = broad_elm.get_attribute("innerText").replace("Điểm phát sóng cao:", "").strip()
        except: pass

        # 5. SỐ LIỆU (Followers, Views, Engagement)
        try:
            metrics = card.find_elements(By.CSS_SELECTOR, ".text-base.font-semibold")
            
            # Kiểm tra xem tìm được bao nhiêu số
            if len(metrics) >= 3:
                # Theo thứ tự giao diện TikTok: [0]=Followers, [1]=Views, [2]=Engagement
                data["Followers"] = metrics[1].text.strip()
                data["Median Views"] = metrics[2].text.strip()
                data["Engagement"] = metrics[3].text.strip()
            elif len(metrics) > 0:
                # Trường hợp hiếm: Thiếu dữ liệu, lấy tạm cái đầu tiên
                data["Followers"] = metrics[0].text.strip()
        except Exception as e:
            # print(f"Lỗi metrics: {e}")
            pass


        # 6. GIÁ TIỀN (Start Price)
        try:
            price_xpath = ".//span[contains(text(), 'Khởi điểm từ')]/ancestor::div[contains(@class, 'flex-col')]//div[contains(@class, 'text-base')]"
            price_elm = card.find_element(By.XPATH, price_xpath)
            # Lấy thêm đơn vị tiền tệ (VND)
            currency = "VND" if "VND" in card.get_attribute("innerText") else ""
            data["Start Price"] = f"{price_elm.text.strip()} {currency}"
        except:
            data["Start Price"] = "Thỏa thuận/Chưa đặt"

        # 7. TAGS
        tags = []
        try:
            # Tìm tất cả các phần tử tag text nằm trong rc-overflow
            # Lưu ý: Tìm thẻ div có class 'truncated__text-single' nằm trong 'rc-overflow-item'
            tag_elms = card.find_elements(By.XPATH, ".//div[contains(@class, 'rc-overflow')]//div[contains(@class, 'rc-overflow-item')]//div[contains(@class, 'truncated__text-single')]")
            
            for t in tag_elms:
                # Dùng 'textContent' thay vì 'text' để lấy được nội dung dù nó bị ẩn (opacity: 0)
                txt = t.get_attribute("textContent").strip()
                
                if txt and len(txt) > 1 and txt != data["ID"] and txt != data["Name"] and "+" not in txt:
                    tags.append(txt)
        except:
            pass

        # Loại bỏ trùng lặp và nối chuỗi
        data["Tags"] = ", ".join(list(set(tags)))


    except:
        pass

    return data






# --- 3. KHỞI TẠO DRIVER ---
ser = Service(GECKO_PATH)
options = webdriver.firefox.options.Options()
options.binary_location = FIREFOX_BINARY_PATH
options.add_argument("-profile")
options.add_argument(MY_PROFILE_PATH)
options.set_preference("dom.webdriver.enabled", False)
options.set_preference("useAutomationExtension", False)

driver = None 

print("WARNING: Hãy TẮT HOÀN TOÀN Firefox thật trước khi chạy!")
print("Đang khởi động Firefox với Profile cá nhân...")

driver = webdriver.Firefox(options=options, service=ser)
wait = WebDriverWait(driver, 20)
action = ActionChains(driver)

# Vào trang Ads
print(f"Truy cập: {TARGET_URL}")
driver.get(TARGET_URL)
driver.maximize_window()
time.sleep(5) 
    # A. Chọn Quốc Gia: Việt Nam
    # Tìm nút mở menu Quốc gia (thường là nút filter đầu tiên)
# 1. Mở menu Quốc gia
# Tìm nút có class filter-trigger đầu tiên hoặc chứa text 'Quốc gia'
trigger_xpath = "//div[contains(@class,'filter-trigger')][1]" 
if safe_click(driver, trigger_xpath):
    print("Đã mở menu Quốc gia.")
    time.sleep(2) # Chờ menu bung ra hoàn toàn
    # 2. Chọn Việt Nam (
    # XPath tìm thẻ div chứa text "Việt Nam"
    vn_xpath = "//div[contains(@class, 'truncated__text') and text()='Việt Nam']"
    is_clicked = safe_click(driver, vn_xpath)
    if is_clicked:
        print("Đã chọn 'Việt Nam'.")
        time.sleep(1)
    else:
        print("[!] Không thấy tùy chọn Việt Nam")
else:
    print("Không mở được menu Quốc gia.")
time.sleep(3) # Đợi reload

# B. Chọn Giá: > 300 USD ổn
# Tìm nút Giá (dựa trên class mới bạn cung cấp)
price_trigger_xpath = "//div[contains(@class, 'filter-item-menu-label') and .//p[contains(text(), 'Giá')]]"
# Nếu không tìm thấy bằng class, dùng XPath dự phòng tìm theo text đơn giản
backup_trigger_xpath = "//p[text()='Giá']/ancestor::div[contains(@class, 'filter-item-menu-label')]"
if safe_click(driver, price_trigger_xpath) or safe_click(driver, backup_trigger_xpath):
    print("Đã mở menu Giá.")
    time.sleep(2) # Chờ menu bung ra

    # 2. Chọn "> 300 USD"
    price_option_xpath = "//li[contains(@class, 'filter-form-select__item') and contains(text(), '> 300 USD')]"
    is_price_clicked = safe_click(driver, price_option_xpath)
    
    if is_price_clicked:
        apply_xpath = "//button[contains(text(), 'Áp dụng')]"
        safe_click(driver, apply_xpath)
        print("Đã bấm Áp dụng.")
    else:
        print("Không tìm thấy text '> 300 USD', thử chọn mục cuối cùng...")

    # 3. Đóng menu
    time.sleep(1)
    try:
        # Click vào khoảng trống bên phải nút Giá (move offset) hoặc click body
        action.move_by_offset(200, 0).click().perform()
    except:
        pass

else:
    print("LỖI: Không tìm thấy nút bấm 'Giá' (Class: filter-item-menu-label).")

time.sleep(3)
container = wait.until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "div.virtualCardResults"))
)

collected = {}
last_max_idx = -1
retry = 0

while len(collected) < TARGET_CREATOR_COUNT:
    cards = container.find_elements(By.CSS_SELECTOR, "div[data-index]")
    current_idxs = [] 

    for row in cards:
        sections = row.find_elements(
            By.CSS_SELECTOR,
            "section[data-testid^='ExploreCreatorCard-index']"
        )

        for section in sections:
            info = extract_creator_data(section)
            key = info["ID"] or f"{info['Index']}_{info['Name']}"

            if key not in collected:
                collected[key] = info
                print(f"[OK] #{info['Index']} {info['Name']} | {info['Followers']}")

    if not current_idxs:
        break

    max_idx = max(current_idxs)
    if max_idx == last_max_idx:
        retry += 1
        if retry > 6:
            break
        driver.execute_script("arguments[0].scrollTop += 900;", container)
    else:
        retry = 0
        last_max_idx = max_idx
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'start'});",
                container.find_element(By.CSS_SELECTOR, f"div[data-index='{max_idx}']")
            )
        except:
            pass
    random_sleep(2, 4)

# ===============================
# EXPORT
# ===============================
df = pd.DataFrame(collected.values())
cols = [
    "Index", "ID", "Name", "Country",
    "Collab Score", "Broadcast Score",
    "Followers", "Median Views", "Engagement",
    "Start Price", "Tags"
]
df = df[cols]
df.to_excel(OUTPUT_FILE, index=False)
print(f"Saved {len(df)} creators")
print("=== DONE ===")