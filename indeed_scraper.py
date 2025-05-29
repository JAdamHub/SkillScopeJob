import sqlite3
import logging
import pandas as pd
from typing import List
from jobspy import scrape_jobs

# configuration parameters
JOB_TITLES = [
    "key account manager",
    "project manager", 
    "business analyst",
    "marketing manager",
    "data analyst"
]

LOCATION = "copenhagen, denmark"
RESULTS_WANTED = 100  # per job title
HOURS_OLD = 168  # 1 week
COUNTRY = "denmark"

# database setup
DB_NAME = 'indeed_jobs.db'
TABLE_NAME = 'job_postings'

# logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('indeed_scraper.log'),
        logging.StreamHandler()
    ]
)

def init_database():
    """initialize sqlite database with indeed-focused job posting schema."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        company TEXT,
        company_url TEXT,
        job_url TEXT UNIQUE,
        location TEXT,
        is_remote BOOLEAN,
        job_type TEXT,
        description TEXT,
        date_posted DATE,
        company_industry TEXT,
        company_description TEXT,
        company_logo TEXT,
        scraped_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        search_term TEXT,
        search_location TEXT
    )
    """)
    
    conn.commit()
    conn.close()
    logging.info(f"database '{DB_NAME}' initialized with table '{TABLE_NAME}'")

def convert_dataframe_to_records(df: pd.DataFrame, search_term: str, search_location: str) -> List[dict]:
    """convert indeed dataframe to database records."""
    records = []
    
    for _, row in df.iterrows():
        try:
            # basic job information
            record = {
                'title': row.get('title', ''),
                'company': row.get('company', ''),
                'company_url': row.get('company_url', ''),
                'job_url': row.get('job_url', ''),
                'description': row.get('description', ''),
                'job_type': row.get('job_type', ''),
                'is_remote': bool(row.get('is_remote', False)),
                'date_posted': row.get('date_posted', None),
                'search_term': search_term,
                'search_location': search_location
            }
            
            # location information - handle as string (København, D84, DK format)
            location_data = row.get('location', '')
            if location_data:
                record['location'] = str(location_data).strip()
            else:
                record['location'] = ''
            
            # indeed specific fields (only ones that typically have data)
            record['company_industry'] = row.get('company_industry', '')
            record['company_description'] = row.get('company_description', '')
            record['company_logo'] = row.get('company_logo', '')
            
            records.append(record)
            
        except Exception as e:
            logging.error(f"error processing row: {e}")
            continue
    
    return records

def insert_job_records(records: List[dict]) -> int:
    """insert job records into database and return count of new records."""
    if not records:
        return 0
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    inserted_count = 0
    
    for record in records:
        try:
            cursor.execute(f"""
            INSERT OR IGNORE INTO {TABLE_NAME} (
                title, company, company_url, job_url, location,
                is_remote, job_type, description, date_posted, company_industry,
                company_description, company_logo, search_term, search_location
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """, (
                record['title'], record['company'], record['company_url'],
                record['job_url'], record['location'], record['is_remote'], 
                record['job_type'], record['description'], record['date_posted'],
                record['company_industry'], record['company_description'], 
                record['company_logo'], record['search_term'], record['search_location']
            ))
            
            if cursor.rowcount > 0:
                inserted_count += 1
                logging.info(f"inserted: {record['title']} at {record['company']}")
            
        except sqlite3.Error as e:
            logging.error(f"database error inserting record: {e}")
        except Exception as e:
            logging.error(f"unexpected error inserting record: {e}")
    
    conn.commit()
    conn.close()
    
    return inserted_count

