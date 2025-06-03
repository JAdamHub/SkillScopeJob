import sqlite3
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import schedule
import time
import threading

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed. Installing...")
    os.system("pip install python-dotenv")
    from dotenv import load_dotenv
    load_dotenv()

try:
    from langchain_together import Together
except ImportError as e:
    print(f"Required package not installed: {e}")
    print("Please run: pip install langchain-together")
    exit(1)

# Configuration
DB_NAME = 'indeed_jobs.db'
TABLE_NAME = 'job_postings'
TOGETHER_API_KEY = os.getenv('TOGETHER_API_KEY')

if not TOGETHER_API_KEY:
    print("Please set TOGETHER_API_KEY in your .env file")
    print("Example: TOGETHER_API_KEY=your_api_key_here")
    exit(1)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_enrichment.log'),
        logging.StreamHandler()
    ]
)

# Initialize TogetherAI LLM
try:
    llm = Together(
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        api_key=TOGETHER_API_KEY,
        temperature=0.1,
        max_tokens=1024,
        top_p=0.9,
        repetition_penalty=1.1
    )
    # Test the LLM connection
    try:
        test_response = llm.invoke("What is 2+2? Answer only with the number.")
        logging.info(f"LLM initialized successfully. Test response: {test_response[:100]}...")
    except Exception as test_e:
        logging.error(f"LLM test failed: {test_e}")
        raise test_e
except Exception as e:
    logging.error(f"Failed to initialize LLM: {e}")
    print(f"LLM initialization failed: {e}")
    print("Trying to diagnose the issue...")
    
    # Diagnostic information
    print(f"API Key present: {bool(TOGETHER_API_KEY)}")
    if TOGETHER_API_KEY:
        print(f"API Key starts with: {TOGETHER_API_KEY[:10]}...")
    
    # Try a simple test
    try:
        import requests
        response = requests.get("https://api.together.xyz/health", timeout=10)
        print(f"Together API health check: {response.status_code}")
    except Exception as req_e:
        print(f"Network/API issue: {req_e}")
    
    exit(1)

# Additional configuration for freshness management
DEFAULT_MAX_JOB_AGE_DAYS = 30
FRESHNESS_THRESHOLDS = {
    "fresh": 7,      # Jobs less than 7 days old
    "recent": 14,    # Jobs less than 14 days old
    "aging": 21,     # Jobs less than 21 days old
    "stale": DEFAULT_MAX_JOB_AGE_DAYS  # Jobs older than max_job_age_days are removed
}

def init_database_with_freshness_tracking():
    """
    Initialize database with additional columns for tracking job freshness
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Add freshness tracking columns if they don't exist
        cursor.execute(f"""
        ALTER TABLE {TABLE_NAME} 
        ADD COLUMN last_seen_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        """)
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute(f"""
        ALTER TABLE {TABLE_NAME} 
        ADD COLUMN job_status TEXT DEFAULT 'active'
        """)
    except sqlite3.OperationalError:
        pass  # Column already exists
        
    try:
        cursor.execute(f"""
        ALTER TABLE {TABLE_NAME} 
        ADD COLUMN refresh_count INTEGER DEFAULT 1
        """)
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create indexes for performance
    try:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_last_seen ON {TABLE_NAME}(last_seen_timestamp)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_job_status ON {TABLE_NAME}(job_status)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_scraped_date ON {TABLE_NAME}(date(scraped_timestamp))")
    except sqlite3.OperationalError:
        pass
    
    # Create metadata table for tracking cleanup dates
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS database_metadata (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()
    logging.info("Database freshness tracking initialized")

def _update_job_freshness_categories(conn: sqlite3.Connection, max_job_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS):
    """
    Update the job_freshness column for all jobs based on their scraped_timestamp.
    """
    cursor = conn.cursor()
    now = datetime.now()
    
    # Define freshness categories and their thresholds (days from now)
    # Order matters: from freshest to stalest
    categories = [
        ("fresh", FRESHNESS_THRESHOLDS["fresh"]),
        ("recent", FRESHNESS_THRESHOLDS["recent"]),
        ("aging", FRESHNESS_THRESHOLDS["aging"]),
        ("stale", max_job_age_days) # Anything older than max_job_age_days is stale
    ]

    try:
        # Fetch all job ids and their scraped_timestamps
        cursor.execute(f"SELECT id, scraped_timestamp FROM {TABLE_NAME}")
        jobs_to_update = cursor.fetchall()
        
        updated_count = 0
        for job_id, scraped_timestamp_str in jobs_to_update:
            if not scraped_timestamp_str:
                continue
            
            scraped_date = datetime.fromisoformat(scraped_timestamp_str)
            age_days = (now - scraped_date).days
            
            current_freshness = "stale" # Default to stale
            if age_days < categories[0][1]: # fresh
                current_freshness = categories[0][0]
            elif age_days < categories[1][1]: # recent
                current_freshness = categories[1][0]
            elif age_days < categories[2][1]: # aging
                current_freshness = categories[2][0]
            # else remains stale

            cursor.execute(f"UPDATE {TABLE_NAME} SET job_freshness = ? WHERE id = ?", (current_freshness, job_id))
            if cursor.rowcount > 0:
                updated_count += 1
        
        conn.commit()
        logging.info(f"Updated job_freshness for {updated_count} jobs.")

    except Exception as e:
        logging.error(f"Error updating job_freshness categories: {e}")
        conn.rollback()
    # No finally conn.close() as connection is managed by caller

def get_job_age_distribution(max_job_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS) -> Dict:
    """
    Get distribution of jobs by age categories
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        now = datetime.now()
        distribution = {}
        
        # Use dynamic thresholds based on max_job_age_days
        thresholds = FRESHNESS_THRESHOLDS.copy()
        thresholds["stale"] = max_job_age_days
        
        for category, days in thresholds.items():
            cutoff = now - timedelta(days=days)
            
            if category == "stale":
                # Count jobs older than threshold
                cursor.execute(f"""
                SELECT COUNT(*) FROM {TABLE_NAME} 
                WHERE scraped_timestamp < ?
                """, (cutoff.isoformat(),))
            else:
                # Count jobs within threshold
                cursor.execute(f"""
                SELECT COUNT(*) FROM {TABLE_NAME} 
                WHERE scraped_timestamp >= ?
                """, (cutoff.isoformat(),))
            
            distribution[category] = cursor.fetchone()[0]
        
        # Total count
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        distribution["total"] = cursor.fetchone()[0]
        
        return distribution
        
    except Exception as e:
        logging.error(f"Error getting job age distribution: {e}")
        return {}
    finally:
        conn.close()

