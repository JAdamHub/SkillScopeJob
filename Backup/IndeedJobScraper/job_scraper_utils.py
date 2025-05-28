import os
import sqlite3
import time
import random

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager


global total_jobs


def init_db(db_name="indeed_jobs.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_postings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE,
            job_title TEXT,
            company TEXT,
            employer_active TEXT,
            location TEXT,
            country_url TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print(f"Database '{db_name}' initialized and 'job_postings' table ensured.")


def configure_webdriver():
    options = webdriver.ChromeOptions()
    # Remove headless mode to better handle Cloudflare
    # options.add_argument("--headless")
    options.add_argument("start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=9222")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Add user agent to appear more human-like
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )

    return driver


def handle_cloudflare_verification(driver, max_retries=3):
    """
    Enhanced Cloudflare verification handler that detects multiple types of verification screens.
    """
    for attempt in range(max_retries):
        try:
            print(f"Checking for Cloudflare verification (attempt {attempt + 1}/{max_retries})...")
            
            # Check for various Cloudflare verification indicators
            verification_selectors = [
                '//button[contains(text(), "Verify")]',
                '//button[contains(text(), "verify")]',
                '//input[@type="button" and contains(@value, "Verify")]',
                '//div[contains(text(), "Additional Verification Required")]',
                '//div[contains(text(), "verification")]//following::button',
                '//div[@class="cf-browser-verification"]',
                '//div[contains(@class, "cf-challenge")]',
                '//*[contains(text(), "Checking if the site connection is secure")]'
            ]
            
            verification_detected = False
            verify_button = None
            
            # Try to find verification elements
            for selector in verification_selectors:
                try:
                    element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if 'button' in selector.lower() or element.tag_name == 'button':
                        verify_button = element
                    verification_detected = True
                    print(f"Cloudflare verification detected with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not verification_detected:
                print("No Cloudflare verification screen detected.")
                return True
            
            # If we found a verify button, click it
            if verify_button and verify_button.is_enabled():
                print("Clicking 'Verify' button...")
                driver.execute_script("arguments[0].click();", verify_button)
                
                # Wait for verification to complete
                print("Waiting for verification to complete...")
                time.sleep(random.uniform(3, 7))
                
                # Wait for the page to reload and check if Indeed content is loaded
                try:
                    WebDriverWait(driver, 20).until(
                        lambda d: any([
                            d.find_elements(By.CLASS_NAME, 'jobsearch'),
                            d.find_elements(By.CLASS_NAME, 'job_seen_beacon'),
                            d.find_elements(By.XPATH, '//div[contains(@class, "jobsearch")]'),
                            'indeed.com' in d.current_url and 'cf-browser-verification' not in d.page_source
                        ])
                    )
                    print("Cloudflare verification completed successfully.")
                    return True
                except TimeoutException:
                    print(f"Verification may not have completed properly on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(5, 10))
                        continue
            else:
                print("Verification screen detected but no clickable verify button found.")
                # Wait and see if it auto-resolves
                time.sleep(random.uniform(5, 10))
                
        except Exception as e:
            print(f"Error during Cloudflare verification attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(3, 8))
                continue
    
    print("Cloudflare verification handling completed (may not have been successful)")
    return False


def search_jobs(driver, country, job_position, job_location, date_posted):
    full_url = f'{country}/jobs?q={"+".join(job_position.split())}&l={job_location}&fromage={date_posted}'
    print(full_url)
    driver.get(full_url)
    
    # Add initial wait for page load
    time.sleep(random.uniform(2, 5))
    
    # Handle Cloudflare verification if it appears
    verification_success = handle_cloudflare_verification(driver)
    
    if not verification_success:
        print("Warning: Cloudflare verification may not have completed successfully")
    
    # Additional wait after verification
    time.sleep(random.uniform(2, 4))
    
    global total_jobs
    try:
        # Try multiple selectors for job count
        job_count_selectors = [
            '//div[starts-with(@class, "jobsearch-JobCountAndSortPane-jobCount")]',
            '//div[contains(@class, "jobsearch-JobCountAndSortPane")]//span',
            '//div[contains(text(), "jobs")]'
        ]
        
        job_count_element = None
        for selector in job_count_selectors:
            try:
                job_count_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                break
            except TimeoutException:
                continue
        
        if job_count_element:
            try:
                total_jobs = job_count_element.find_element(By.XPATH, './span').text
            except NoSuchElementException:
                total_jobs = job_count_element.text
            print(f"{total_jobs} found")
        else:
            raise NoSuchElementException("No job count element found")
            
    except NoSuchElementException:
        print("No job count found")
        total_jobs = "Unknown"

    driver.save_screenshot('screenshot.png')
    return full_url


def scrape_job_data(driver, country_url, db_name="indeed_jobs.db"):
    job_count = 0
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    while True:
        # Handle Cloudflare verification if it appears during pagination
        handle_cloudflare_verification(driver)
        
        # Add random delay to appear more human-like
        time.sleep(random.uniform(1, 3))
        
        soup = BeautifulSoup(driver.page_source, 'lxml')
        boxes = soup.find_all('div', class_='job_seen_beacon')

        if not boxes:
            print("No job boxes found on the current page.")
            
        for i in boxes:
            try:
                link = i.find('a', {'data-jk': True}).get('href')
                link_full = country_url + link
            except (AttributeError, TypeError):
                try:
                    link = i.find('a', class_=lambda x: x and 'JobTitle' in x).get('href')
                    link_full = country_url + link
                except (AttributeError, TypeError):
                    link_full = None

            try:
                job_title = i.find('a', class_=lambda x: x and 'JobTitle' in x).text.strip()
            except AttributeError:
                try:
                    job_title = i.find('span', id=lambda x: x and 'jobTitle-' in str(x)).text.strip()
                except AttributeError:
                    job_title = None

            try:
                company = i.find('span', {'data-testid': 'company-name'}).text.strip()
            except AttributeError:
                try:
                    company = i.find('span', class_=lambda x: x and 'company' in str(x).lower()).text.strip()
                except AttributeError:
                    company = None

            try:
                employer_active = i.find('span', class_='date').text.strip()
            except AttributeError:
                try:
                    employer_active = i.find('span', {'data-testid': 'myJobsStateDate'}).text.strip()
                except AttributeError:
                    employer_active = None
            
            try:
                location_element = i.find('div', {'data-testid': 'text-location'})
                if location_element:
                    try:
                        location = location_element.find('span').text.strip()
                    except AttributeError:
                        location = location_element.text.strip()
                else:
                    raise AttributeError
            except AttributeError:
                try:
                    location_element = i.find('div', class_=lambda x: x and 'location' in str(x).lower())
                    if location_element:
                        try:
                            location = location_element.find('span').text.strip()
                        except AttributeError:
                            location = location_element.text.strip()
                    else:
                        location = ''
                except AttributeError:
                    location = ''


            if link_full and job_title:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO job_postings 
                        (link, job_title, company, employer_active, location, country_url) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (link_full, job_title, company, employer_active, location, country_url))
                    if cursor.rowcount > 0:
                        job_count += 1
                except sqlite3.Error as e:
                    print(f"SQLite error when inserting job: {e} - Data: {link_full}, {job_title}")
            
        conn.commit()
        print(f"Scraped {job_count} jobs so far in this session of {total_jobs} reported.")

        try:
            next_page_link_element = soup.find('a', {'aria-label': 'Next Page'})
            if next_page_link_element:
                next_page_href = next_page_link_element.get('href')
                if next_page_href:
                    next_page_url = country_url + next_page_href
                    driver.get(next_page_url)
                else:
                    print("Next page link found, but no href. Ending pagination.")
                    break 
            else:
                print("No 'Next Page' link found. Assuming end of results.")
                break
        except Exception as e:
            print(f"Error navigating to next page: {e}")
            break
            
    conn.close()
    return job_count
