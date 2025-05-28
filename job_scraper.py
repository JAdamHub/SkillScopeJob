import sqlite3
import logging
import time
import random
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth

# Input Parameters
JOB_TITLE = "Product Manager"
LOCATION = "Copenhagen"  # or "Remote"

# Database setup
DB_NAME = 'job_postings.db'
TABLE_NAME = 'job_postings'

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Ethics & Legality Comment ---
# Scraping web pages should be done responsibly.
# 1. Always check the website's robots.txt.
# 2. Do not send too many requests in a short period.
# 3. Be aware that website structures change.
# 4. LinkedIn is highly restrictive.
# 5. Cloudflare or similar anti-bot services make scraping difficult.
#    Using browser automation (Selenium/Playwright) is often necessary
#    but can also be detected or fail, and is generally slower.
# --- End Ethics & Legality Comment ---

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_title TEXT,
        company TEXT,
        location TEXT,
        date_posted TEXT,
        employment_type TEXT,
        description TEXT,
        source_url TEXT UNIQUE,
        scraped_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()
    logging.info(f"Database '{DB_NAME}' initialized and table '{TABLE_NAME}' is ready.")

def insert_job_posting(job_data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(f"""
        INSERT INTO {TABLE_NAME} (job_title, company, location, date_posted, employment_type, description, source_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (job_data['job_title'], job_data['company'], job_data['location'],
              job_data['date_posted'], job_data['employment_type'], job_data['description'], job_data['source_url']))
        conn.commit()
        logging.info(f"Inserted job: {job_data['job_title']} at {job_data['company']}")
        return True
    except sqlite3.IntegrityError:
        logging.warning(f"Job with source_url {job_data['source_url']} already exists. Skipping.")
        return False
    except Exception as e:
        logging.error(f"Error inserting job data: {e}")
        return False
    finally:
        conn.close()

def get_job_description_selenium(driver, job_url):
    """Fetches and parses the full job description from a given job URL using Selenium."""
    try:
        driver.get(job_url)
        # Wait for the job description text container to be present
        desc_container = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "jobDescriptionText"))
        )
        # It can be beneficial to add a small artificial delay for dynamic content to settle
        time.sleep(random.uniform(0.5, 1.5))
        return desc_container.text # .text usually gets all visible text content
    except TimeoutException:
        logging.warning(f"Timeout waiting for job description container at {job_url}")
        return "Description not found (Timeout)"
    except NoSuchElementException:
        logging.warning(f"Could not find job description text container for {job_url} (NoSuchElement)")
        return "Description not found (NoSuchElement)"
    except WebDriverException as e:
        logging.error(f"WebDriverException while fetching description from {job_url}: {e}")
        return "Error fetching description (WebDriverException)"
    except Exception as e:
        logging.error(f"Unexpected error parsing description for {job_url}: {e}")
        return "Error parsing description"

def try_handle_popups(driver):
    """Attempts to close common pop-up dialogs like cookie consent or other modals."""
    popup_selectors = [
        (By.ID, "onetrust-accept-btn-handler"), # Common cookie consent
        (By.CSS_SELECTOR, "button[aria-label=\"close\"]"), # Generic close button often used in popups
        (By.CSS_SELECTOR, "button[aria-label=\"Close\"]") # Variation with capital C
    ]

    for by_method, selector_value in popup_selectors:
        try:
            popup_button = driver.find_element(by_method, selector_value)
            if popup_button.is_displayed() and popup_button.is_enabled():
                logging.info(f"Attempting to click popup button: {selector_value}")
                popup_button.click()
                time.sleep(random.uniform(1, 2)) # Wait for popup to disappear/process
                logging.info(f"Clicked popup button: {selector_value}")
                # Optional: Could add a break here if only one popup is expected at a time
        except NoSuchElementException:
            logging.debug(f"Popup button not found: {selector_value}")
        except Exception as e_popup:
            logging.warning(f"Error clicking popup button {selector_value}: {e_popup}")

def setup_driver():
    """Sets up the Selenium Chrome WebDriver with stealth capabilities."""
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # Make sure this line IS commented out for visible browser
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # Apply stealth settings
        stealth(driver,
                languages=["en-US", "en", "da"], # Added Danish
                vendor="Google Inc.",
                platform="Win32", # Can be "Win32", "Win64", "MacIntel", "Linux x86_64"
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
                run_on_insecure_origins=False # Set to True if testing on non-HTTPS sites sometimes
                )

        return driver
    except Exception as e:
        logging.error(f"Failed to setup ChromeDriver: {e}")
        logging.error("Please ensure Google Chrome is installed and accessible.")
        logging.error("If issues persist, try updating Chrome or manually managing ChromeDriver.")
        return None

def scrape_indeed_selenium(job_title_query, location_query, pages_to_scrape=1):
    base_url = "https://dk.indeed.com"
    jobs_collected = 0

    driver = setup_driver()
    if not driver:
        logging.error("WebDriver setup failed. Exiting scraper.")
        return

    try:
        for page in range(pages_to_scrape):
            start_param = page * 10
            search_url = f"{base_url}/jobs?q={job_title_query.replace(' ', '+')}&l={location_query.replace(' ', '+')}&start={start_param}"
            logging.info(f"Scraping page {page + 1} for '{job_title_query}' in '{location_query}': {search_url}")
            
            driver.get(search_url)
            logging.info("Page requested. Waiting for potential Cloudflare challenge or page load.")

            # Manual intervention period for Cloudflare/CAPTCHA
            manual_intervention_seconds = 25  # User-defined time for manual intervention
            logging.info(f"You now have {manual_intervention_seconds} seconds to manually solve any Cloudflare/CAPTCHA in the Selenium browser.")
            logging.info("If no challenge appears, the script will proceed after the timeout.")
            time.sleep(manual_intervention_seconds)
            logging.info("Proceeding after manual intervention period...")

            # Attempt to handle any overlay popups after manual intervention (or page load)
            try_handle_popups(driver)

            try:
                # Now, wait for job cards to be present on the page.
                WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.job_seen_beacon, div.jobsearch-SerpJobCard"))
                )
                # It's good practice to wait a bit for JS to finish loading all elements, especially on Indeed
                time.sleep(random.uniform(0.5, 2)) # User-defined shorter wait

            except TimeoutException:
                logging.error(f"Timeout waiting for job cards on page {page + 1}. URL: {search_url}")
                logging.info(f"Page source (first 500 chars): {driver.page_source[:500]}")
                # Check for CAPTCHA or consent pop-ups that might block content
                if " मानव " in driver.page_source or "human" in driver.page_source.lower() or "captcha" in driver.page_source.lower():
                    logging.warning("CAPTCHA or human verification detected in page source. Selenium might be blocked or manual intervention failed.")
                
                # One last attempt to handle popups if the initial one didn't clear the way for job cards
                logging.info("Re-attempting to handle popups after timeout waiting for job cards.")
                try_handle_popups(driver) 
                
                # If still no cards after handling potential pop-ups, skip page
                if not driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon, div.jobsearch-SerpJobCard"):
                    logging.warning(f"Still no job cards found on page {page+1} after checks. Skipping page.")
                    continue

            except WebDriverException as e:
                logging.error(f"WebDriverException while loading search page {page + 1}: {e}")
                continue

            # Use BeautifulSoup to parse the page source obtained from Selenium
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            job_cards = soup.select("div.job_seen_beacon, div.jobsearch-SerpJobCard")

            if not job_cards:
                logging.info(f"No job cards parsed by BeautifulSoup on page {page + 1}. URL: {search_url}")
                # print(driver.page_source) # For debugging
                continue

            for card_soup in job_cards: # Iterate over BeautifulSoup elements
                job_data = {
                    'job_title': None, 'company': None, 'location': None,
                    'date_posted': None, 'employment_type': 'Not Specified',
                    'description': None, 'source_url': None
                }

                try:
                    title_element = card_soup.select_one('h2.jobTitle a, h2.jobTitle span') 
                    # More robust selector for title, preferring the one inside 'a' if present
                    if title_element:
                        job_data['job_title'] = title_element.get_text(strip=True)
                        # Try to find the link associated with this title
                        link_tag = None
                        if title_element.name == 'a': # If the title_element itself is the <a> tag
                            link_tag = title_element
                        else: # If title_element is a span, look for a parent <a> or a sibling <a>
                            link_tag = title_element.find_parent('a')
                        
                        if not link_tag: # Fallback: try finding any link in the h2
                            h2_jobtitle = card_soup.select_one('h2.jobTitle')
                            if h2_jobtitle:
                                link_tag = h2_jobtitle.find('a')

                        if link_tag and link_tag.get('href'):
                            relative_job_url = link_tag['href']
                            if not relative_job_url.startswith('http'):
                                job_data['source_url'] = base_url + relative_job_url
                            else:
                                job_data['source_url'] = relative_job_url
                        else: # Fallback if specific link not found, try the card's main link
                            main_card_link = card_soup.find('a', attrs={'data-jk': True})
                            if main_card_link and main_card_link.get('href'):
                                relative_job_url = main_card_link['href']
                                if not relative_job_url.startswith('http'):
                                    job_data['source_url'] = base_url + relative_job_url
                                else:
                                    job_data['source_url'] = relative_job_url
                    
                    company_element = card_soup.select_one('[data-testid="company-name"]')
                    if company_element:
                        job_data['company'] = company_element.get_text(strip=True)

                    location_element = card_soup.select_one('[data-testid="text-location"]')
                    if location_element:
                        job_data['location'] = location_element.get_text(strip=True)

                    date_element = card_soup.select_one('span.date')
                    if date_element:
                        job_data['date_posted'] = date_element.get_text(strip=True).replace('Posted', '').strip()

                except Exception as e_parse:
                    logging.error(f"Error parsing a job card: {e_parse} Card HTML: {card_soup.prettify()[:200]}")
                    continue # Skip this card

                if job_data['source_url']:
                    logging.info(f"Fetching description for: {job_data.get('job_title', 'N/A')} ({job_data['source_url']})")
                    time.sleep(random.uniform(1, 2)) # Shorter delay as page navigation is slower
                    job_data['description'] = get_job_description_selenium(driver, job_data['source_url'])
                else:
                    logging.warning(f"Could not find source URL for a job card. Title: {job_data.get('job_title', 'N/A')}")
                    continue

                if job_data['job_title'] and job_data['company'] and job_data['description']:
                    if insert_job_posting(job_data):
                        jobs_collected += 1
                else:
                    logging.warning(f"Skipped a job due to missing critical data: Title={job_data.get('job_title')}, Company={job_data.get('company')}, Desc found={job_data.get('description') is not None and not job_data.get('description').startswith('Description not found')}")
                
                time.sleep(random.uniform(0.5, 1.0)) # Shorter delay between processing cards as page loads are slow

            logging.info(f"Finished processing page {page + 1}. Sleeping before next page...")
            time.sleep(random.uniform(3, 6)) # Delay before fetching the next search results page

    except Exception as e_main:
        logging.error(f"An unexpected error occurred in the main scraping loop: {e_main}", exc_info=True)
    finally:
        if driver:
            logging.info("Closing WebDriver.")
            driver.quit()
        logging.info(f"Scraping complete. Collected {jobs_collected} job postings.")

if __name__ == '__main__':
    init_db()
    logging.info(f"Starting job scraping for '{JOB_TITLE}' in '{LOCATION}' using Selenium.")
    scrape_indeed_selenium(JOB_TITLE, LOCATION, pages_to_scrape=1) # Start with 1 page for testing
    logging.info("Script finished.")

    # --- Future Scalability & Integration Notes ---
    # 1. CLI Integration:
    #    - Use `argparse` module to accept job_title, location, pages_to_scrape from command line.
    #    - Example: python job_scraper.py --title "Data Scientist" --location "Remote" --pages 5
    # 2. Streamlit Integration:
    #    - The `scrape_indeed_selenium` function could be called from a Streamlit app.
    #    - Input fields in Streamlit UI for job_title, location.
    #    - Display scraped data in a table or use for further analysis within Streamlit.
    #    - Need to manage state and potentially run scraping in a separate thread to avoid UI blocking.
    # 3. Robustness:
    #    - Implement more sophisticated error handling and retries.
    #    - Use a proxy service (e.g., ScraperAPI, Zyte Smart Proxy Manager) or rotate user agents/IPs
    #      if Indeed starts blocking requests (especially for larger scale scraping).
    #    - Regularly check and update CSS selectors as website structure can change.
    # 4. Advanced Filtering (e.g., JOB_TYPE):
    #    - Indeed's URL parameters for job type are not as straightforward as 'q' and 'l'.
    #    - It might require using their advanced search and constructing URLs like:
    #      `&sc=0kf%3Ajt(fulltime)%3B` for full-time.
    #    - This would need to be added to the `search_url` construction.
    # 5. NLP Preprocessing:
    #    - The 'description' field is raw text. Subsequent NLP steps would involve cleaning this text
    #      (removing HTML remnants if any, special characters, stop words) before skill extraction.
    # --- End Scalability & Integration Notes --- 