import os
import sqlite3

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
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
    options.add_argument("--headless")
    options.add_argument("start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
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


def search_jobs(driver, country, job_position, job_location, date_posted):
    full_url = f'{country}/jobs?q={"+".join(job_position.split())}&l={job_location}&fromage={date_posted}'
    print(full_url)
    driver.get(full_url)
    global total_jobs
    try:
        job_count_element = driver.find_element(By.XPATH,
                                                '//div[starts-with(@class, "jobsearch-JobCountAndSortPane-jobCount")]')
        total_jobs = job_count_element.find_element(By.XPATH, './span').text
        print(f"{total_jobs} found")
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
