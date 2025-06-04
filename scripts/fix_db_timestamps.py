#!/usr/bin/env python3
"""
Script to standardize all timestamp formats in the Indeed jobs database.
This ensures all timestamps follow the YYYY-MM-DD HH:MM:SS format and fixes
any problematic ISO8601 format timestamps that use the T separator.
"""

import sqlite3
import os
import sys
import logging
from datetime import datetime

# Add the project root to Python path for proper imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

try:
    from src.skillscope.scrapers.indeed_scraper import DB_NAME, TABLE_NAME
except ImportError:
    # Set default values if import fails
    DB_NAME = 'data/databases/indeed_jobs.db'
    TABLE_NAME = 'job_postings'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(project_root, 'data/logs/timestamp_fix.log')),
        logging.StreamHandler()
    ]
)

def standardize_timestamps():
    """
    Fix all inconsistent timestamp formats in the database.
    Convert ISO8601 formats (with T separator) to standard SQLite format.
    """
    conn = None
    try:
        logging.info(f"Connecting to database at {DB_NAME}")
        if not os.path.exists(os.path.join(project_root, DB_NAME)):
            logging.error(f"Database file {DB_NAME} not found")
            return False
            
        conn = sqlite3.connect(os.path.join(project_root, DB_NAME))
        cursor = conn.cursor()
        
        # Get all timestamp columns in the table
        cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
        columns = cursor.fetchall()
        timestamp_columns = [col[1] for col in columns if 'timestamp' in col[1].lower()]
        
        logging.info(f"Found {len(timestamp_columns)} timestamp columns: {timestamp_columns}")
        
        total_fixed = 0
        for column in timestamp_columns:
            # Check how many records have ISO format timestamps
            cursor.execute(f"""
                SELECT COUNT(*) FROM {TABLE_NAME} 
                WHERE {column} LIKE '%T%' OR {column} LIKE '%.%'
            """)
            problematic_count = cursor.fetchone()[0]
            
            if problematic_count > 0:
                logging.info(f"Found {problematic_count} problematic timestamps in column {column}")
                
                # Fix timestamps by converting ISO format (YYYY-MM-DDThh:mm:ss.ssssss) to SQLite format (YYYY-MM-DD hh:mm:ss)
                cursor.execute(f"""
                    UPDATE {TABLE_NAME} SET {column} = 
                    SUBSTR({column}, 1, 10) || ' ' || SUBSTR({column}, 12, 8)
                    WHERE {column} LIKE '%T%'
                """)
                
                # Handle missing timestamps
                cursor.execute(f"""
                    UPDATE {TABLE_NAME} SET {column} = DATETIME('now')
                    WHERE {column} IS NULL
                """)
                
                total_fixed += cursor.rowcount
        
        logging.info(f"Fixed a total of {total_fixed} timestamp entries")
        
        # Add an optional check to make sure last_seen_timestamp is never before scraped_timestamp
        if 'last_seen_timestamp' in timestamp_columns and 'scraped_timestamp' in timestamp_columns:
            cursor.execute(f"""
                UPDATE {TABLE_NAME} SET last_seen_timestamp = scraped_timestamp
                WHERE datetime(last_seen_timestamp) < datetime(scraped_timestamp)
            """)
            if cursor.rowcount > 0:
                logging.info(f"Fixed {cursor.rowcount} records where last_seen_timestamp was earlier than scraped_timestamp")
        
        conn.commit()
        logging.info("All timestamp formats have been standardized successfully")
        return True
        
    except Exception as e:
        logging.error(f"Error standardizing timestamps: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    logging.info("Starting timestamp standardization process")
    if standardize_timestamps():
        logging.info("Timestamp standardization completed successfully")
        sys.exit(0)
    else:
        logging.error("Timestamp standardization failed")
        sys.exit(1)
