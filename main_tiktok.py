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
MY_PROFILE_PATH = "" #cấu hình cookie của máy 
GECKO_PATH = r"C:\Users\Admin\Desktop\TANPHAT\Manguonmotrongkhoahocjdulieu\DOAN_MNM\tiktok\geckodriver.exe"
FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"
TARGET_CREATOR_COUNT = 3 # Số Creator muốn lấy
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

    }

    try:
        #Lấy index
        data["Index"] = card.get_attribute("data-index")

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


        # 5. SỐ LIỆU (Followers, Views, Engagement)
        try:
            # Tìm TẤT CẢ các thẻ có class "text-base font-semibold" trong Card này.
            # Đây là class đặc trưng của số liệu, khác với class của ID (text-sm).
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
            # Logic: Tìm chữ "Khởi điểm từ", nhảy lên div cha, tìm div chứa số (text-base)
            price_xpath = ".//span[contains(text(), 'Khởi điểm từ')]/ancestor::div[contains(@class, 'flex-col')]"
            price_elm = card.find_element(By.XPATH, price_xpath)
            # Lấy thêm đơn vị tiền tệ (VND)
            currency = "VND" if "VND" in card.get_attribute("innerText") else ""
            data["Start Price"] = f"{price_elm.text.strip()} {currency}"
        except:
            data["Start Price"] = "Thỏa thuận/Chưa đặt"


    except:
        pass


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
target_url = "https://ads.tiktok.com/creative/forpartners/creator/explore?region=row"
print(f"Truy cập: {target_url}")
driver.get(target_url)
driver.maximize_window()
time.sleep(5) 
print("Tiêu đề trang hiện tại:", driver.title)
