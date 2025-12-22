import time
import random
import re
import pandas as pd
import os
import json
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
import json
from selenium.webdriver.common.keys import Keys

# 1. Configuration
MY_PROFILE_PATH = "./ads.tiktok.com_cookies.txt"
FIREFOX_BINARY_PATH = "/Applications/Firefox.app/Contents/MacOS/firefox"
GECKODRIVER_PATH = "./geckodriver"
TARGET_CREATOR_COUNT = 50
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "ContentCreators1K"
MONGO_COLLECTION = "content_creators"

#2 support functions
def random_sleep(min=2, max=5):
    time.sleep(random.uniform(min, max))

def safe_click(driver, xpath, retries=3):
    for attempt in range(retries):
        try:
            element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            element.click()
            return
        except StaleElementReferenceException:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                raise

def extract_creator_data(card):
    """
    Hàm trích xuất dữ liệu từ một thẻ creator trên TikTok
    """
    data = {
        "Index": "",
        "ID": "",
        "Name": "",
        "Username": "",
        "Country": "",
        "Collab Score": "",
        "Billboard Score": "",
        "Followers": "",
        "Median Views": "",
        "Engagement": "",
        "Start Price": "",
        "Tags": ""
    }
    try:
        # Estract Index
        data["Index"] = card.get_attribute("data-index")
        # Estract ID
        try:
            id_element = card.find_element(By.XPATH, ".//div[contains(@class, 'text-black') and contains(@class, 'font-semibold')]//div[contains(@class, 'truncated__text-single')]")
            data["ID"] = id_element.text.strip()
        except:
            pass
        
        # Estract Name
        try:
            name_element= card.find_element(By.XPATH, ".//div[contains(@class, 'text-neutral-onFillLow')]//div[contains(@class, 'truncated__text-single')]")
            data["Name"] = name_element.text.strip()
        except:
            pass   
        
        # Estract Country
        try:
            country_element = card.find_element(By.XPATH, ".//div[contains(@class, 'truncated__text-single') and text()='Việt Nam']")
            data["Country"] = country_element.text.strip()
        except:
            pass
        
        # 4. Estract Scores: Billboard, Collab, Broadcast
        try:
            collab_elm = card.find_element(By.XPATH, ".//*[contains(text(), 'Điểm cộng tác')]")
            data["Collab Score"] = collab_elm.get_attribute("innerText").replace("Điểm cộng tác tổng thể:", "").strip()
        except: pass

        try:
            broad_elm = card.find_element(By.XPATH, ".//*[contains(text(), 'Điểm phát sóng')]")
            data["Broadcast Score"] = broad_elm.get_attribute("innerText").replace("Điểm phát sóng cao:", "").strip()
        except: pass

        # 5. Estract Metrics: Followers, Median Views, Engagement
        try:
            # Tìm TẤT CẢ các thẻ có class "text-base font-semibold" trong Card này.
            # Đây là class đặc trưng của số liệu, khác với class của ID (text-sm).
            metrics = card.find_elements(By.CSS_SELECTOR, ".text-base.font-semibold")
            
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

        # ==============================================================================
        # 6. [MỚI] LẤY GIÁ TIỀN (START PRICE)
        # ==============================================================================
        try:
            # Tìm thẻ chứa VND -> Lấy cha -> Lấy text-base
            price_elm = card.find_element(By.XPATH, ".//div[contains(text(), 'VND')]/parent::div//div[contains(@class, 'text-base')]")
            data["Start Price"] = f"{price_elm.text.strip()} VND"
        except: 
            # Fallback cho trường hợp "Chưa đặt" hoặc USD
            try:
                price_fallback = card.find_element(By.XPATH, ".//span[contains(text(), 'Khởi điểm từ')]/ancestor::div[contains(@class, 'flex-col')]//div[contains(@class, 'text-base') or contains(text(), 'Chưa đặt')]")
                data["Start Price"] = price_fallback.text.strip()
            except: pass

        # 7. Tags
        tags = []
        try:
            # Tìm tất cả các phần tử tag text nằm trong rc-overflow
            # Lưu ý: Tìm thẻ div có class 'truncated__text-single' nằm trong 'rc-overflow-item'
            tag_elms = card.find_elements(By.XPATH, ".//div[contains(@class, 'rc-overflow')]//div[contains(@class, 'rc-overflow-item')]//div[contains(@class, 'truncated__text-single')]")
            
            for t in tag_elms:
                # Dùng 'textContent' thay vì 'text' để lấy được nội dung dù nó bị ẩn (opacity: 0)
                txt = t.get_attribute("textContent").strip()
                
                # Lọc rác: 
                # - Tag phải dài > 1 ký tự
                # - Không phải là ID hay Tên (tránh trùng class)
                # - Không chứa dấu '+' (loại bỏ nút +4, +3...)
                if txt and len(txt) > 1 and txt != data["ID"] and txt != data["Name"] and "+" not in txt:
                    tags.append(txt)
                    
        except Exception as e:
            # print(f"Lỗi lấy tags: {e}")
            pass
        
        # Eliminate duplicates and join tags into a single string
        data["Tags"] = ", ".join(list(set(tags)))

    except Exception:
        pass
    
    return data


