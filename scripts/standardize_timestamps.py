#!/usr/bin/env python3
"""
Script to standardize all timestamp formats in the database.
This ensures all timestamps follow the YYYY-MM-DD HH:MM:SS format.

Can be used as a standalone script or imported as a module.
"""

import sqlite3
import pandas as pd
import argparse
import logging
from datetime import datetime
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Path to database
DB_PATH = 'data/databases/indeed_jobs.db'

def standardize_timestamps(dry_run=False):
    """
    Standardize all timestamps in the database to format: YYYY-MM-DD HH:MM:SS
    
    Args:
        dry_run (bool): If True, report issues but don't make changes
    """
    logger.info(f"Starting timestamp standardization {'(DRY RUN)' if dry_run else ''}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all records with potentially problematic timestamps
        timestamp_columns = ['last_seen_timestamp', 'scraped_timestamp', 'date_posted']
        problematic_counts = {}
        
        for column in timestamp_columns:
            cursor.execute(f"""
                SELECT COUNT(*) FROM job_postings 
                WHERE {column} LIKE '%T%' OR {column} LIKE '%.%'
            """)
            count = cursor.fetchone()[0]
            problematic_counts[column] = count
            
            if count > 0:
                logger.info(f"Found {count} records with non-standard format in {column}")
                
                # Get sample of problematic values
                cursor.execute(f"""
                    SELECT id, {column} FROM job_postings 
                    WHERE {column} LIKE '%T%' OR {column} LIKE '%.%'
                    LIMIT 5
                """)
                samples = cursor.fetchall()
                logger.info(f"Sample problematic values in {column}: {samples}")
                
                if not dry_run:
                    # Fix the problematic timestamps
                    cursor.execute(f"""
                        SELECT id, {column} FROM job_postings 
                        WHERE {column} LIKE '%T%' OR {column} LIKE '%.%'
                    """)
                    records_to_fix = cursor.fetchall()
                    
                    fixed_count = 0
                    for record_id, timestamp in records_to_fix:
                        try:
                            if timestamp:
                                # Parse and standardize the timestamp
                                dt = pd.to_datetime(timestamp, format='mixed')
                                standardized_timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
                                
                                cursor.execute(
                                    f"UPDATE job_postings SET {column} = ? WHERE id = ?",
                                    (standardized_timestamp, record_id)
                                )
                                fixed_count += 1
                        except Exception as e:
                            logger.error(f"Error fixing {column} for job ID {record_id}: {e}")
                    
                    logger.info(f"Fixed {fixed_count} records in {column}")
        
        if not dry_run and sum(problematic_counts.values()) > 0:
            # Commit changes
            conn.commit()
            logger.info(f"Successfully standardized all timestamps in the database.")
        elif sum(problematic_counts.values()) == 0:
            logger.info("No problematic timestamps found. Database is clean.")
        
        return problematic_counts
            
    except Exception as e:
        logger.error(f"Error: {e}")
        if conn and not dry_run:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Standardize timestamp formats in the database")
    parser.add_argument("--dry-run", action="store_true", help="Check for issues without making changes")
    
    args = parser.parse_args()
    standardize_timestamps(dry_run=args.dry_run)
