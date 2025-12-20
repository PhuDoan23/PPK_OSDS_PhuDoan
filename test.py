import time
import random
import re
import os
import sys
import platform
import json
import argparse
from pathlib import Path
from pymongo import MongoClient

from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

# ==========================================
# 1. CONFIGURATION
# ==========================================

# MongoDB
MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB = "tiktok_creators_db"
MONGO_COLLECTION = "creators"

# Scraping Targets
TARGET_CREATOR_COUNT = 10
TARGET_URL = "https://ads.tiktok.com/creative/forpartners/creator/explore?region=row&from_creative=login"

# Paths
PROJ_ROOT = Path(__file__).parent
# Detect OS for geckodriver name
if platform.system() == "Windows":
    GECKO_PATH = PROJ_ROOT / "geckodriver.exe"
else:
    GECKO_PATH = PROJ_ROOT / "geckodriver"

# Optional: Path to specific Firefox Profile (leave empty if not using)
MY_PROFILE_PATH = "" 
# Optional: Path to specific Firefox Binary (leave None to use default system Firefox)
FIREFOX_BINARY_PATH = None 

# Cookie File
DEFAULT_COOKIES = PROJ_ROOT / "ads.tiktok.com_cookies.txt"


# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

def random_sleep(min_s=2, max_s=4):
    time.sleep(random.uniform(min_s, max_s))

def extract_creator_data(card):
    """
    Extracts data from a single creator card DOM element.
    """
    data = {
        "Index": None,
        "ID": None,
        "username": None,
        "display_name": None,
        "profile_url": None,
        "Country": None,
        "Followers": None,
        "Median Views": None,
        "Engagement": None,
        "overall_score": None,
        "Tags": [],
        "scraped_at": time.time()
    }

    try:
        # 1. Index and raw HTML (for debug)
        data['Index'] = card.get_attribute('data-index')

        # 2. Profile URL, Username, Display Name
        try:
            a_tag = card.find_element(By.XPATH, ".//a[contains(@href, '/@')]")
            href = a_tag.get_attribute('href')
            if href:
                data['profile_url'] = href
                # Extract username from URL (e.g. /@username)
                match = re.search(r"/@([^/?#]+)", href)
                if match:
                    data['username'] = match.group(1)
                    data['ID'] = match.group(1) # Use username as ID
            
            # Display Name
            txt = a_tag.text.strip()
            if txt:
                data['display_name'] = txt
        except NoSuchElementException:
            pass

        # 3. Country (Heuristic: Short text that isn't the name)
        try:
            # Look for small text usually indicating location
            candidates = card.find_elements(By.CSS_SELECTOR, ".text-xs, .truncated__text-single")
            for c in candidates:
                txt = c.text.strip()
                # If text is alphabetic, short, and not the username
                if txt and re.match(r'^[A-Za-z \-]{2,30}$', txt):
                    if txt.lower() != (data.get('username') or '').lower():
                        data['Country'] = txt
                        break
        except Exception:
            pass

        # 4. Metrics (Followers, Views, Engagement)
        # Strategy: Get all text, regex for patterns if specific selectors fail
        card_text = card.get_attribute("innerText") or ""
        
        # Followers
        if "Followers" in card_text:
            m = re.search(r"([\d,.]+[KkMm]?)\s*Followers", card_text, re.IGNORECASE)
            if m: data['Followers'] = m.group(1)
        
        # Engagement
        if "Engagement" in card_text:
            m = re.search(r"([\d,.]+%?)\s*Engagement", card_text, re.IGNORECASE)
            if m: data['Engagement'] = m.group(1)

        # Median Views
        if "Median" in card_text:
            m = re.search(r"([\d,.]+[KkMm]?)\s*Median", card_text, re.IGNORECASE)
            if m: data['Median Views'] = m.group(1)

        # 5. Scores (Overall)
        try:
            # Try to find the tag specifically
            score_tag = card.find_element(By.XPATH, ".//*[contains(text(), 'Overall collaboration score')]")
            # The number is usually nearby or in the text
            m = re.search(r"(\d+)", score_tag.text)
            if m: data['overall_score'] = m.group(1)
        except:
            # Fallback regex on whole card
            m = re.search(r"Overall collaboration score[:\s]*(\d+)", card_text)
            if m: data['overall_score'] = m.group(1)

        # 6. Tags
        try:
            tags = card.find_elements(By.XPATH, ".//*[contains(@data-testid, 'CreatorTags')]")
            data['Tags'] = [t.text.strip() for t in tags if t.text.strip()]
        except:
            pass

    except Exception as e:
        print(f"[WARN] Error parsing card {data.get('Index')}: {e}")

    return data

def load_cookies_from_file(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding='utf-8')
        # Try JSON
        try:
            data = json.loads(content)
            if isinstance(data, dict) and 'cookies' in data: return data['cookies']
            if isinstance(data, list): return data
        except json.JSONDecodeError:
            pass
        # Fallback for Netscape/Cookies.txt format would go here
    except Exception as e:
        print(f"[ERR] Failed to read cookie file: {e}")
    return None

