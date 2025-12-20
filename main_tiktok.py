from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from pymongo import MongoClient
import time
import pandas as pd
import random
import re
import os
import stat
import platform
from pathlib import Path
import json
import argparse

# --- 1. CẤU HÌNH --- ( Tinh chỉnh theo cá nhân)
# MY_PROFILE_PATH = "" #cấu hình cookie của máy 
# GECKO_PATH = r"C:\Users\Admin\Desktop\TANPHAT\Manguonmotrongkhoahocjdulieu\DOAN_MNM\tiktok\geckodriver.exe"
# FIREFOX_BINARY_PATH = r"C:\Program Files\Mozilla Firefox\firefox.exe"

#cua TanPhat
# Configure these if you want to reuse your Firefox profile and a local geckodriver
# MY_PROFILE_PATH: set to your Firefox profile "Root Directory" from about:profiles (optional)
MY_PROFILE_PATH = ""  # set to your Firefox profile folder if you want to reuse a logged-in profile

# GECKO_PATH: prefer to use a geckodriver next to this script, otherwise fall back to common locations
proj_root = Path(__file__).parent
if platform.system() == "Windows":
    default_gecko = proj_root / "geckodriver.exe"
else:
    default_gecko = proj_root / "geckodriver"

GECKO_PATH = str(default_gecko)

# FIREFOX_BINARY_PATH: set if Firefox is installed in a non-standard location
FIREFOX_BINARY_PATH = "/Applications/Firefox.app/Contents/MacOS/firefox"

TARGET_CREATOR_COUNT = 3 # Số Creator muốn lấy
# OUTPUT_FILE removed — storing results in MongoDB instead.
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "tiktok_creators_db"
MONGO_COLLECTION = "creators"
TARGET_URL = "https://ads.tiktok.com/creative/forpartners/creator/explore?region=row&from_creative=login"
DEFAULT_COOKIES = Path(__file__).parent / "ads.tiktok.com_cookies.txt"

def find_cookie_file(provided_path: str = None) -> str:
    """Resolve cookie file path.
    Priority: provided_path (CLI/ENV) -> DEFAULT_COOKIES.
    Returns string path or empty string if not found.
    """
    # 1) explicit path
    if provided_path:
        p = Path(provided_path).expanduser()
        if p.exists():
            return str(p)

    # 2) default location next to script
    if DEFAULT_COOKIES.exists():
        return str(DEFAULT_COOKIES)

    return ""

# COOKIES_FILE will be resolved at runtime from CLI/ENV/default
COOKIES_FILE = ""

#---------------------------



#Hàm hỗ trợ 

def random_sleep(min_s = 2, max_s = 4):
    time.sleep(random.uniform(min_s, max_s))
    
def safe_click(driver, xpath, retries=3):
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

def extract_creator_data(card):
    """
    card = <section data-testid="ExploreCreatorCard-index-...">
    """
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
        "Start Price": "Thỏa thuận/Chưa đặt",
        "Tags": ""
    }

    # Index (lấy từ ancestor data-index)
    try:
        data["Index"] = card.find_element(
            By.XPATH, "./ancestor::div[@data-index]"
        ).get_attribute("data-index")
    except:
        pass

    # ID
    try:
        data["ID"] = card.find_element(
            By.CSS_SELECTOR,
            ".text-black.font-semibold .truncated__text-single"
        ).text.strip()
    except:
        pass

    # Name
    try:
        data["Name"] = card.find_element(
            By.CSS_SELECTOR,
            ".text-neutral-onFillLow .truncated__text-single"
        ).text.strip()
    except:
        pass

    # Country
    try:
        data["Country"] = card.find_element(
            By.CSS_SELECTOR,
            ".fi + .truncated__text-single"
        ).text.strip()
    except:
        pass

    # Scores
    try:
        data["Collab Score"] = card.find_element(
            By.XPATH, ".//*[contains(text(),'Điểm cộng tác tổng thể')]"
        ).text.split(":")[-1].strip()
    except:
        pass

    try:
        data["Broadcast Score"] = card.find_element(
            By.XPATH, ".//*[contains(text(),'Điểm phát sóng cao')]"
        ).text.split(":")[-1].strip()
    except:
        pass

    # Metrics
    try:
        metrics = card.find_elements(By.CSS_SELECTOR, ".text-base.font-semibold")
        if len(metrics) >= 3:
            data["Followers"] = metrics[0].text.strip()
            data["Median Views"] = metrics[1].text.strip()
            data["Engagement"] = metrics[2].text.strip()
    except:
        pass

    # Start Price
    try:
        price = card.find_element(
            By.XPATH, ".//span[text()='Khởi điểm từ']/following-sibling::span"
        )
        data["Start Price"] = price.text.strip()
    except:
        pass

    # Tags
    try:
        tags = card.find_elements(
            By.CSS_SELECTOR,
            ".bg-support-surface2 .truncated__text-single"
        )
        data["Tags"] = ", ".join(sorted({t.text.strip() for t in tags if t.text.strip()}))
    except:
        pass

    return data


