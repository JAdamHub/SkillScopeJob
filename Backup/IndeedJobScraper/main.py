from dotenv import load_dotenv
from job_scraper_utils import configure_webdriver, search_jobs, scrape_job_data, init_db
import os
import time
import random

load_dotenv()

"""
List of countries url.
"""
nigeria = 'https://ng.indeed.com'
united_kingdom = 'https://uk.indeed.com'
united_states = 'https://www.indeed.com'
canada = 'https://ca.indeed.com'
denmark = 'https://dk.indeed.com'
germany = 'https://de.indeed.com'
australia = 'https://au.indeed.com'
south_africa = 'https://za.indeed.com'
sweden = 'https://se.indeed.com'
singapore = 'https://www.indeed.com.sg'
switzerland = 'https://www.indeed.ch'
united_arab_emirates = 'https://www.indeed.ae'
new_zealand = 'https://nz.indeed.com'
india = 'https://www.indeed.co.in'
france = 'https://www.indeed.fr'
italy = 'https://it.indeed.com'
spain = 'https://www.indeed.es'
japan = 'https://jp.indeed.com'
south_korea = 'https://kr.indeed.com'
brazil = 'https://www.indeed.com.br'
mexico = 'https://www.indeed.com.mx'
china = 'https://cn.indeed.com'
saudi_arabia = 'https://sa.indeed.com'
egypt = 'https://eg.indeed.com'
thailand = 'https://th.indeed.com'
vietnam = 'https://vn.indeed.com'
argentina = 'https://ar.indeed.com'
ireland = 'https://ie.indeed.com'

def main():
    db_name = "indeed_jobs.db"
    init_db(db_name)

    driver = configure_webdriver()
    
    country_url = 'https://dk.indeed.com'
    job_position = 'software engineer'
    job_location = 'Copenhagen'
    date_posted = 7

    print(f"Starting job scrape for '{job_position}' in '{job_location if job_location else country_url}' for jobs posted within {date_posted} days.")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"Scraping attempt {attempt + 1}/{max_retries}")
            
            full_search_url = search_jobs(driver, country_url, job_position, job_location, date_posted)
            print(f"Searching at URL: {full_search_url}")

            # Check if we're still on a Cloudflare page
            if 'cf-browser-verification' in driver.page_source or 'Additional Verification Required' in driver.page_source:
                print("Still on Cloudflare verification page, retrying...")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(10, 20))
                    continue
                else:
                    print("Failed to bypass Cloudflare after all attempts")
                    break

            new_jobs_count = scrape_job_data(driver, country_url, db_name=db_name)

            if new_jobs_count > 0:
                print(f"Successfully scraped and stored {new_jobs_count} new job postings.")
            else:
                print("No new job postings were found or added to the database for the given criteria.")
            
            break  # Success, exit retry loop

        except Exception as e:
            print(f"An error occurred during scraping attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                print("Retrying...")
                time.sleep(random.uniform(5, 15))
            else:
                print("All retry attempts failed.")
                import traceback
                traceback.print_exc()
    
    finally:
        if 'driver' in locals() and driver is not None:
            print("Quitting webdriver.")
            driver.quit()
        print("Scraping process finished.")

if __name__ == "__main__":
    main()