def scrape_indeed_jobs(search_term: str, location: str) -> int:
    """scrape jobs from indeed and save to database."""
    
    logging.info(f"starting indeed job scrape for '{search_term}' in '{location}'")
    
    try:
        # scrape jobs using jobspy - indeed only
        jobs_df = scrape_jobs(
            site_name=["indeed"],
            search_term=search_term,
            location=location,
            results_wanted=RESULTS_WANTED,
            hours_old=HOURS_OLD,
            country_indeed=COUNTRY,
            verbose=1,
            description_format="markdown"
        )
        
        logging.info(f"scraped {len(jobs_df)} jobs from indeed")
        
        if jobs_df.empty:
            logging.warning("no jobs found")
            return 0
        
        # log description statistics
        jobs_with_descriptions = 0
        for _, row in jobs_df.iterrows():
            desc = row.get('description', '')
            if desc and desc != '':
                jobs_with_descriptions += 1
        
        logging.info(f"jobs with descriptions: {jobs_with_descriptions}/{len(jobs_df)}")
        
        # convert to database records
        records = convert_dataframe_to_records(jobs_df, search_term, location)
        logging.info(f"converted {len(records)} records for database insertion")
        
        if not records:
            logging.error("no records created from dataframe")
            return 0
        
        # insert into database
        inserted_count = insert_job_records(records)
        logging.info(f"successfully inserted {inserted_count} new job postings")
        
        return inserted_count
        
    except Exception as e:
        logging.error(f"error during job scraping: {e}")
        return 0

def test_database_connection():
    """test database connection and table creation."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # test table exists
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE_NAME}';")
        table_exists = cursor.fetchone()
        
        if table_exists:
            logging.info(f"table '{TABLE_NAME}' exists in database")
            
            # count existing records
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            count = cursor.fetchone()[0]
            logging.info(f"current record count: {count}")
        else:
            logging.error(f"table '{TABLE_NAME}' does not exist!")
        
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"database connection test failed: {e}")
        return False

def get_database_stats():
    """get statistics about jobs in database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        total_jobs = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE date(scraped_timestamp) = date('now')")
        today_jobs = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE description IS NOT NULL AND description != ''")
        jobs_with_descriptions = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE location IS NOT NULL AND location != ''")
        jobs_with_location = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT AVG(LENGTH(description)) FROM {TABLE_NAME} WHERE description IS NOT NULL AND description != ''")
        avg_desc_length = cursor.fetchone()[0]
        
        logging.info(f"database statistics:")
        logging.info(f"  total jobs: {total_jobs}")
        logging.info(f"  jobs scraped today: {today_jobs}")
        logging.info(f"  jobs with descriptions: {jobs_with_descriptions}/{total_jobs}")
        logging.info(f"  jobs with location: {jobs_with_location}/{total_jobs}")
        if avg_desc_length:
            logging.info(f"  average description length: {avg_desc_length:.0f} characters")
            
    except sqlite3.Error as e:
        logging.error(f"error getting database stats: {e}")
    finally:
        conn.close()

def check_description_quality():
    """check and report on description quality in database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # get sample descriptions for quality check
        cursor.execute(f"""
        SELECT title, company, location, LENGTH(description) as desc_length, 
               SUBSTR(description, 1, 100) as desc_sample
        FROM {TABLE_NAME} 
        WHERE description IS NOT NULL AND description != ''
        ORDER BY desc_length DESC
        LIMIT 10
        """)
        
        samples = cursor.fetchall()
        
        logging.info("=== description quality samples ===")
        for title, company, location, length, sample in samples:
            logging.info(f"{title} at {company} ({location})")
            logging.info(f"  length: {length} chars")
            logging.info(f"  sample: {sample}...")
            logging.info("")
            
    except sqlite3.Error as e:
        logging.error(f"error checking description quality: {e}")
    finally:
        conn.close()

def main():
    """main execution function."""
    logging.info("starting indeed job scraper with multiple job titles")
    
    # initialize database
    init_database()
    
    # test database connection
    if not test_database_connection():
        logging.error("database test failed - exiting")
        return
    
    total_inserted_all = 0
    
    # scrape jobs for each job title
    for job_title in JOB_TITLES:
        logging.info(f"=== searching for: {job_title} ===")
        
        try:
            inserted = scrape_indeed_jobs(job_title, LOCATION)
            total_inserted_all += inserted
            logging.info(f"inserted {inserted} jobs for '{job_title}'")
            
            # small delay between searches to be respectful
            import time
            time.sleep(2)
            
        except Exception as e:
            logging.error(f"error searching for '{job_title}': {e}")
            continue
    
    # show final statistics
    logging.info(f"=== all searches completed ===")
    logging.info(f"total new jobs inserted across all titles: {total_inserted_all}")
    get_database_stats()
    
    if total_inserted_all > 0:
        check_description_quality()
    
    logging.info("indeed scraper finished")

if __name__ == "__main__":
    main()