# --- 3. KHỞI TẠO DRIVER ---
# Ensure geckodriver exists; fallback to common locations if not
gecko_path = Path(GECKO_PATH)
if not gecko_path.exists():
    # common macOS/homebrew and linux locations
    candidates = [
        Path("/opt/homebrew/bin/geckodriver"),
        Path("/usr/local/bin/geckodriver"),
        Path("/usr/bin/geckodriver")
    ]
    for c in candidates:
        if c.exists():
            gecko_path = c
            break

if not gecko_path.exists():
    print(f"[WARN] geckodriver not found at {GECKO_PATH} or common locations. Make sure geckodriver is installed and on PATH.")
else:
    try:
        gecko_path.chmod(gecko_path.stat().st_mode | stat.S_IEXEC)
    except Exception:
        pass

ser = None
try:
    if gecko_path.exists():
        ser = Service(executable_path=str(gecko_path))
    else:
        # let selenium find geckodriver on PATH
        ser = None
except Exception:
    ser = None

options = webdriver.firefox.options.Options()
if FIREFOX_BINARY_PATH and Path(FIREFOX_BINARY_PATH).exists():
    options.binary_location = FIREFOX_BINARY_PATH

# Only add profile args when provided and the folder exists
if MY_PROFILE_PATH and Path(MY_PROFILE_PATH).exists():
    options.add_argument("-profile")
    options.add_argument(MY_PROFILE_PATH)
else:
    if MY_PROFILE_PATH:
        print(f"[WARN] MY_PROFILE_PATH not found: {MY_PROFILE_PATH}. Proceeding with a fresh/profile-less Firefox session.")

options.set_preference("dom.webdriver.enabled", False)
options.set_preference("useAutomationExtension", False)

driver = None 

print("WARNING: Hãy TẮT HOÀN TOÀN Firefox thật trước khi chạy!")
print("Đang khởi động Firefox...")

if ser:
    driver = webdriver.Firefox(options=options, service=ser)
else:
    driver = webdriver.Firefox(options=options)
wait = WebDriverWait(driver, 30)
action = ActionChains(driver)

# Vào trang Ads
# If you have an exported cookies JSON file (from tiktokone), load them and inject into the session
def _load_cookies_from_file(path):
    # Support two formats: JSON array/object or Netscape cookies.txt
    p = Path(path)
    if not p.exists():
        return None
    try:
        text = p.read_text(encoding='utf-8')
    except Exception as e:
        print(f"[WARN] Failed to read cookies file {path}: {e}")
        return None

    # Netscape format (cookies.txt) detection: lines starting with '# Netscape'
    lines = [ln for ln in text.splitlines()]
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

    # Otherwise try JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict) and 'cookies' in data:
            return data['cookies']
        if isinstance(data, list):
            return data
    except Exception as e:
        print(f"[WARN] Cookie file is not JSON and not Netscape format: {e}")

    return None


def _apply_cookies(driver, cookies):
    # Group cookies by domain to ensure we are on the correct origin before adding
    domains = {}
    for c in cookies:
        if not isinstance(c, dict):
            continue
        d = c.get('domain') or c.get('Domain') or ''
        d = d.lstrip('.') if isinstance(d, str) else ''
        domains.setdefault(d, []).append(c)

    applied_total = 0
    # If no domain information, try to add them on the current page
    if not domains:
        domains = {'': cookies}

    for domain, domain_cookies in domains.items():
        # Determine base URL to navigate to before setting cookies
        if domain:
            base = f"https://{domain}"
        else:
            base = None

        if base:
            try:
                driver.get(base)
                time.sleep(0.5)
            except Exception as e:
                print(f"[WARN] Could not navigate to {base} to set cookies: {e}")

        # Optionally clear existing cookies on that origin to avoid conflicts
        try:
            driver.delete_all_cookies()
        except Exception:
            pass

        for c in domain_cookies:
            try:
                cookie = dict(c)
                if 'name' not in cookie or 'value' not in cookie:
                    continue
                # Normalize cookie fields
                cookie.pop('sameSite', None)
                cookie.pop('hostOnly', None)
                # Convert expiry to int if present
                if 'expiry' in cookie:
                    try:
                        cookie['expiry'] = int(cookie['expiry'])
                    except Exception:
                        cookie.pop('expiry', None)

                # Selenium requires name/value and will accept domain/path if on same origin
                try:
                    driver.add_cookie(cookie)
                    applied_total += 1
                except Exception as e:
                    # Try without domain/path if Selenium rejects
                    cookie2 = {k: v for k, v in cookie.items() if k in ('name', 'value', 'path', 'expiry', 'secure', 'httpOnly')}
                    try:
                        driver.add_cookie(cookie2)
                        applied_total += 1
                    except Exception as e2:
                        print(f"[DEBUG] Could not add cookie '{cookie.get('name')}' for domain '{domain}': {e2}")
            except Exception as e:
                print(f"[DEBUG] Skipping invalid cookie entry: {e}")

    return applied_total


