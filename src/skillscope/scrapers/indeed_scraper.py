import sqlite3
import logging
import pandas as pd
from typing import List, Dict
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
HOURS_OLD = 168  # 1 week - NOTE: this parameter may not be supported in current jobspy version
COUNTRY = "denmark"

# database setup
DB_NAME = 'data/databases/indeed_jobs.db'
TABLE_NAME = 'job_postings'

# logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/indeed_scraper.log'),
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
        search_location TEXT,
        search_job_type TEXT,
        search_is_remote BOOLEAN,
        job_status TEXT DEFAULT 'active',
        refresh_count INTEGER DEFAULT 1,
        job_freshness TEXT,
        enrichment_status TEXT,
        user_profile_match REAL
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
    updated_count = 0
    current_timestamp = pd.Timestamp.now().isoformat()
    
    for record in records:
        try:
            # First, try to insert the job record
            cursor.execute(f"""
            INSERT OR IGNORE INTO {TABLE_NAME} (
                title, company, company_url, job_url, location,
                is_remote, job_type, description, date_posted, company_industry,
                company_description, company_logo, search_term, search_location,
                scraped_timestamp, last_seen_timestamp
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """, (
                record['title'], record['company'], record['company_url'],
                record['job_url'], record['location'], record['is_remote'], 
                record['job_type'], record['description'], record['date_posted'],
                record['company_industry'], record['company_description'], 
                record['company_logo'], record['search_term'], record['search_location'],
                current_timestamp, current_timestamp
            ))
            
            if cursor.rowcount > 0:
                inserted_count += 1
                logging.info(f"✅ inserted new job: {record['title']} at {record['company']}")
            else:
                # Job already exists, update last_seen_timestamp
                cursor.execute(f"""
                UPDATE {TABLE_NAME} 
                SET last_seen_timestamp = ?, 
                    refresh_count = refresh_count + 1,
                    job_status = 'active'
                WHERE job_url = ?
                """, (current_timestamp, record['job_url']))
                
                if cursor.rowcount > 0:
                    updated_count += 1
                    logging.info(f"🔄 updated existing job: {record['title']} at {record['company']}")
            
        except sqlite3.Error as e:
            logging.error(f"database error inserting record: {e}")
        except Exception as e:
            logging.error(f"unexpected error inserting record: {e}")
    
    conn.commit()
    conn.close()
    
    logging.info(f"📊 Job insertion summary: {inserted_count} new jobs, {updated_count} existing jobs updated")
    return inserted_count

def scrape_indeed_jobs(search_term: str, location: str) -> int:
    """scrape jobs from indeed and save to database."""
    
    logging.info(f"starting indeed job scrape for '{search_term}' in '{location}'")
    
    try:
        # Build parameters dictionary to handle version differences
        scrape_params = {
            "site_name": ["indeed"],
            "search_term": search_term,
            "location": location,
            "results_wanted": RESULTS_WANTED,
            "country_indeed": COUNTRY,
            "verbose": 1,
            "description_format": "markdown"
        }
        
        # Try to add hours_old parameter, but handle if not supported
        try:
            jobs_df = scrape_jobs(**scrape_params, hours_old=HOURS_OLD)
        except TypeError as e:
            if "hours_old" in str(e):
                logging.warning("hours_old parameter not supported, scraping without time filter")
                jobs_df = scrape_jobs(**scrape_params)
            else:
                raise e
        
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

