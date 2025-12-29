import time
import random
import os
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains

from config.setting import GECKO_PATH, FIREFOX_BINARY_PATH, MY_PROFILE_PATH, TARGET_NEW_ITEMS
from src.cleaner import DataCleaner

class TikTokBot:
    def __init__(self, db_connector):
        self.db = db_connector
        self.existing_ids = self.db.get_existing_ids()
        self.driver = self._init_driver()
        self.wait = WebDriverWait(self.driver, 20)
        self.action = ActionChains(self.driver)

    def _init_driver(self):
        """Khởi tạo Firefox Driver"""
        # Kill process cũ
        try:
            os.system("taskkill /f /im firefox.exe")
            time.sleep(2)
        except: pass

        print("--- [BOT] KHỞI ĐỘNG FIREFOX ---")
        ser = Service(GECKO_PATH)
        options = webdriver.firefox.options.Options()
        options.binary_location = FIREFOX_BINARY_PATH
        options.add_argument("-profile")
        options.add_argument(MY_PROFILE_PATH)
        options.set_preference("dom.webdriver.enabled", False)
        options.set_preference("useAutomationExtension", False)
        
        return webdriver.Firefox(options=options, service=ser)

    def random_sleep(self, min_s=2, max_s=4):
        time.sleep(random.uniform(min_s, max_s))

    def safe_click(self, xpath):
        """Click an toàn"""
        for i in range(3):
            try:
                element = WebDriverWait(self.driver, 3).until(EC.presence_of_element_located((By.XPATH, xpath)))
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except:
                time.sleep(1)
        return False

    def get_creator_id_only(self, card_section):
        try:
            id_elm = card_section.find_element(By.XPATH, ".//div[contains(@class, 'text-black') and contains(@class, 'font-semibold')]//div[contains(@class, 'truncated__text-single')]")
            return id_elm.text.strip()
        except:
            return "N/A"

    def extract_full_details(self, card_section, creator_id):
        """Logic bóc tách dữ liệu DOM"""
        data = {
            "_id": creator_id, "ID": creator_id,
            "Name": "N/A", "Country": "N/A", "Collab Score": "N/A",
            "Broadcast Score": "N/A", "Followers": "N/A", "Median Views": "N/A",
            "Engagement": "N/A", "Start Price": "N/A", "Tags": "",
            "avatar_url": "", "avatar_local_path": "",
        }
        
        try:
            # 1. Name & Country
            try:
                data["Name"] = card_section.find_element(By.XPATH, ".//div[contains(@class, 'text-neutral-onFillLow')]//div[contains(@class, 'truncated__text-single')]").text.strip()
            except: pass
            
            try:
                data["Country"] = card_section.find_element(By.XPATH, ".//div[contains(@class, 'truncated__text-single') and text()='Việt Nam']").text.strip()
            except: data["Country"] = "Unknown"

            # 2. Scores
            try:
                data["Collab Score"] = card_section.find_element(By.XPATH, ".//*[contains(text(), 'Điểm cộng tác')]").get_attribute("innerText").replace("Điểm cộng tác tổng thể:", "").strip()
            except: pass

            # 3. Metrics (Followers, Views, Engagement)
            try:
                metrics = card_section.find_elements(By.CSS_SELECTOR, ".text-base.font-semibold")
                if len(metrics) >= 3:
                    data["Followers"] = metrics[0].text.strip()
                    data["Median Views"] = metrics[1].text.strip()
                    data["Engagement"] = metrics[2].text.strip()
            except: pass

            # 4. Price
            try:
                price_xpath = ".//span[contains(text(), 'Khởi điểm từ')]/ancestor::div[contains(@class, 'flex-col')]//div[contains(@class, 'text-base')]"
                price_elm = card_section.find_element(By.XPATH, price_xpath)
                currency = "VND" if "VND" in card_section.get_attribute("innerText") else ""
                data["Start Price"] = f"{price_elm.text.strip()} {currency}"
            except:
                data["Start Price"] = "Thỏa thuận/Chưa đặt"

            # 5. Tags
            try:
                tags = []
                tag_elms = card_section.find_elements(By.XPATH, ".//div[contains(@class, 'rc-overflow')]//div[contains(@class, 'rc-overflow-item')]//div[contains(@class, 'truncated__text-single')]")
                for t in tag_elms:
                    txt = t.get_attribute("textContent").strip()
                    if txt and len(txt) > 1 and txt != data["ID"]:
                        tags.append(txt)
                data["Tags"] = ", ".join(list(set(tags)))
            except: pass

            # 6. Avatar
            try:
                avatar_img = card_section.find_element(By.XPATH, ".//div[contains(@class,'creator-avatar__wrapper')]//img")
                raw_url = avatar_img.get_attribute("data-src") or avatar_img.get_attribute("src")
                data["avatar_url"] = raw_url.strip() if raw_url else ""
                
                # Gọi Cleaner để tải ảnh
                if data["avatar_url"]:
                    data["avatar_local_path"] = DataCleaner.download_avatar(data["avatar_url"], creator_id)
            except: pass

        except Exception: pass
        return data

    def run(self):
        try:
            self.driver.get("https://ads.tiktok.com/creative/creator/explore?region=row")
            self.driver.maximize_window()
            time.sleep(5)

            # --- Apply Filters ---
            print("--- [BOT] Đang áp dụng bộ lọc ---")
            if self.safe_click("//div[contains(@class,'filter-trigger')][1]"):
                time.sleep(1)
                self.safe_click("//div[contains(@class, 'truncated__text') and text()='Việt Nam']")
                self.safe_click("//button[contains(text(), 'Áp dụng')]")
            time.sleep(5)

            # --- Main Loop ---
            print("\n--- [BOT] BẮT ĐẦU CÀO DỮ LIỆU ---")
            new_items_count = 0
            consecutive_duplicates = 0
            last_highest_index = -1
            retry_scroll = 0

            # Wait for list load
            try: self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-index='0']")))
            except: pass

            while new_items_count < TARGET_NEW_ITEMS:
                # Anti-ban break
                if new_items_count > 0 and new_items_count % 100 == 0:
                    print(f"\n>>> [ANTI-BAN] Đã lấy {new_items_count} người. Nghỉ 60s...")
                    time.sleep(60)
                    self.driver.execute_script("window.scrollBy(0, -200);")

                visible_rows = self.driver.find_elements(By.CSS_SELECTOR, "div[data-index]")
                if not visible_rows:
                    time.sleep(1)
                    continue

                current_row_indices = []

                for row in visible_rows:
                    try:
                        current_row_indices.append(int(row.get_attribute("data-index")))
                        creator_cards = row.find_elements(By.TAG_NAME, "section")

                        for card in creator_cards:
                            c_id = self.get_creator_id_only(card)
                            if c_id == "N/A": continue

                            if c_id in self.existing_ids:
                                consecutive_duplicates += 1
                                if consecutive_duplicates % 10 == 0: print(".", end="", flush=True)
                                continue
                            
                            # Found new creator
                            consecutive_duplicates = 0
                            info = self.extract_full_details(card, c_id)
                            
                            if self.db.upsert_creator(info):
                                self.existing_ids.add(c_id)
                                new_items_count += 1
                                print(f"\n [NEW #{new_items_count}] {info['ID']} | FL: {info['Followers']}")

                    except StaleElementReferenceException: continue

                # Scroll Logic
                if not current_row_indices: break
                max_row_idx = max(current_row_indices)

                if max_row_idx == last_highest_index:
                    retry_scroll += 1
                    print(f" [Wait load {retry_scroll}]", end="\r")
                    if retry_scroll >= 3: self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    elif retry_scroll >= 5: 
                        self.driver.execute_script("window.scrollBy(0, -300);")
                        time.sleep(1)
                        self.driver.execute_script("window.scrollBy(0, 1000);")
                    if retry_scroll > 15: break
                else:
                    retry_scroll = 0
                    last_highest_index = max_row_idx
                    try:
                        if visible_rows:
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", visible_rows[-1])
                        else: self.driver.execute_script("window.scrollBy(0, 800);")
                    except: self.driver.execute_script("window.scrollBy(0, 800);")
                
                self.random_sleep(2, 3)

            print(f"\n[BOT] Hoàn tất! Đã thu thập {new_items_count} người.")

        except Exception as e:
            print(f"[BOT] Lỗi Runtime: {e}")
        finally:
            self.driver.quit()