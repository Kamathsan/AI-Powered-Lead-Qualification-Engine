# scraper.py
import time
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -----------------------------------
# Selectors
# -----------------------------------
BASE_URL = "https://hitmarker.net/jobs?categories=art-animation"
COOKIE_BUTTON_ID = "cookie-consent-accept-all"
JOB_CARD_SELECTOR = "a.block.border-alpha-4"
TITLE_SELECTOR_H2 = "h2.font-medium"
TITLE_SELECTOR_SPAN = "span.font-bold"
INFO_CONTAINER_SELECTOR = "div.flex.flex-wrap.text-alpha-7"
COMPANY_PATH = "div:nth-child(1) > span.truncate"
LOCATION_PATH = "div:nth-child(2) > span.truncate"


# =====================================================================
#   SCRAPER CORE (NOW SUPPORTS AUTO-ALL-PAGES)
# =====================================================================
def scrape_all_pages(max_pages=20, auto_all_pages=False):
    print("Starting scraper…")

    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")

    # Disable image loading (20–30% speed improvement)
    chrome_prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", chrome_prefs)

    driver = uc.Chrome(options=chrome_options)
    driver.implicitly_wait(0.4)
    wait = WebDriverWait(driver, 6)

    all_jobs = []
    seen_urls = set()
    page = 1

    try:
        while True:

            # ---------- Manual page limit ----------
            if not auto_all_pages and page > max_pages:
                break

            url = f"{BASE_URL}&page={page}"
            print(f"\n🔎 Page {page} → {url}")
            driver.get(url)

            # Cookie banner only on first page
            if page == 1:
                try:
                    btn = wait.until(EC.element_to_be_clickable((By.ID, COOKIE_BUTTON_ID)))
                    btn.click()
                except:
                    pass

            # Wait for job cards (auto-stop if none)
            try:
                wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, JOB_CARD_SELECTOR)))
            except TimeoutException:
                print("No job cards → stopping.")
                break

            cards = driver.find_elements(By.CSS_SELECTOR, JOB_CARD_SELECTOR)
            print(f"Found {len(cards)} jobs.")

            if len(cards) == 0:
                print("Empty page → stopping.")
                break

            # ---------- Extract job info ----------
            for card in cards:
                try:
                    job_url = card.get_attribute("href")
                    if job_url in seen_urls:
                        continue

                    # Title extraction fallback
                    try:
                        title = card.find_element(By.CSS_SELECTOR, TITLE_SELECTOR_H2).text
                    except:
                        try:
                            title = card.find_element(By.CSS_SELECTOR, TITLE_SELECTOR_SPAN).text
                        except:
                            continue

                    info = card.find_element(By.CSS_SELECTOR, INFO_CONTAINER_SELECTOR)
                    company = info.find_element(By.CSS_SELECTOR, COMPANY_PATH).text
                    location = info.find_element(By.CSS_SELECTOR, LOCATION_PATH).text

                    all_jobs.append({
                        "company": company,
                        "title": title,
                        "location": location,
                        "url": job_url
                    })

                    seen_urls.add(job_url)

                except NoSuchElementException:
                    continue

            page += 1
            time.sleep(0.4)

    except Exception as e:
        print("Scraper error:", e)

    finally:
        driver.quit()

    print(f"\nScraping complete → {len(all_jobs)} jobs.")
    return all_jobs


# =====================================================================
# STREAMLIT WRAPPER
# =====================================================================
def scrape_jobs(keyword: str, max_pages: int, auto_all_pages: bool = False):
    """
    Called from dashboard.py.
    - keyword: job keyword (art, animation, unreal, etc)
    - max_pages: user-defined page count
    - auto_all_pages: if True → scrape until no more pages
    """
    global BASE_URL
    BASE_URL = f"https://hitmarker.net/jobs?keyword={keyword}&search={keyword}"

    jobs = scrape_all_pages(max_pages, auto_all_pages)
    return pd.DataFrame(jobs)