def _load_cookies_from_file(path):
    """Load cookies from a Netscape cookies.txt or a JSON file.
    Returns a list of cookie dicts suitable for selenium.add_cookie or None on failure.
    """
    p = os.path.expanduser(path)
    if not os.path.exists(p):
        return None
    try:
        with open(p, 'r', encoding='utf-8') as fh:
            text = fh.read()
    except Exception as e:
        print(f"[WARN] Failed to read cookies file {p}: {e}")
        return None

    lines = text.splitlines()
    # Netscape format detection
    if any(ln.startswith('# Netscape') for ln in lines[:5]):
        cookies = []
        for ln in lines:
            ln = ln.strip()
            if not ln or ln.startswith('#'):
                continue
            parts = ln.split('\t')
            if len(parts) < 7:
                continue
            domain, flag, path_field, secure_flag, expiry, name, value = parts[:7]
            cookie = {
                'domain': domain,
                'path': path_field,
                'name': name,
                'value': value,
                'secure': True if secure_flag.upper() == 'TRUE' or secure_flag == 'TRUE' else False,
            }
            try:
                cookie['expiry'] = int(expiry)
            except Exception:
                pass
            cookies.append(cookie)
        return cookies

    # Try JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict) and 'cookies' in data:
            return data['cookies']
        if isinstance(data, list):
            return data
    except Exception:
        pass

    return None


def _apply_cookies(driver, cookies):
    """Apply cookies to the webdriver session. Returns number applied."""
    if not cookies:
        return 0
    # Group by domain
    domains = {}
    for c in cookies:
        if not isinstance(c, dict):
            continue
        d = c.get('domain') or c.get('Domain') or ''
        d = d.lstrip('.') if isinstance(d, str) else ''
        domains.setdefault(d, []).append(c)

    applied = 0
    if not domains:
        domains = {'': cookies}

    for domain, domain_cookies in domains.items():
        base = f"https://{domain}" if domain else None
        if base:
            try:
                driver.get(base)
                time.sleep(0.5)
            except Exception as e:
                print(f"[WARN] Could not navigate to {base} to set cookies: {e}")

        try:
            driver.delete_all_cookies()
        except Exception:
            pass

        for c in domain_cookies:
            try:
                cookie = dict(c)
                # Ensure mandatory fields
                if 'name' not in cookie or 'value' not in cookie:
                    continue
                cookie.pop('sameSite', None)
                cookie.pop('hostOnly', None)
                if 'expiry' in cookie:
                    try:
                        cookie['expiry'] = int(cookie['expiry'])
                    except Exception:
                        cookie.pop('expiry', None)
                try:
                    driver.add_cookie(cookie)
                    applied += 1
                except Exception:
                    # try a minimal cookie
                    cookie2 = {k: v for k, v in cookie.items() if k in ('name', 'value', 'path', 'expiry', 'secure', 'httpOnly')}
                    try:
                        driver.add_cookie(cookie2)
                        applied += 1
                    except Exception as e:
                        print(f"[DEBUG] Could not add cookie '{cookie.get('name')}' for domain '{domain}': {e}")
            except Exception as e:
                print(f"[DEBUG] Skipping invalid cookie entry: {e}")

    return applied

