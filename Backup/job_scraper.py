import sqlite3
import logging
import time
import random
from bs4 import BeautifulSoup

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

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
        INSERT OR IGNORE INTO {TABLE_NAME} (job_title, company, location, date_posted, employment_type, description, source_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (job_data['job_title'], job_data['company'], job_data['location'],
              job_data['date_posted'], job_data['employment_type'], job_data['description'], job_data['source_url']))
        conn.commit()
        if cursor.rowcount > 0:
            logging.info(f"Inserted job: {job_data['job_title']} at {job_data['company']}")
            return True
        else:
            logging.debug(f"Job already exists: {job_data['source_url']}")
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
    """Sets up the Undetected Chrome WebDriver with enhanced stealth capabilities."""
    options = uc.ChromeOptions()
    
    # Keep browser visible for manual intervention if needed
    # options.add_argument("--headless")  # Commented out for visibility
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Add realistic user agent
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        # Use undetected-chromedriver instead of regular selenium
        driver = uc.Chrome(
            options=options,
            use_subprocess=False,  # Better for avoiding detection
            version_main=None  # Auto-detect Chrome version
        )
        
        logging.info("Undetected ChromeDriver setup successful")
        return driver
        
    except Exception as e:
        logging.error(f"Failed to setup Undetected ChromeDriver: {e}")
        logging.error("Please ensure Google Chrome is installed and accessible.")
        return None