def clean_stale_jobs(max_job_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS) -> Dict:
    """
    Remove jobs that are older than the maximum age threshold
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cutoff_date = datetime.now() - timedelta(days=max_job_age_days)
        
        # Count jobs to be removed
        cursor.execute(f"""
        SELECT COUNT(*) FROM {TABLE_NAME} 
        WHERE scraped_timestamp < ?
        """, (cutoff_date.isoformat(),))
        
        stale_count = cursor.fetchone()[0]
        
        if stale_count > 0:
            # Remove stale jobs
            cursor.execute(f"""
            DELETE FROM {TABLE_NAME} 
            WHERE scraped_timestamp < ?
            """, (cutoff_date.isoformat(),))
            
            conn.commit()
            logging.info(f"🧹 Removed {stale_count} stale jobs older than {max_job_age_days} days")
        
        # Get remaining job age distribution
        age_distribution = get_job_age_distribution(max_job_age_days)
        
        return {
            "stale_jobs_removed": stale_count,
            "cutoff_date": cutoff_date.isoformat(),
            "remaining_jobs": age_distribution
        }
        
    except Exception as e:
        logging.error(f"Error cleaning stale jobs: {e}")
        return {"error": str(e)}
    finally:
        conn.close()

def clear_entire_database():
    """
    Nuclear option: Clear entire job database for fresh start
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"DELETE FROM {TABLE_NAME}")
        conn.commit()
        logging.info("🧨 Entire job database cleared for fresh start")
        return {"status": "database_cleared", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logging.error(f"Error clearing database: {e}")
        return {"error": str(e)}
    finally:
        conn.close()

def get_last_cleanup_date() -> Optional[datetime]:
    """
    Get the last cleanup date from metadata table
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
        SELECT value FROM database_metadata 
        WHERE key = 'last_cleanup_date'
        """)
        
        result = cursor.fetchone()
        if result:
            return datetime.fromisoformat(result[0])
        return None
        
    except Exception as e:
        logging.error(f"Error getting last cleanup date: {e}")
        return None
    finally:
        conn.close()

def record_cleanup_date():
    """
    Record the current date as last cleanup date
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
        INSERT OR REPLACE INTO database_metadata (key, value, updated_timestamp)
        VALUES ('last_cleanup_date', ?, ?)
        """, (datetime.now().isoformat(), datetime.now().isoformat()))
        
        conn.commit()
        logging.info("📅 Cleanup date recorded")
    except Exception as e:
        logging.error(f"Error recording cleanup date: {e}")
    finally:
        conn.close()