def __main___():
    ser = Service(GECKODRIVER_PATH)
    option = webdriver.FirefoxOptions()
    option.binary_location = FIREFOX_BINARY_PATH
    # Determine whether MY_PROFILE_PATH is a Firefox profile directory or a cookies file.
    cookies_file = None
    if MY_PROFILE_PATH:
        if os.path.isdir(MY_PROFILE_PATH):
            option.add_argument("-profile")
            option.add_argument(MY_PROFILE_PATH)
        elif os.path.isfile(MY_PROFILE_PATH):
            # It's a file — assume it's a cookies file to be injected later.
            cookies_file = MY_PROFILE_PATH
            print(f"[INFO] Detected cookies file: {cookies_file}. Will attempt to inject cookies after browser starts.")
        else:
            print(f"[WARN] MY_PROFILE_PATH does not exist: {MY_PROFILE_PATH}. Ignoring profile argument.")

    # Try to set a minimal set of Firefox preferences; guard in case the browser/geckodriver rejects them.
    try:
        option.set_preference("dom.webdriver.enabled", False)
    except Exception as e:
        print(f"[WARN] Could not set preference dom.webdriver.enabled: {e}")
    
    driver = webdriver.Firefox(service=ser, options=option)
    wait = WebDriverWait(driver, 20)
    action = ActionChains(driver)
    # If a cookies file was provided, try to load and apply cookies now before navigating.
    if 'cookies_file' in locals() and cookies_file:
        cookies = _load_cookies_from_file(cookies_file)
        if cookies:
            applied = _apply_cookies(driver, cookies)
            print(f"[INFO] Applied {applied} cookies from {cookies_file}")
            try:
                driver.refresh()
            except Exception:
                pass
            time.sleep(1)
        else:
            print(f"[WARN] No cookies loaded from {cookies_file} (format not recognized or empty)")
    try:
        # 1. Truy cập trang chính TikTok Ads Creative Center
        initial_url = "https://ads.tiktok.com/creative/creator"
        print(f"Truy cập trang chính: {initial_url}")
        driver.get(initial_url)
        driver.maximize_window()
        time.sleep(3)

        # 2. CLICK VÀO NÚT "EXPLORE CREATORS"
        print("\n--- CLICK 'EXPLORE CREATORS' ---")
        explore_button_xpaths = [
            "//span[@data-inspector='t-e996ebaa2b850742' and contains(text(), 'Explore creators')]",
            "//span[contains(@class, 'text-gray-9') and contains(text(), 'Explore creators')]",
            "//span[contains(text(), 'Explore creators')]",
            "//button[.//span[contains(text(), 'Explore creators')]]",
            "//a[.//span[contains(text(), 'Explore creators')]]"
        ]
        
        button_clicked = False
        for xpath in explore_button_xpaths:
            try:
                button = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                button.click()
                print("✓ Đã click 'Explore creators'")
                button_clicked = True
                time.sleep(3)
                break
            except:
                continue
        
        if not button_clicked:
            print("[WARN] Không tìm thấy nút 'Explore creators', thử truy cập trực tiếp URL...")
            target_url = "https://ads.tiktok.com/creative/creator/explore?region=row"
            driver.get(target_url)
        
        time.sleep(5)

        # ---------------------------------------------------------
        # BƯỚC 3: XỬ LÝ BỘ LỌC (QUỐC GIA & GIÁ)
        # ---------------------------------------------------------
        print("\n--- CẤU HÌNH BỘ LỌC ---")
        
        # Helper function for robust clicking
        def robust_click(driver, xpath, method='js'):
            """Try multiple methods to click an element"""
            try:
                element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                
                if method == 'js':
                    # Use JavaScript click (bypasses overlay issues)
                    driver.execute_script("arguments[0].click();", element)
                    return True
                elif method == 'actions':
                    # Use ActionChains
                    ActionChains(driver).move_to_element(element).click().perform()
                    return True
                else:
                    # Standard click
                    element.click()
                    return True
            except Exception as e:
                print(f"[DEBUG] Click failed: {e}")
                # Try JavaScript as fallback
                try:
                    element = driver.find_element(By.XPATH, xpath)
                    driver.execute_script("arguments[0].click();", element)
                    return True
                except:
                    return False
        
        # A. Chọn Quốc Gia: Việt Nam
        # Tìm nút mở menu Quốc gia (thường là nút filter đầu tiên)
        print("Mở menu Quốc gia...")
        country_filter_xpaths = [
            "//div[contains(@class,'filter-trigger')][1]",
            "(//div[contains(@class,'filter-trigger')])[1]",
            "//div[@class='filter-trigger filter-trigger--invisible'][1]"
        ]
        
        country_opened = False
        for xpath in country_filter_xpaths:
            if robust_click(driver, xpath, method='js'):
                country_opened = True
                print("✓ Đã mở menu Quốc gia")
                time.sleep(2)
                break
        
        if country_opened:
            # Chọn Việt Nam
            vn_xpaths = [
                "//div[@data-inspector='t-899614ddd8915160' and contains(@class, 'truncated__text')]",
                "//div[contains(@class, 'truncated__text') and text()='Vietnam']",
                "//div[contains(@class, 'truncated__text') and contains(text(), 'Vietnam')]",
                "//div[contains(@class, 'truncated__text') and text()='Việt Nam']",
                "//span[text()='Vietnam']",
                "//*[text()='Vietnam']"
            ]
            
            vn_selected = False
            for vn_xpath in vn_xpaths:
                if robust_click(driver, vn_xpath, method='js'):
                    print(" -> ✓ Tick 'Vietnam'")
                    vn_selected = True
                    time.sleep(1)
                    break
            
            if not vn_selected:
                print("[!] Không thấy tùy chọn Vietnam")
            
            # Click Apply button after selecting Vietnam
            time.sleep(1)
            apply_xpaths = [
                "//button[@data-inspector='t-1e120eb24731b48d']",
                "//button[contains(@class, 'filter-apply__button')]",
                "//button[contains(@class, 'byted-btn-type-primary') and contains(text(), 'Apply')]",
                "//button[contains(text(), 'Apply')]",
                "//button[contains(text(), 'Áp dụng')]"
            ]
            
            apply_clicked = False
            for apply_xpath in apply_xpaths:
                if robust_click(driver, apply_xpath, method='js'):
                    print("✓ Đã bấm Apply")
                    apply_clicked = True
                    break
            
            if not apply_clicked:
                print("[!] Không tìm thấy nút Apply")
        else:
            print("[!] Không thể mở menu Quốc gia")

        time.sleep(3)

        print("\n--- BẮT ĐẦU CÀO DỮ LIỆU ---")
        print(f"Mục tiêu: Thu thập 1000 content creators")
        
        collected_data = {} 
        last_highest_index = -1
        retry_scroll = 0
        no_new_data_count = 0
        TARGET_CREATOR_COUNT = 1000  # Mục tiêu thu thập 1000 creators
        
        # Tìm container danh sách
        try:
            container = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@data-index='0']/..")))
        except:
            container = driver.find_element(By.TAG_NAME, "body")

        while len(collected_data) < TARGET_CREATOR_COUNT:
            visible_cards = driver.find_elements(By.CSS_SELECTOR, "div[data-index]")
            
            if not visible_cards:
                time.sleep(1)
                continue
                
            current_indices = []
            new_data_in_batch = 0
            
            for card in visible_cards:
                try:
                    idx_str = card.get_attribute("data-index")
                    if not idx_str: continue
                    idx = int(idx_str)
                    current_indices.append(idx)
                    
                    info = extract_creator_data(card)
                    key = info["ID"] if info["ID"] != "N/A" else info["Name"]
                    
                    if key != "N/A" and key not in collected_data:
                        collected_data[key] = info
                        new_data_in_batch += 1
                        # In ra màn hình để kiểm tra
                        print(f" [#{len(collected_data)}/{TARGET_CREATOR_COUNT}] {info['ID']} | FL: {info['Followers']} | Giá: {info['Start Price']}")
                except: continue

            if not current_indices: 
                print("[WARN] Không tìm thấy cards nào")
                break
            
            max_idx = max(current_indices)
            
            # Kiểm tra xem có dữ liệu mới không
            if new_data_in_batch == 0:
                no_new_data_count += 1
                print(f" ...Không có dữ liệu mới ({no_new_data_count}/15)...")
                if no_new_data_count >= 15:
                    print("[INFO] Đã hết dữ liệu hoặc đạt giới hạn của trang")
                    break
            else:
                no_new_data_count = 0
            
            if max_idx == last_highest_index:
                retry_scroll += 1
                print(f" ...Đang load thêm ({retry_scroll})...")
                
                # Thử các chiến lược scroll khác nhau
                if retry_scroll >= 3:
                    driver.execute_script("window.scrollBy(0, 1000);")
                    time.sleep(2)
                if retry_scroll >= 6:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(3)
                if retry_scroll > 12:
                    print("[WARN] Không thể scroll thêm, có thể đã đến cuối trang")
                    break
            else:
                retry_scroll = 0
                last_highest_index = max_idx
                
                # Scroll đến card cuối cùng
                try:
                    last_card = driver.find_element(By.CSS_SELECTOR, f"div[data-index='{max_idx}']")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", last_card)
                except:
                    driver.execute_script("window.scrollBy(0, 800);")
            
            random_sleep(1, 2)  # Giảm thời gian chờ để tăng tốc độ
            
        print(f"\n=== HOÀN THÀNH ===")
        print(f"Đã thu thập: {len(collected_data)}/{TARGET_CREATOR_COUNT} creators")
        
        # Connect du lieu vao Database MongoDB
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        creators_collection = db[MONGO_COLLECTION]

        # Insert or upsert data into MongoDB
        if collected_data:
            upserted = 0
            updated = 0
            for creator in list(collected_data.values()):
                # Use 'ID' field as unique key when available; otherwise fall back to a composite key
                key = None
                if creator.get('ID') and creator.get('ID') != 'N/A':
                    key = {'ID': creator['ID']}
                else:
                    key = {'Name': creator.get('Name', ''), 'Index': creator.get('Index')}

                try:
                    res = creators_collection.update_one(key, {'$set': creator}, upsert=True)
                    if res.matched_count:
                        updated += 1
                    else:
                        upserted += 1
                except Exception as e:
                    print(f"[WARN] Failed to upsert creator {creator.get('Name')} : {e}")

            print(f"DB: upserted={upserted}, updated={updated} (total processed={len(collected_data)})")
        else:
            print("No data to insert into MongoDB")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        print("Đóng trình duyệt...")
        driver.quit()


if __name__ == "__main__":
    __main___()
    
        
        

    