print(f"Truy cập: {TARGET_URL}")

# Resolve cookie file from CLI/ENV/default/search
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--cookies', '-c', help='Path to cookies JSON file to inject')
args, _ = parser.parse_known_args()
env_cookie = os.environ.get('TIKTOK_COOKIES')
COOKIES_FILE = find_cookie_file(args.cookies or env_cookie)

if COOKIES_FILE:
    print(f"[INFO] Loading cookies from {COOKIES_FILE}")
    cookies = _load_cookies_from_file(COOKIES_FILE)
    if cookies:
        # Navigate to base domain so cookies can be set
        try:
            applied = _apply_cookies(driver, cookies)
            print(f"[INFO] Applied {applied} cookies (across detected domains)")
            # Refresh to apply cookies
            driver.refresh()
            time.sleep(1)
        except Exception as e:
            print(f"[WARN] Failed to apply cookies: {e}")
    else:
        print("[WARN] No cookies found in file or invalid format.")
else:
    print(f"[INFO] No cookies file found (searched defaults and env). Proceeding without injecting cookies.")

driver.get(TARGET_URL)
driver.maximize_window()
time.sleep(5) 

try:
    container = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.virtualCardResults"))
    )
except TimeoutException:
    # If we landed on a login page, prompt the user to authenticate manually
    login_detected = False
    try:
        maybe_login = driver.find_elements(By.XPATH, "//button[contains(., 'Log in') or contains(., 'Đăng nhập') or contains(., 'Sign in')]")
        if maybe_login:
            login_detected = True
    except Exception:
        maybe_login = []

    url_lower = driver.current_url.lower() if driver.current_url else ""
    title_lower = driver.title.lower() if driver.title else ""
    if "login" in url_lower or "log in" in title_lower or login_detected:
        print("[INFO] It looks like you're on a login page. Please log in using the opened Firefox window.")
        print("After completing login, the page should redirect back to the creator explorer.")
        try:
            input("When you've logged in and the page has redirected, press Enter to continue (or Ctrl-C to abort)...\n")
        except Exception:
            # If input is not available, fall back to a timed wait
            print("[WARN] No interactive input available; will wait 60 seconds for page to load...")
            try:
                container = WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.virtualCardResults"))
                )
            except TimeoutException:
                container = None

        # Try again to locate container after manual login
        try:
            container = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.virtualCardResults"))
            )
            print("[INFO] Found creator container after login. Continuing...")
        except TimeoutException:
            # fall through to save debug artifacts below
            pass

    # If container still not found, save artifacts and exit with diagnostics
    if 'container' not in locals() or container is None:
        ts = int(time.time())
        png = f"debug_page_{ts}.png"
        html = f"debug_page_{ts}.html"
        try:
            driver.save_screenshot(png)
            with open(html, "w", encoding="utf-8") as fh:
                fh.write(driver.page_source)
            print(f"[DEBUG] Saved screenshot -> {png}")
            print(f"[DEBUG] Saved page source -> {html}")
        except Exception as e:
            print(f"[DEBUG] Failed to save debug artifacts: {e}")

        print("[ERROR] Timeout waiting for 'div.virtualCardResults'. Possible causes:")
        print(" - Not logged in / redirected to login page")
        print(" - Page structure changed (selector no longer exists)")
        print(" - Network or loading issue")
        print("Current URL:", driver.current_url)
        print("Page title:", driver.title)

        # Quit driver and raise for visibility
        try:
            driver.quit()
        except:
            pass
        raise

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
            # collect numeric indices so we can detect progress when scrolling
            try:
                idx_val = info.get('Index')
                if idx_val and idx_val != 'N/A':
                    try:
                        current_idxs.append(int(idx_val))
                    except Exception:
                        # try to extract digits
                        m = re.search(r"(\d+)", str(idx_val))
                        if m:
                            current_idxs.append(int(m.group(1)))
            except Exception:
                pass

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
# df = pd.DataFrame(collected.values())
# cols = [
#     "Index", "ID", "Name", "Country",
#     "Collab Score", "Broadcast Score",
#     "Followers", "Median Views", "Engagement",
#     "Start Price", "Tags"
# ]
# df = df[cols]
# df.to_excel(OUTPUT_FILE, index=False)
# print(f"Saved {len(df)} creators")
# print("=== DONE ===")

# connecting to mongodb

    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    creators_collection = db[MONGO_COLLECTION]

    # Insert or upsert data into MongoDB
    if collected:
        upserted = 0
        updated = 0
        for creator in list(collected.values()):
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

        print(f"DB: upserted={upserted}, updated={updated} (total processed={len(collected)})")
    else:
        print("No data to insert into MongoDB")

    # Optional: print inserted documents summary (limit to 10)
    if collected:
        print("Sample documents in DB:")
        for creator in creators_collection.find().limit(10):
            print(creator)