def smart_database_refresh(cleanup_strategy: str = "smart", max_job_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS, force_full_refresh: bool = False) -> Dict:
    """
    Intelligent database refresh based on job age and cleanup strategy
    
    Args:
        cleanup_strategy: "aggressive" (daily clean), "smart" (selective refresh), or "conservative" (weekly)
        max_job_age_days: Maximum age for jobs before they're considered stale
        force_full_refresh: Force complete database refresh regardless of strategy
    """
    refresh_stats = {
        "strategy": cleanup_strategy,
        "timestamp": datetime.now().isoformat(),
        "actions_taken": [],
        "before_stats": get_job_age_distribution(max_job_age_days),
        "after_stats": {}
    }
    
    try:
        if cleanup_strategy == "aggressive" or force_full_refresh:
            # Daily complete refresh - nuclear option
            refresh_stats["actions_taken"].append("full_database_clear")
            clear_result = clear_entire_database()
            refresh_stats["clear_result"] = clear_result
            
        elif cleanup_strategy == "smart":
            # Selective refresh based on job age
            refresh_stats["actions_taken"].append("stale_job_cleanup")
            cleanup_result = clean_stale_jobs(max_job_age_days)
            refresh_stats["cleanup_result"] = cleanup_result
            
            # Check if we need to refresh specific categories
            age_dist = get_job_age_distribution(max_job_age_days)
            
            if age_dist.get("fresh", 0) < 50 and age_dist.get("total", 0) > 0:
                # Low fresh jobs - trigger targeted refresh
                refresh_stats["actions_taken"].append("targeted_fresh_job_scraping_needed")
                logging.info("⚠️ Low number of fresh jobs - consider running job scraping")
                
        elif cleanup_strategy == "conservative":
            # Weekly cleanup only
            last_cleanup = get_last_cleanup_date()
            if not last_cleanup or (datetime.now() - last_cleanup).days >= 7:
                refresh_stats["actions_taken"].append("weekly_cleanup")
                cleanup_result = clean_stale_jobs(max_job_age_days)
                refresh_stats["cleanup_result"] = cleanup_result
                record_cleanup_date()
            else:
                refresh_stats["actions_taken"].append("skipped_cleanup_too_recent")
                days_since_cleanup = (datetime.now() - last_cleanup).days
                logging.info(f"⏭️ Skipping cleanup - last cleanup was {days_since_cleanup} days ago")
        
        # Always update freshness tracking and job_freshness categories
        init_database_with_freshness_tracking()
        conn = sqlite3.connect(DB_NAME)
        try:
            _update_job_freshness_categories(conn, max_job_age_days)
        finally:
            conn.close()

        refresh_stats["after_stats"] = get_job_age_distribution(max_job_age_days)
        
        logging.info(f"🔄 Database refresh completed: {refresh_stats['actions_taken']}")
        return refresh_stats
        
    except Exception as e:
        logging.error(f"Error in smart database refresh: {e}")
        refresh_stats["error"] = str(e)
        return refresh_stats

def get_database_health_report(max_job_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS) -> Dict:
    """
    Comprehensive database health and freshness report
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "configuration": {
            "max_job_age_days": max_job_age_days,
            "freshness_thresholds": FRESHNESS_THRESHOLDS
        }
    }
    
    # Job age distribution
    report["age_distribution"] = get_job_age_distribution(max_job_age_days)
    
    # Enrichment status
    report["enrichment_status"] = get_database_stats()
    
    # Cleanup history
    last_cleanup = get_last_cleanup_date()
    report["last_cleanup"] = last_cleanup.isoformat() if last_cleanup else None
    
    # Health recommendations
    age_dist = report["age_distribution"]
    recommendations = []
    
    if age_dist.get("stale", 0) > 100:
        recommendations.append("Consider running stale job cleanup")
    
    if age_dist.get("fresh", 0) < 20 and age_dist.get("total", 0) > 0:
        recommendations.append("Database needs fresh job scraping")
    
    if age_dist.get("total", 0) == 0:
        recommendations.append("Database is empty - full scraping needed")
    
    freshness_ratio = (age_dist.get("fresh", 0) + age_dist.get("recent", 0)) / max(age_dist.get("total", 1), 1)
    if freshness_ratio < 0.3:
        recommendations.append("Low freshness ratio - consider more frequent scraping")
    
    report["recommendations"] = recommendations
    report["freshness_ratio"] = round(freshness_ratio, 2)
    
    logging.info(f"📊 Database health report generated - Freshness ratio: {report['freshness_ratio']}")
    
    return report

def auto_database_maintenance(cleanup_strategy: str = "smart", max_job_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS) -> Dict:
    """
    Automated database maintenance that can be run before enrichment
    """
    logging.info(f"🔧 Starting automated database maintenance (strategy: {cleanup_strategy})")
    
    # Get health report first
    health_report = get_database_health_report(max_job_age_days)
    
    # Decide if maintenance is needed
    maintenance_needed = False
    reasons = []
    
    # Check if we have stale jobs
    if health_report["age_distribution"].get("stale", 0) > 50:
        maintenance_needed = True
        reasons.append(f"Too many stale jobs: {health_report['age_distribution']['stale']}")
    
    # Check freshness ratio
    if health_report["freshness_ratio"] < 0.2:
        maintenance_needed = True
        reasons.append(f"Low freshness ratio: {health_report['freshness_ratio']}")
    
    # Check last cleanup date for conservative strategy
    if cleanup_strategy == "conservative":
        last_cleanup = get_last_cleanup_date()
        if not last_cleanup or (datetime.now() - last_cleanup).days >= 7:
            maintenance_needed = True
            reasons.append("Weekly cleanup is due")
    
    maintenance_result = {
        "maintenance_needed": maintenance_needed,
        "reasons": reasons,
        "health_report_before": health_report,
        "actions_performed": []
    }
    
    if maintenance_needed:
        logging.info(f"🚨 Maintenance needed: {', '.join(reasons)}")
        
        # Perform maintenance
        refresh_result = smart_database_refresh(cleanup_strategy, max_job_age_days)
        maintenance_result["refresh_result"] = refresh_result
        maintenance_result["actions_performed"] = refresh_result.get("actions_taken", [])
        
        # Get updated health report
        maintenance_result["health_report_after"] = get_database_health_report(max_job_age_days)
        
        logging.info(f"✅ Maintenance completed: {maintenance_result['actions_performed']}")
    else:
        logging.info("✨ Database is healthy - no maintenance needed")
    
    return maintenance_result

def get_database_stats():
    """Enhanced database statistics including freshness metrics."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # ...existing code...
        
        # Add freshness-related stats
        stats = {
            'total_records': 0,
            'missing_company': 0,
            'missing_industry': 0,
            'missing_description': 0
        }
        
        # Total records
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        stats['total_records'] = cursor.fetchone()[0]
        
        # Records with missing company
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE company IS NULL OR company = ''")
        stats['missing_company'] = cursor.fetchone()[0]
        
        # Records with missing industry
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE company_industry IS NULL OR company_industry = ''")
        stats['missing_industry'] = cursor.fetchone()[0]
        
        # Records with missing description
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE company_description IS NULL OR company_description = ''")
        stats['missing_description'] = cursor.fetchone()[0]
        
        # Add enrichment percentage
        if stats['total_records'] > 0:
            enriched_count = stats['total_records'] - stats['missing_industry']
            stats['enrichment_percentage'] = round((enriched_count / stats['total_records'] * 100), 1)
        else:
            stats['enrichment_percentage'] = 0.0
        
        # Add recent activity
        cursor.execute(f"""
        SELECT COUNT(*) FROM {TABLE_NAME} 
        WHERE date(scraped_timestamp) >= date('now', '-7 days')
        """)
        stats['recent_jobs_7_days'] = cursor.fetchone()[0]
        
        return stats
        
    except Exception as e:
        logging.error(f"Error getting database stats: {e}")
        return None
    finally:
        conn.close()