def check_existing_jobs_for_terms(search_terms: List[str], location: str = None) -> int:
    """Check how many jobs already exist in database for given search terms"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Build query to check for existing jobs matching the search terms
        conditions = []
        params = []
        
        for term in search_terms:
            conditions.append("LOWER(title) LIKE ? OR LOWER(search_term) LIKE ?")
            params.extend([f"%{term.lower()}%", f"%{term.lower()}%"])
        
        where_clause = " OR ".join(conditions)
        
        if location:
            where_clause += " AND (LOWER(location) LIKE ? OR LOWER(search_location) LIKE ?)"
            params.extend([f"%{location.lower()}%", f"%{location.lower()}%"])
        
        query = f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE {where_clause}"
        
        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        
        logging.info(f"Found {count} existing jobs matching search terms: {search_terms}")
        return count
        
    except Exception as e:
        logging.error(f"Error checking existing jobs: {e}")
        return 0
    finally:
        conn.close()

def get_recent_jobs_count(days: int = 7) -> int:
    """Get count of jobs scraped in the last N days"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"""
        SELECT COUNT(*) FROM {TABLE_NAME} 
        WHERE date(scraped_timestamp) >= date('now', '-{days} days')
        """)
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        logging.error(f"Error getting recent jobs count: {e}")
        return 0
    finally:
        conn.close()

def scrape_indeed_jobs_with_profile(search_term: str, location: str, job_type: str = None, 
                                   is_remote: bool = None, max_results: int = 50) -> Dict:
    """
    Enhanced function that returns both job count AND actual job data from Indeed search
    Still prevents duplicates in database but provides fresh data to frontend
    """
    logging.info(f"Starting enhanced Indeed search: '{search_term}' in '{location}' (max: {max_results})")
    
    try:
        # Initialize database
        init_database()
        
        # Build scrape_jobs parameters - only include valid parameters
        scrape_params = {
            "site_name": ["indeed"],
            "search_term": search_term,
            "location": location,
            "results_wanted": max_results,
            "country_indeed": "denmark",
            "verbose": 1,
            "description_format": "markdown"
        }
        
        # Only add optional parameters if they have valid values
        if job_type is not None and job_type.strip():
            scrape_params["job_type"] = job_type
            
        if is_remote is not None:  # Only add if explicitly True or False, not None
            scrape_params["is_remote"] = is_remote
        
        logging.info(f"Scraping with parameters: {scrape_params}")
        
        # Scrape jobs using jobspy with error handling for parameter compatibility
        try:
            df = scrape_jobs(**scrape_params)
        except TypeError as e:
            # If there's a parameter error, try with minimal parameters
            logging.warning(f"Parameter error: {e}. Trying with minimal parameters...")
            minimal_params = {
                "site_name": ["indeed"],
                "search_term": search_term,
                "location": location,
                "results_wanted": max_results
            }
            df = scrape_jobs(**minimal_params)
        
        if df is None or df.empty:
            logging.warning(f"No jobs found for search: '{search_term}' in '{location}'")
            return {
                "total_jobs_found": 0,
                "new_jobs_added": 0,
                "jobs_from_search": [],
                "search_summary": {
                    "search_term": search_term,
                    "location": location,
                    "job_type": job_type,
                    "is_remote": is_remote,
                    "status": "no_results"
                },
                "timestamp": pd.Timestamp.now().isoformat()
            }
        
        logging.info(f"Indeed returned {len(df)} jobs for '{search_term}'")
        
        # Convert DataFrame to records with search metadata
        job_records = convert_dataframe_to_records(df, search_term, location)
        
        # Check for existing jobs in database to avoid duplicates
        existing_jobs = set()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT title, company, location FROM job_postings")
            existing_jobs = {(row[0], row[1], row[2]) for row in cursor.fetchall()}
            logging.info(f"Found {len(existing_jobs)} existing jobs in database")
        except Exception as e:
            logging.warning(f"Could not check existing jobs: {e}")
        finally:
            conn.close()
        
        # Separate new jobs from duplicates
        new_jobs_for_db = []
        all_jobs_from_search = []
        
        for job in job_records:
            job_key = (job.get('title', ''), job.get('company', ''), job.get('location', ''))
            
            # Add to search results regardless (fresh from Indeed)
            all_jobs_from_search.append(job)
            
            # Only add to database if it's new
            if job_key not in existing_jobs:
                new_jobs_for_db.append(job)
                existing_jobs.add(job_key)  # Update set to avoid duplicates within this batch
        
        # Insert only new jobs into database
        new_jobs_count = 0
        if new_jobs_for_db:
            new_jobs_count = insert_job_records_enhanced(new_jobs_for_db)
            logging.info(f"Added {new_jobs_count} new jobs to database")
        else:
            logging.info("All jobs from Indeed search already exist in database")
        
        # Return comprehensive results including fresh job data
        return {
            "total_jobs_found": len(all_jobs_from_search),
            "new_jobs_added": new_jobs_count,
            "jobs_from_search": all_jobs_from_search,  # Fresh data from Indeed
            "search_summary": {
                "search_term": search_term,
                "location": location,
                "job_type": job_type,
                "is_remote": is_remote,
                "indeed_results": len(df),
                "new_in_database": new_jobs_count,
                "duplicates_found": len(all_jobs_from_search) - new_jobs_count,
                "status": "success"
            },
            "timestamp": pd.Timestamp.now().isoformat()
        }
        
    except Exception as e:
        error_msg = f"Error during Indeed scraping: {str(e)}"
        logging.error(error_msg)
        return {
            "total_jobs_found": 0,
            "new_jobs_added": 0,
            "jobs_from_search": [],
            "search_summary": {
                "search_term": search_term,
                "location": location,
                "error": error_msg,
                "status": "error"
            },
            "error": error_msg,
            "timestamp": pd.Timestamp.now().isoformat()
        }

def insert_job_records_enhanced(records: List[dict]) -> int:
    """Enhanced insert function that handles additional profile search metadata"""
    if not records:
        return 0
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Add columns for profile search metadata if they don't exist
    try:
        cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN search_job_type TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN search_is_remote BOOLEAN")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    inserted_count = 0
    
    for record in records:
        try:
            # Create a timestamp for both scraped_timestamp and last_seen_timestamp
            current_timestamp = pd.Timestamp.now().isoformat()
            
            cursor.execute(f"""
            INSERT OR IGNORE INTO {TABLE_NAME} (
                title, company, company_url, job_url, location,
                is_remote, job_type, description, date_posted, company_industry,
                company_description, company_logo, search_term, search_location,
                search_job_type, search_is_remote, scraped_timestamp, last_seen_timestamp
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """, (
                record['title'], record['company'], record['company_url'],
                record['job_url'], record['location'], record['is_remote'], 
                record['job_type'], record['description'], record['date_posted'],
                record['company_industry'], record['company_description'], 
                record['company_logo'], record['search_term'], record['search_location'],
                record.get('search_job_type'), record.get('search_is_remote'),
                current_timestamp, current_timestamp
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

def test_jobspy_parameters():
    """Test what parameters jobspy actually supports"""
    logging.info("Testing jobspy parameters...")
    
    try:
        # Test basic scraping with minimal parameters
        test_df = scrape_jobs(
            site_name=["indeed"],
            search_term="data analyst",
            location="copenhagen, denmark",
            results_wanted=5
        )
        logging.info(f"Basic scraping works - found {len(test_df)} jobs")
        
        # Test with country parameter
        try:
            test_df = scrape_jobs(
                site_name=["indeed"],
                search_term="data analyst", 
                location="copenhagen, denmark",
                results_wanted=5,
                country_indeed="denmark"
            )
            logging.info("country_indeed parameter works")
        except Exception as e:
            logging.warning(f"country_indeed parameter failed: {e}")
        
        # Test with job_type parameter
        try:
            test_df = scrape_jobs(
                site_name=["indeed"],
                search_term="data analyst",
                location="copenhagen, denmark", 
                results_wanted=5,
                job_type="fulltime"
            )
            logging.info("job_type parameter works")
        except Exception as e:
            logging.warning(f"job_type parameter failed: {e}")
            
        # Test with hours_old parameter
        try:
            test_df = scrape_jobs(
                site_name=["indeed"],
                search_term="data analyst",
                location="copenhagen, denmark",
                results_wanted=5,
                hours_old=168
            )
            logging.info("hours_old parameter works")
        except Exception as e:
            logging.warning(f"hours_old parameter failed: {e}")
            
    except Exception as e:
        logging.error(f"Basic jobspy test failed: {e}")

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
