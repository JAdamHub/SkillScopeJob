#!/usr/bin/env python3
"""
Script to fix inconsistent timestamp formats in the database.
This will standardize all timestamps to the format: YYYY-MM-DD HH:MM:SS
"""

import sqlite3
import pandas as pd
from datetime import datetime
import os
import sys

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = 'data/databases/indeed_jobs.db'

def fix_timestamps():
    """Fix inconsistent timestamp formats in the database"""
    print(f"Connecting to database at {DB_PATH}...")
    
    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all records with ISO8601 format (containing 'T')
        cursor.execute("""
            SELECT id, last_seen_timestamp, scraped_timestamp 
            FROM job_postings 
            WHERE last_seen_timestamp LIKE '%T%' 
               OR scraped_timestamp LIKE '%T%'
        """)
        
        problematic_records = cursor.fetchall()
        print(f"Found {len(problematic_records)} records with inconsistent timestamp formats")
        
        if not problematic_records:
            print("No problematic records found. Database is clean.")
            conn.close()
            return
        
        # Process and fix each problematic record
        for record_id, last_seen, scraped in problematic_records:
            # Fix last_seen_timestamp if needed
            if 'T' in last_seen:
                # Parse ISO format and convert to standard format
                try:
                    dt = pd.to_datetime(last_seen, format='mixed')
                    standardized_timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    cursor.execute(
                        "UPDATE job_postings SET last_seen_timestamp = ? WHERE id = ?",
                        (standardized_timestamp, record_id)
                    )
                    print(f"Fixed last_seen_timestamp for job ID {record_id}: {last_seen} → {standardized_timestamp}")
                except Exception as e:
                    print(f"Error fixing last_seen_timestamp for job ID {record_id}: {e}")
            
            # Fix scraped_timestamp if needed
            if scraped and 'T' in str(scraped):
                try:
                    dt = pd.to_datetime(scraped, format='mixed')
                    standardized_timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    cursor.execute(
                        "UPDATE job_postings SET scraped_timestamp = ? WHERE id = ?",
                        (standardized_timestamp, record_id)
                    )
                    print(f"Fixed scraped_timestamp for job ID {record_id}: {scraped} → {standardized_timestamp}")
                except Exception as e:
                    print(f"Error fixing scraped_timestamp for job ID {record_id}: {e}")
        
        # Commit changes
        conn.commit()
        print(f"Successfully standardized all timestamps in the database.")
            
    except Exception as e:
        print(f"Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    fix_timestamps()