def is_rate_limit_error(msg: str) -> bool:
    """Detect Together API rate limit error in a message."""
    if not msg:
        return False
    return (
        "rate limit" in msg.lower()
        or "You have reached the rate limit" in msg
        or "model_rate_limit" in msg
    )

def batch_enrichment(batch_size=15):
    """Process multiple job records in a single LLM call for efficiency."""
    logging.info(f"Starting batch enrichment process with batch size: {batch_size}")
    
    # Get incomplete records
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"""
        SELECT id, title, company, description, company_industry, company_description
        FROM {TABLE_NAME}
        WHERE (company IS NULL OR company = '' OR 
               company_industry IS NULL OR company_industry = '' OR
               company_description IS NULL OR company_description = '')
        AND (description IS NOT NULL AND description != '')
        LIMIT ?
        """, (batch_size,))
        
        records = cursor.fetchall()
        
        if not records:
            logging.info("No records to enrich")
            return True
        
        logging.info(f"Found {len(records)} records to process in one batch")
        
        # Build a more structured and clear prompt
        prompt_parts = [
            "You are a data analyst. Analyze job postings and extract missing company information.",
            "",
            "IMPORTANT: You must respond in the exact format specified below for each job.",
            "Do not include any other text, explanations, or code.",
            "",
            "JOBS TO ANALYZE:"
        ]
        
        jobs_data = []
        for record in records:
            job_id, title, company, description, current_industry, current_description = record
            
            missing_company = not company or company.strip() == ''
            missing_industry = not current_industry or current_industry.strip() == ''
            missing_description = not current_description or current_description.strip() == ''
            
            if not missing_company and not missing_industry and not missing_description:
                continue
                
            jobs_data.append({
                'id': job_id,
                'title': title,
                'company': company,
                'description': description,
                'missing_company': missing_company,
                'missing_industry': missing_industry,
                'missing_description': missing_description
            })
            
            prompt_parts.append(f"")
            prompt_parts.append(f"JOB ID: {job_id}")
            prompt_parts.append(f"Title: {title}")
            prompt_parts.append(f"Company: {company if company else 'MISSING'}")
            prompt_parts.append(f"Description: {description[:350]}...")
            
            missing_fields = []
            if missing_company:
                missing_fields.append("company name")
            if missing_industry:
                missing_fields.append("industry")
            if missing_description:
                missing_fields.append("company description")
            prompt_parts.append(f"Missing fields: {', '.join(missing_fields)}")
        
        if not jobs_data:
            logging.info("No jobs need enrichment")
            return True
            
        prompt_parts.extend([
            "",
            "RESPONSE FORMAT:",
            "For each job above, respond with exactly this format (no extra text):",
            "",
            "JOB_ID: 1",
            "COMPANY: [company name only if missing]",
            "INDUSTRY: [one of: Technology, Healthcare, Finance, Retail, Manufacturing, Education, Government, Consulting, Transportation, Energy, Real Estate, Media, Food & Beverage, Hospitality, Construction, Legal, Non-profit]",
            "DESCRIPTION: [brief company description in 1-2 sentences]",
            "",
            "JOB_ID: 2", 
            "INDUSTRY: [category]",
            "DESCRIPTION: [description]",
            "",
            "RULES:",
            "- Only include COMPANY: line if company was MISSING",
            "- Always include INDUSTRY: and DESCRIPTION: for every job",
            "- Use exact format shown above",
            "- No explanations, code, or extra text",
            "- Process ALL jobs listed above",
            "",
            "START YOUR RESPONSE NOW:"
        ])
        
        prompt = "\n".join(prompt_parts)
        
        try:
            logging.info(f"Sending batch of {len(jobs_data)} jobs to LLM...")
            response = llm.invoke(prompt)
            logging.info(f"LLM batch response received: {len(response)} characters")
            
            # Log first 500 chars of response for debugging
            logging.info(f"Response preview: {response[:500]}...")
            
            # Parse batch response with better error handling
            current_job_id = None
            current_updates = {}
            all_updates = {}
            
            lines = response.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('JOB_ID:'):
                    # Save previous job if exists
                    if current_job_id is not None and current_updates:
                        all_updates[current_job_id] = current_updates
                        logging.debug(f"Saved updates for job {current_job_id}: {current_updates}")
                    
                    # Start new job
                    current_job_id = line.replace('JOB_ID:', '').strip()
                    current_updates = {}
                    logging.debug(f"Started processing job {current_job_id}")
                    
                elif line.startswith('COMPANY:') and current_job_id:
                    company_name = line.replace('COMPANY:', '').strip()
                    if company_name and len(company_name) > 2 and company_name.lower() not in ['unknown', 'n/a', 'not specified', 'missing', 'various']:
                        current_updates['company'] = company_name
                        logging.debug(f"Found company for job {current_job_id}: {company_name}")
                        
                elif line.startswith('INDUSTRY:') and current_job_id:
                    industry = line.replace('INDUSTRY:', '').strip()
                    if industry and len(industry) > 2 and industry.lower() not in ['unknown', 'n/a', 'not specified', 'various']:
                        current_updates['company_industry'] = industry
                        logging.debug(f"Found industry for job {current_job_id}: {industry}")
                        
                elif line.startswith('DESCRIPTION:') and current_job_id:
                    description = line.replace('DESCRIPTION:', '').strip()
                    if description and len(description) > 10 and description.lower() not in ['unknown', 'n/a', 'not specified', 'not available']:
                        current_updates['company_description'] = description
                        logging.debug(f"Found description for job {current_job_id}: {description[:50]}...")
            
            # Don't forget the last job
            if current_job_id is not None and current_updates:
                all_updates[current_job_id] = current_updates
                logging.debug(f"Saved final updates for job {current_job_id}: {current_updates}")
            
            logging.info(f"Parsed updates for {len(all_updates)} jobs out of {len(jobs_data)} sent")
            
            # If we got very few responses, log the full response for debugging
            if len(all_updates) < len(jobs_data) / 2:
                logging.warning(f"Low response rate. Full LLM response: {response}")
            
            # Apply updates to database
            updated_count = 0
            for job_data in jobs_data:
                job_id = str(job_data['id'])
                
                if job_id in all_updates:
                    updates_for_job = all_updates[job_id]
                    
                    # Filter updates based on what was actually missing
                    filtered_updates = {}
                    
                    if 'company' in updates_for_job and job_data['missing_company']:
                        filtered_updates['company'] = updates_for_job['company']
                    
                    if 'company_industry' in updates_for_job and job_data['missing_industry']:
                        filtered_updates['company_industry'] = updates_for_job['company_industry']
                        
                    if 'company_description' in updates_for_job and job_data['missing_description']:
                        filtered_updates['company_description'] = updates_for_job['company_description']
                    
                    if filtered_updates:
                        # Build update query
                        set_clauses = []
                        values = []
                        
                        for field, value in filtered_updates.items():
                            set_clauses.append(f"{field} = ?")
                            values.append(value)
                        
                        values.append(int(job_id))
                        update_query = f"UPDATE {TABLE_NAME} SET {', '.join(set_clauses)} WHERE id = ?"
                        
                        cursor.execute(update_query, values)
                        
                        if cursor.rowcount > 0:
                            updated_count += 1
                            logging.info(f"✅ Updated job {job_id}: {list(filtered_updates.keys())}")

                            # Determine enrichment status
                            # Fetch the updated record to check all relevant fields
                            cursor.execute(f"SELECT company, company_industry, company_description FROM {TABLE_NAME} WHERE id = ?", (int(job_id),))
                            updated_job_details = cursor.fetchone()
                            current_company, current_industry, current_comp_desc = updated_job_details if updated_job_details else (None, None, None)

                            enrich_status = 'pending' # Default
                            if current_company and current_industry and current_comp_desc and \
                               current_company.strip() and current_industry.strip() and current_comp_desc.strip():
                                enrich_status = 'full'
                            elif (current_company and current_company.strip()) or \
                                 (current_industry and current_industry.strip()) or \
                                 (current_comp_desc and current_comp_desc.strip()):
                                enrich_status = 'partial'
                            
                            cursor.execute(f"UPDATE {TABLE_NAME} SET enrichment_status = ? WHERE id = ?", (enrich_status, int(job_id)))
                            logging.info(f"Job {job_id} enrichment_status set to {enrich_status}")
                        else:
                            logging.warning(f"❌ No rows updated for job {job_id}")
                    else:
                        logging.info(f"⚠️  No valid updates for job {job_id}")
                else:
                    logging.warning(f"⚠️  No response found for job {job_id}")
            
            # Commit all changes
            conn.commit()
            logging.info(f"🎉 Successfully committed {updated_count} record updates to database")
            
            # Return True if we processed at least some records successfully
            return updated_count > 0 or len(all_updates) > 0
            
        except Exception as e:
            logging.error(f"❌ Error processing LLM batch response: {e}")
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            return False
        
    except Exception as e:
        logging.error(f"❌ Error in batch enrichment: {e}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        conn.rollback()
        return False
    finally:
        conn.close()

def test_llm_functionality():
    """Test LLM functionality with improved prompting."""
    logging.info("Testing LLM functionality...")
    
    try:
        # Test with clearer, more structured prompt
        test_prompt = """You are a data analyst. Analyze job postings and extract missing company information.

IMPORTANT: You must respond in the exact format specified below for each job.
Do not include any other text, explanations, or code.

JOBS TO ANALYZE:

JOB ID: 1
Title: Software Engineer
Company: MISSING
Description: We are a leading technology company developing mobile applications and web solutions for clients worldwide...
Missing fields: company name, industry, company description

JOB ID: 2
Title: Nurse
Company: Regional Hospital
Description: Hospital seeking qualified nurses for patient care in our emergency department...
Missing fields: industry, company description

RESPONSE FORMAT:
For each job above, respond with exactly this format (no extra text):

JOB_ID: 1
COMPANY: [company name only if missing]
INDUSTRY: [one of: Technology, Healthcare, Finance, Retail, Manufacturing, Education, Government, Consulting, Transportation, Energy, Real Estate, Media, Food & Beverage, Hospitality, Construction, Legal, Non-profit]
DESCRIPTION: [brief company description in 1-2 sentences]

JOB_ID: 2
INDUSTRY: [category]
DESCRIPTION: [description]

RULES:
- Only include COMPANY: line if company was MISSING
- Always include INDUSTRY: and DESCRIPTION: for every job
- Use exact format shown above
- No explanations, code, or extra text
- Process ALL jobs listed above

START YOUR RESPONSE NOW:"""
        
        response = llm.invoke(test_prompt)
        logging.info(f"Test response length: {len(response)} characters")
        logging.info(f"Test response preview: {response[:400]}...")
        
        # Test parsing
        job_updates = {}
        current_job_id = None
        
        for line in response.split('\n'):
            line = line.strip()
            if line.startswith('JOB_ID:'):
                current_job_id = line.replace('JOB_ID:', '').strip()
                job_updates[current_job_id] = {}
            elif line.startswith('COMPANY:') and current_job_id:
                job_updates[current_job_id]['company'] = line.replace('COMPANY:', '').strip()
            elif line.startswith('INDUSTRY:') and current_job_id:
                job_updates[current_job_id]['industry'] = line.replace('INDUSTRY:', '').strip()
            elif line.startswith('DESCRIPTION:') and current_job_id:
                job_updates[current_job_id]['description'] = line.replace('DESCRIPTION:', '').strip()
        
        logging.info(f"Parsed test updates: {job_updates}")
        
        # Check if we got responses for both test jobs
        if len(job_updates) >= 2:
            logging.info("✅ Test passed - got responses for multiple jobs")
            return True
        else:
            logging.warning(f"⚠️ Test partial - only got {len(job_updates)} responses")
            return True  # Still continue, but with warning
            
    except Exception as e:
        logging.error(f"LLM test failed: {e}")
        return False

def schedule_maintenance_jobs():
    """
    Set up scheduled maintenance jobs based on different strategies
    """
    # Daily maintenance at 2 AM (aggressive strategy)
    schedule.every().day.at("02:00").do(lambda: smart_database_refresh("aggressive"))
    
    # Smart maintenance every 12 hours
    schedule.every(12).hours.do(lambda: auto_database_maintenance("smart"))
    
    # Conservative maintenance weekly on Sunday at 3 AM
    schedule.every().sunday.at("03:00").do(lambda: auto_database_maintenance("conservative"))
    
    # Health check every 6 hours
    schedule.every(6).hours.do(log_database_health)
    
    logging.info("📅 Maintenance jobs scheduled:")
    logging.info("  - Daily aggressive cleanup at 2:00 AM")
    logging.info("  - Smart maintenance every 12 hours")
    logging.info("  - Conservative maintenance weekly on Sunday 3:00 AM")
    logging.info("  - Health checks every 6 hours")

def log_database_health():
    """
    Log database health status for monitoring
    """
    health = get_database_health_report()
    logging.info(f"🏥 Health Check - Freshness: {health['freshness_ratio']}, Total Jobs: {health['age_distribution']['total']}")
    
    # Alert if health is poor
    if health['freshness_ratio'] < 0.2:
        logging.warning(f"🚨 ALERT: Low freshness ratio {health['freshness_ratio']} - maintenance needed!")
    
    if health['age_distribution']['stale'] > 200:
        logging.warning(f"🚨 ALERT: {health['age_distribution']['stale']} stale jobs - cleanup recommended!")

def run_maintenance_scheduler():
    """
    Run the maintenance scheduler in a background thread
    """
    def scheduler_worker():
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
    scheduler_thread.start()
    logging.info("🔄 Maintenance scheduler started in background")

def check_maintenance_needed() -> Dict:
    """
    Check if maintenance is urgently needed based on current database state
    """
    health = get_database_health_report()
    
    urgent_maintenance = {
        "needed": False,
        "reasons": [],
        "recommended_action": "none",
        "health_score": health['freshness_ratio']
    }
    
    # Check for urgent conditions
    if health['freshness_ratio'] < 0.1:
        urgent_maintenance["needed"] = True
        urgent_maintenance["reasons"].append("Critical: Freshness ratio below 10%")
        urgent_maintenance["recommended_action"] = "immediate_cleanup"
    
    if health['age_distribution']['stale'] > 500:
        urgent_maintenance["needed"] = True
        urgent_maintenance["reasons"].append(f"Too many stale jobs: {health['age_distribution']['stale']}")
        urgent_maintenance["recommended_action"] = "aggressive_cleanup"
    
    if health['age_distribution']['total'] == 0:
        urgent_maintenance["needed"] = True
        urgent_maintenance["reasons"].append("Database is empty")
        urgent_maintenance["recommended_action"] = "full_scraping_needed"
    
    # Check last cleanup date
    last_cleanup = get_last_cleanup_date()
    if last_cleanup:
        days_since_cleanup = (datetime.now() - last_cleanup).days
        if days_since_cleanup > 14:
            urgent_maintenance["needed"] = True
            urgent_maintenance["reasons"].append(f"No cleanup for {days_since_cleanup} days")
            urgent_maintenance["recommended_action"] = "scheduled_cleanup"
    
    return urgent_maintenance

def main():
    """Enhanced main execution function with database maintenance"""
    logging.info("🚀 Starting data enrichment process with database maintenance")
    
    # Check database connection
    if not os.path.exists(DB_NAME):
        logging.error(f"Database {DB_NAME} not found. Run the scraper first.")
        return
    
    # Initialize freshness tracking
    init_database_with_freshness_tracking()
    
    # Check if urgent maintenance is needed
    urgent_check = check_maintenance_needed()
    if urgent_check["needed"]:
        logging.warning(f"🚨 Urgent maintenance needed: {', '.join(urgent_check['reasons'])}")
        logging.info(f"📋 Recommended action: {urgent_check['recommended_action']}")
        
        # Perform urgent maintenance
        if urgent_check["recommended_action"] == "immediate_cleanup":
            smart_database_refresh("aggressive", force_full_refresh=True)
        elif urgent_check["recommended_action"] == "aggressive_cleanup":
            smart_database_refresh("aggressive")
        else:
            auto_database_maintenance("smart")
    else:
        # Run normal maintenance
        maintenance_result = auto_database_maintenance(cleanup_strategy="smart")
        if maintenance_result["maintenance_needed"]:
            logging.info("🔧 Database maintenance was performed before enrichment")
    
    # Verify API key is loaded
    logging.info(f"API key loaded: {'Yes' if TOGETHER_API_KEY else 'No'}")
    if TOGETHER_API_KEY:
        logging.info(f"API key length: {len(TOGETHER_API_KEY)}")
    
    # Test LLM functionality
    if not test_llm_functionality():
        logging.error("LLM test failed. Check your API key and connection.")
        return
    
    # Get initial stats (now includes freshness metrics)
    initial_stats = get_database_stats()
    if not initial_stats:
        logging.error("Could not get database statistics")
        return
    
    # Get health report
    health_report = get_database_health_report()
    
    logging.info("📊 Initial database statistics:")
    logging.info(f"  Total records: {initial_stats['total_records']}")
    logging.info(f"  Missing company: {initial_stats['missing_company']}")
    logging.info(f"  Missing industry: {initial_stats['missing_industry']}")
    logging.info(f"  Missing description: {initial_stats['missing_description']}")
    logging.info(f"  Enrichment percentage: {initial_stats['enrichment_percentage']}%")
    logging.info(f"  Freshness ratio: {health_report['freshness_ratio']}")
    logging.info(f"  Recent jobs (7 days): {initial_stats['recent_jobs_7_days']}")
    
    if initial_stats['missing_company'] == 0 and initial_stats['missing_industry'] == 0 and initial_stats['missing_description'] == 0:
        logging.info("✅ No missing data found. Nothing to enrich.")
        # Still show health report
        logging.info("📈 Database health summary:")
        for rec in health_report.get("recommendations", []):
            logging.info(f"  💡 {rec}")
        return
    
    # Run enrichment batches with smaller batch size for better consistency
    batch_count = 0
    max_batches = 15  # Increased since we're using smaller batches
    batch_size = 15   # Reduced batch size for better LLM consistency
    wait_time = 3

    logging.info(f"🚀 Starting enrichment with batch size: {batch_size}")

    while batch_count < max_batches:
        batch_count += 1
        logging.info(f"🔄 Running enrichment batch {batch_count}/{max_batches} (batch_size={batch_size})")
        
        try:
            result = batch_enrichment(batch_size=batch_size)
            
            if not result:
                logging.warning(f"⚠️ Batch {batch_count} had no updates - continuing anyway")
                # Don't break immediately, continue with next batch
                
        except Exception as e:
            msg = str(e)
            if is_rate_limit_error(msg):
                logging.warning(f"⏰ Rate limit hit. Waiting {wait_time} seconds before retrying...")
                import time
                time.sleep(wait_time)
                wait_time = min(wait_time * 2, 60)  # exponential backoff, max 1 min
                batch_count -= 1  # retry this batch
                batch_size = max(3, batch_size // 2)  # reduce batch size, minimum 3
                logging.info(f"📉 Reduced batch size to {batch_size}")
                continue
            else:
                logging.error(f"❌ Batch {batch_count} failed with error: {e}")
                break
        
        # Check if there's more work to do
        current_stats = get_database_stats()
        if current_stats:
            remaining_work = (current_stats['missing_company'] + 
                            current_stats['missing_industry'] + 
                            current_stats['missing_description'])
            
            logging.info(f"📈 Progress update after batch {batch_count}:")
            logging.info(f"  Remaining missing fields: {remaining_work}")
            
            if remaining_work == 0:
                logging.info("🎉 All missing data has been enriched!")
                break
        
        # Wait between batches
        if batch_count < max_batches:
            logging.info(f"⏸️  Waiting {wait_time} seconds before next batch...")
            import time
            time.sleep(wait_time)

    # Get final stats and health report
    final_stats = get_database_stats()
    final_health = get_database_health_report()
    
    if final_stats:
        logging.info("📊 Final database statistics:")
        logging.info(f"  Total records: {final_stats['total_records']}")
        logging.info(f"  Missing company: {final_stats['missing_company']}")
        logging.info(f"  Missing industry: {final_stats['missing_industry']}")
        logging.info(f"  Missing description: {final_stats['missing_description']}")
        logging.info(f"  Enrichment percentage: {final_stats['enrichment_percentage']}%")
        logging.info(f"  Final freshness ratio: {final_health['freshness_ratio']}")
        
        # Calculate improvements
        company_improved = initial_stats['missing_company'] - final_stats['missing_company']
        industry_improved = initial_stats['missing_industry'] - final_stats['missing_industry']
        description_improved = initial_stats['missing_description'] - final_stats['missing_description']
        
        logging.info("🎯 Enrichment results:")
        logging.info(f"  Company names filled: {company_improved}")
        logging.info(f"  Industries filled: {industry_improved}")
        logging.info(f"  Descriptions filled: {description_improved}")
        logging.info(f"  Total fields enriched: {company_improved + industry_improved + description_improved}")
        
        # Final health recommendations
        if final_health.get("recommendations"):
            logging.info("💡 Final recommendations:")
            for rec in final_health["recommendations"]:
                logging.info(f"  - {rec}")
    
    logging.info("✅ Data enrichment process completed with freshness management")

if __name__ == "__main__":
    # Optional: Start maintenance scheduler for long-running processes
    import sys
    if "--schedule" in sys.argv:
        schedule_maintenance_jobs()
        run_maintenance_scheduler()
        logging.info("🔄 Running with automatic maintenance scheduling")
        
        # Keep the script running for scheduled tasks
        try:
            while True:
                time.sleep(3600)  # Sleep for 1 hour between checks
        except KeyboardInterrupt:
            logging.info("🛑 Maintenance scheduler stopped")
    else:
        main()