def apply_cookies(driver, cookies):
    if not cookies: return
    # Navigate to base domain first
    try:
        driver.get("https://ads.tiktok.com")
        time.sleep(1)
    except: pass
    
    count = 0
    for cookie in cookies:
        try:
            c = {
                'name': cookie.get('name'),
                'value': cookie.get('value'),
                'domain': cookie.get('domain', '.tiktok.com'),
                'path': cookie.get('path', '/'),
                'expiry': int(cookie.get('expiry')) if cookie.get('expiry') else None
            }
            # Cleanup keys that Selenium doesn't like
            if c['domain'].startswith('.'): 
                # Sometimes helps to strip leading dot or ensure we are on that domain
                pass 
            driver.add_cookie(c)
            count += 1
        except Exception:
            continue
    print(f"[INFO] Applied {count} cookies.")
    driver.refresh()

# ==========================================
# 3. MAIN SCRIPT
# ==========================================

if __name__ == "__main__":
    # 1. Setup MongoDB
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        collection = db[MONGO_COLLECTION]
        print(f"[INFO] DB Connected: {MONGO_DB}.{MONGO_COLLECTION}")
    except Exception as e:
        print(f"[FATAL] MongoDB Connection Failed: {e}")
        sys.exit(1)

    # 2. Setup Selenium Driver
    if not Path(GECKO_PATH).exists():
        print(f"[WARN] Geckodriver not found at {GECKO_PATH}. Ensure it is installed.")
    
    options = webdriver.FirefoxOptions()
    if FIREFOX_BINARY_PATH:
        options.binary_location = FIREFOX_BINARY_PATH
    if MY_PROFILE_PATH:
        options.add_argument("-profile")
        options.add_argument(MY_PROFILE_PATH)

    # Init Driver
    service = Service(str(GECKO_PATH)) if Path(GECKO_PATH).exists() else None
    print("[INFO] Starting Firefox...")
    driver = webdriver.Firefox(options=options, service=service) if service else webdriver.Firefox(options=options)
    wait = WebDriverWait(driver, 30)

    # 3. Load & Apply Cookies
    cookies = load_cookies_from_file(DEFAULT_COOKIES)
    if cookies:
        apply_cookies(driver, cookies)

    # 4. Navigate
    print(f"[INFO] Navigating to {TARGET_URL}")
    driver.get(TARGET_URL)

    # 5. Check Login
    time.sleep(5)
    if "login" in driver.current_url.lower():
        print("\n[!!!] LOGIN REQUIRED [!!!]")
        print("Please log in manually in the browser.")
        input("Press ENTER here once logged in and redirected to the Marketplace...\n")
    
    # 6. Wait for Content
    try:
        container = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.virtualCardResults, div[class*='virtualCardResults']")))
        print("[INFO] Content container found.")
    except TimeoutException:
        print("[ERR] Timeout waiting for creator cards. Exiting.")
        driver.quit()
        sys.exit(1)

    # 7. Scraping Loop
    collected_keys = set()
    total_processed = 0
    retry_scroll_count = 0

    while total_processed < TARGET_CREATOR_COUNT:
        # Find all card wrappers
        cards = container.find_elements(By.CSS_SELECTOR, "div[data-index]")
        
        new_data_found = False

        for card in cards:
            # We look for the inner section that actually has data
            try:
                # Some structure variations exist, try generic section or direct div
                inner = card.find_element(By.TAG_NAME, "section")
            except:
                inner = card

            info = extract_creator_data(inner)
            
            # Determine Unique Key for DB (Username is best, Fallback to Name+Index)
            unique_key = info.get('username') or info.get('ID')
            if not unique_key and info.get('display_name'):
                unique_key = f"{info['display_name']}_{info['Index']}"

            if unique_key and unique_key not in collected_keys:
                collected_keys.add(unique_key)
                
                # DB UPSERT
                try:
                    collection.update_one(
                        {"ID": unique_key}, # Query
                        {"$set": info},     # Update
                        upsert=True
                    )
                    print(f"[SAVE] #{info.get('Index')} {info.get('display_name')} | Followers: {info.get('Followers')}")
                    total_processed += 1
                    new_data_found = True
                except Exception as e:
                    print(f"[ERR] DB Save error: {e}")

        # Break if target reached
        if total_processed >= TARGET_CREATOR_COUNT:
            break

        # Scroll Logic
        if not new_data_found:
            retry_scroll_count += 1
            print(f"[INFO] Scrolling... (Attempt {retry_scroll_count})")
        else:
            retry_scroll_count = 0
            print(f"[INFO] Scrolling...")

        if retry_scroll_count > 5:
            print("[WARN] No new creators found after scrolling multiple times. Stopping.")
            break

        # Execute Scroll
        try:
            driver.execute_script("window.scrollBy(0, 800);")
        except: pass
        random_sleep(2, 4)

    print("=== FINISHED ===")
    print(f"Total Creators Processed: {total_processed}")
    driver.quit()