def handle_cloudflare_verification(driver, max_retries=3):
    """Enhanced Cloudflare verification handler that specifically handles Turnstile challenges."""
    for attempt in range(max_retries):
        try:
            logging.info(f"Checking for Cloudflare verification (attempt {attempt + 1}/{max_retries})...")
            
            # Wait for undetected-chromedriver to handle verification automatically
            initial_wait = random.uniform(8, 12)
            logging.info(f"Waiting {initial_wait:.1f} seconds for automatic verification...")
            time.sleep(initial_wait)
            
            # Get current page source for analysis
            page_source = driver.page_source
            page_source_lower = page_source.lower()
            
            # Check for Cloudflare Turnstile challenge specifically
            turnstile_indicators = [
                'cf-turnstile-response',
                'waiting for dk.indeed.com to respond',
                'challenge-error-text',
                'enable javascript and cookies to continue',
                'main-wrapper" role="main"',
                'lds-ring'  # The loading ring animation
            ]
            
            # Check for general Cloudflare indicators
            general_cloudflare_indicators = [
                'checking if the site connection is secure',
                'cf-browser-verification',
                'cf-challenge',
                'ddos protection by cloudflare',
                'challenge platform by cloudflare',
                'please wait while we verify',
                'verifying you are human'
            ]
            
            # Detect if we're in a Turnstile challenge
            turnstile_detected = any(indicator in page_source_lower for indicator in turnstile_indicators)
            general_cf_detected = any(indicator in page_source_lower for indicator in general_cloudflare_indicators)
            
            if turnstile_detected:
                logging.info(f"Cloudflare Turnstile challenge detected on attempt {attempt + 1}")
                
                # Look for the specific waiting message
                if 'waiting for dk.indeed.com to respond' in page_source_lower:
                    logging.info("Detected 'Waiting for dk.indeed.com to respond' message")
                
                # For Turnstile, we need to wait longer as it's more sophisticated
                extended_wait = random.uniform(20, 35)
                logging.info(f"Extended wait of {extended_wait:.1f} seconds for Turnstile challenge resolution...")
                time.sleep(extended_wait)
                
                # Check if challenge is resolved by looking for Indeed content
                page_source = driver.page_source
                page_source_lower = page_source.lower()
                
                # Check if Turnstile indicators are still present
                if any(indicator in page_source_lower for indicator in turnstile_indicators):
                    logging.warning(f"Turnstile challenge still active after extended wait on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        logging.info("Refreshing page and trying again...")
                        driver.refresh()
                        time.sleep(random.uniform(5, 10))
                        continue
                else:
                    logging.info("Turnstile challenge appears to be resolved")
                    
            elif general_cf_detected:
                logging.info(f"General Cloudflare challenge detected on attempt {attempt + 1}")
                
                # Standard wait for general Cloudflare challenges
                extended_wait = random.uniform(15, 25)
                logging.info(f"Extended wait of {extended_wait:.1f} seconds for challenge resolution...")
                time.sleep(extended_wait)
                
                page_source_lower = driver.page_source.lower()
                if any(indicator in page_source_lower for indicator in general_cloudflare_indicators):
                    logging.warning(f"Cloudflare still active after extended wait on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        logging.info("Refreshing page and trying again...")
                        driver.refresh()
                        time.sleep(random.uniform(5, 8))
                        continue
                else:
                    logging.info("Cloudflare indicators no longer detected")
            
            # Verify that we're actually on Indeed and it's functional
            logging.info("Verifying that Indeed content is actually functional...")
            
            # Test 1: Check for Indeed URL
            current_url = driver.current_url.lower()
            if 'indeed.com' not in current_url:
                logging.warning(f"Not on Indeed domain. Current URL: {driver.current_url}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(3, 5))
                    continue
                else:
                    return False
            
            # Test 2: Try to find functional Indeed elements
            functional_indeed_found = False
            try:
                # Wait for actual functional elements with longer timeout for post-Turnstile loading
                WebDriverWait(driver, 15).until(
                    lambda d: any([
                        d.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon"),
                        d.find_elements(By.CSS_SELECTOR, "div.jobsearch-SerpJobCard"),
                        d.find_elements(By.CSS_SELECTOR, "[data-testid='company-name']"),
                        d.find_elements(By.CSS_SELECTOR, "h2.jobTitle"),
                        d.find_elements(By.CSS_SELECTOR, "div.jobsearch-JobCountAndSortPane"),
                        d.find_elements(By.CSS_SELECTOR, "div.jobsearch")
                    ])
                )
                functional_indeed_found = True
                logging.info("Functional Indeed elements detected")
            except TimeoutException:
                logging.warning("No functional Indeed elements found within timeout")
                
                # Fallback: Check if we at least have basic Indeed page structure
                indeed_structure_indicators = [
                    'jobsearch', 'job_seen_beacon', 'jobtitle', 'jobcountandsortpane'
                ]
                page_source_lower = driver.page_source.lower()
                if any(indicator in page_source_lower for indicator in indeed_structure_indicators):
                    logging.info("Basic Indeed page structure detected in source")
                    functional_indeed_found = True
                else:
                    logging.warning("No Indeed page structure detected")
            
            # Test 3: Final validation - check page isn't showing error/blocking messages
            blocking_indicators = [
                'access denied', 'blocked', 'forbidden', 'captcha required',
                'unusual traffic', 'automated queries', 'please verify',
                'cf-turnstile-response'  # Still showing Turnstile elements
            ]
            
            page_source_lower = driver.page_source.lower()
            if any(indicator in page_source_lower for indicator in blocking_indicators):
                logging.warning("Blocking indicators still present in page")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(5, 10))
                    continue
                else:
                    return False
            
            # Only return success if we have functional Indeed content and no blocking
            if functional_indeed_found:
                logging.info("Verification appears successful - functional Indeed content confirmed")
                return True
            else:
                logging.warning("Verification status unclear - Indeed content not confirmed as functional")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(5, 8))
                    continue
                
        except Exception as e:
            logging.warning(f"Error during Cloudflare check attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(5, 8))
                continue
    
    # Final conservative check
    try:
        logging.info("Performing final verification check...")
        
        current_url = driver.current_url.lower()
        page_source_lower = driver.page_source.lower()
        
        # Must be on Indeed domain
        if 'indeed.com' not in current_url:
            logging.error("Final check failed: Not on Indeed domain")
            return False
        
        # Must not have Cloudflare/Turnstile indicators
        challenge_still_present = any(indicator in page_source_lower for indicator in [
            'checking if the site connection is secure',
            'cf-browser-verification',
            'cf-challenge',
            'cf-turnstile-response',
            'waiting for dk.indeed.com to respond'
        ])
        
        if challenge_still_present:
            logging.error("Final check failed: Challenge indicators still present")
            return False
        
        # Should have some Indeed content
        has_indeed_content = any(indicator in page_source_lower for indicator in [
            'jobsearch', 'job_seen_beacon', 'jobtitle'
        ])
        
        if has_indeed_content:
            logging.info("Final verification passed - page appears ready")
            return True
        else:
            logging.warning("Final verification uncertain - limited Indeed content detected")
            return False
            
    except Exception as e:
        logging.error(f"Error in final verification check: {e}")
        return False

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
            
            # Retry mechanism for page loading
            page_load_success = False
            for load_attempt in range(3):
                try:
                    logging.info(f"Loading page (attempt {load_attempt + 1}/3)...")
                    driver.get(search_url)
                    
                    # Initial wait for page load
                    time.sleep(random.uniform(3, 6))
                    
                    # Handle Cloudflare verification passively
                    verification_success = handle_cloudflare_verification(driver)
                    if verification_success:
                        page_load_success = True
                        break
                    else:
                        logging.warning(f"Page load attempt {load_attempt + 1} may not have succeeded")
                        if load_attempt < 2:
                            logging.info("Retrying page load...")
                            time.sleep(random.uniform(5, 8))
                            continue
                        
                except Exception as e:
                    logging.error(f"Error during page load attempt {load_attempt + 1}: {e}")
                    if load_attempt < 2:
                        time.sleep(random.uniform(5, 8))
                        continue
            
            if not page_load_success:
                logging.error(f"Failed to load page {page + 1} after multiple attempts. Skipping.")
                continue
            
            # Minimal manual intervention time since we're letting undetected-chromedriver handle everything
            logging.info("Brief pause for any final loading...")
            time.sleep(random.uniform(2, 4))
            
            try_handle_popups(driver)

            try:
                # Wait for job cards with shorter timeout since page should be loaded
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.job_seen_beacon, div.jobsearch-SerpJobCard"))
                )
                time.sleep(random.uniform(1, 2))

            except TimeoutException:
                logging.error(f"Timeout waiting for job cards on page {page + 1}. URL: {search_url}")
                logging.info("Checking page source for debugging...")
                page_source_snippet = driver.page_source[:500].lower()
                logging.info(f"Page source snippet: {page_source_snippet}")
                
                if any(indicator in page_source_snippet for indicator in ['blocked', 'captcha', 'verification', 'challenge']):
                    logging.warning("Possible blocking or challenge detected in page source")
                continue

            # Use BeautifulSoup to parse the page source obtained from Selenium
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            job_cards = soup.select("div.job_seen_beacon, div.jobsearch-SerpJobCard")

            if not job_cards:
                logging.info(f"No job cards parsed by BeautifulSoup on page {page + 1}. URL: {search_url}")
                continue

            for card_soup in job_cards:
                job_data = {
                    'job_title': None, 'company': None, 'location': None,
                    'date_posted': None, 'employment_type': 'Not Specified',
                    'description': None, 'source_url': None
                }

                try:
                    # Enhanced job title extraction with multiple fallbacks
                    title_element = card_soup.select_one('h2.jobTitle a, h2.jobTitle span')
                    if not title_element:
                        title_element = card_soup.find('span', id=lambda x: x and 'jobTitle-' in str(x))
                    
                    if title_element:
                        job_data['job_title'] = title_element.get_text(strip=True)
                        
                        # Enhanced link extraction
                        link_tag = None
                        if title_element.name == 'a':
                            link_tag = title_element
                        else:
                            link_tag = title_element.find_parent('a')
                        
                        if not link_tag:
                            h2_jobtitle = card_soup.select_one('h2.jobTitle')
                            if h2_jobtitle:
                                link_tag = h2_jobtitle.find('a')
                        
                        if not link_tag:
                            link_tag = card_soup.find('a', {'data-jk': True})

                        if link_tag and link_tag.get('href'):
                            relative_job_url = link_tag['href']
                            if not relative_job_url.startswith('http'):
                                job_data['source_url'] = base_url + relative_job_url
                            else:
                                job_data['source_url'] = relative_job_url
                    
                    # Enhanced company extraction with fallbacks
                    company_element = card_soup.select_one('[data-testid="company-name"]')
                    if not company_element:
                        company_element = card_soup.find('span', class_=lambda x: x and 'company' in str(x).lower())
                    if company_element:
                        job_data['company'] = company_element.get_text(strip=True)

                    # Enhanced location extraction with fallbacks
                    location_element = card_soup.select_one('[data-testid="text-location"]')
                    if not location_element:
                        location_element = card_soup.find('div', {'data-testid': 'text-location'})
                        if location_element:
                            span_element = location_element.find('span')
                            if span_element:
                                location_element = span_element
                    if not location_element:
                        location_element = card_soup.find('div', class_=lambda x: x and 'location' in str(x).lower())
                    if location_element:
                        job_data['location'] = location_element.get_text(strip=True)

                    # Enhanced date extraction with fallbacks
                    date_element = card_soup.select_one('span.date')
                    if not date_element:
                        date_element = card_soup.find('span', {'data-testid': 'myJobsStateDate'})
                    if date_element:
                        job_data['date_posted'] = date_element.get_text(strip=True).replace('Posted', '').strip()

                except Exception as e_parse:
                    logging.error(f"Error parsing a job card: {e_parse}")
                    continue

                if job_data['source_url']:
                    logging.info(f"Fetching description for: {job_data.get('job_title', 'N/A')} ({job_data['source_url']})")
                    time.sleep(random.uniform(1, 2))
                    job_data['description'] = get_job_description_selenium(driver, job_data['source_url'])
                else:
                    logging.warning(f"Could not find source URL for a job card. Title: {job_data.get('job_title', 'N/A')}")
                    continue

                if job_data['job_title'] and job_data['company'] and job_data['description']:
                    if insert_job_posting(job_data):
                        jobs_collected += 1
                else:
                    logging.warning(f"Skipped a job due to missing critical data: Title={job_data.get('job_title')}, Company={job_data.get('company')}, Desc found={job_data.get('description') is not None and not job_data.get('description').startswith('Description not found')}")

                time.sleep(random.uniform(0.5, 1.0))

            # Check for next page and navigate
            try:
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                next_page_link_element = soup.find('a', {'aria-label': 'Next Page'})
                if next_page_link_element and page < pages_to_scrape - 1:
                    next_page_href = next_page_link_element.get('href')
                    if next_page_href:
                        next_page_url = base_url + next_page_href
                        logging.info(f"Navigating to next page: {next_page_url}")
                        driver.get(next_page_url)
                        time.sleep(random.uniform(3, 6))
            except Exception as e:
                logging.warning(f"Error checking for next page: {e}")

            logging.info(f"Finished processing page {page + 1}. Sleeping before next page...")
            time.sleep(random.uniform(4, 8))  # Slightly longer delays with undetected-chromedriver

    except KeyboardInterrupt:
        logging.info("Scraping interrupted by user")
    except Exception as e_main:
        logging.error(f"An unexpected error occurred in the main scraping loop: {e_main}", exc_info=True)
    finally:
        try:
            if driver:
                logging.info("Closing WebDriver.")
                driver.quit()
        except Exception as e:
            logging.error(f"Error closing driver: {e}")
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