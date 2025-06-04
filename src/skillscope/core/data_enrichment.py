import sqlite3
import logging
import os
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import schedule
import time
import threading

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    # Also try loading from project root
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
    env_path = os.path.join(project_root, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
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
    Together = None

# Configuration
DB_NAME = 'data/databases/indeed_jobs.db'
TABLE_NAME = 'job_postings'
TOGETHER_API_KEY = os.getenv('TOGETHER_API_KEY')

# Don't exit at import time - allow module to be imported for data cleaning functions
if not TOGETHER_API_KEY:
    print("Warning: TOGETHER_API_KEY not set. LLM functions will not work.")
    print("Set TOGETHER_API_KEY in your .env file for full functionality.")
    print("Example: TOGETHER_API_KEY=your_api_key_here")
    llm = None
else:
    llm = None  # Will be initialized when needed

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/data_enrichment.log'),
        logging.StreamHandler()
    ]
)

# Initialize TogetherAI LLM when needed
def initialize_llm():
    """Initialize the LLM only when needed"""
    global llm
    if llm is not None:
        return llm
    
    if not TOGETHER_API_KEY:
        logging.error("TOGETHER_API_KEY not set. Cannot initialize LLM.")
        return None
    
    if Together is None:
        logging.error("langchain_together not available. Cannot initialize LLM.")
        return None
    
    try:
        llm = Together(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            api_key=TOGETHER_API_KEY,
            temperature=0.1,
            max_tokens=1024,
            top_p=0.9,
            repetition_penalty=1.1
        )
        logging.info("LLM initialized successfully")
        return llm
    except Exception as e:
        logging.error(f"Failed to initialize LLM: {e}")
        return None

# Additional configuration for job management
DEFAULT_MAX_JOB_AGE_DAYS = 30

def clean_old_jobs(max_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS) -> Dict:
    """
    Simple data cleaning: Remove jobs older than specified days based on last_seen_timestamp
    This replaces all complex cleaning strategies with a single, reliable approach.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        # Count jobs to be removed (based on last_seen_timestamp)  
        cursor.execute(f"""
        SELECT COUNT(*) FROM {TABLE_NAME} 
        WHERE last_seen_timestamp < ? OR last_seen_timestamp IS NULL
        """, (cutoff_date.isoformat(),))
        
        old_count = cursor.fetchone()[0]
        
        # Get total count before cleanup
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        total_before = cursor.fetchone()[0]
        
        if old_count > 0:
            # Remove old jobs
            cursor.execute(f"""
            DELETE FROM {TABLE_NAME} 
            WHERE last_seen_timestamp < ? OR last_seen_timestamp IS NULL
            """, (cutoff_date.isoformat(),))
            
            conn.commit()
            logging.info(f"🧹 Removed {old_count} jobs not seen in the last {max_age_days} days")
        
        # Get remaining job count
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        total_after = cursor.fetchone()[0]
        
        # Record cleanup date
        cursor.execute("""
        INSERT OR REPLACE INTO database_metadata (key, value, updated_timestamp)
        VALUES ('last_cleanup_date', ?, ?)
        """, (datetime.now().isoformat(), datetime.now().isoformat()))
        
        conn.commit()
        
        return {
            "jobs_removed": old_count,
            "jobs_before": total_before,
            "jobs_after": total_after,
            "cutoff_date": cutoff_date.isoformat(),
            "max_age_days": max_age_days,
            "cleanup_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Error cleaning old jobs: {e}")
        return {"error": str(e)}
    finally:
        conn.close()

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
    Update the job_freshness column for all jobs based on their last_seen_timestamp.
    Simplified to use only active/inactive status.
    """
    cursor = conn.cursor()
    now = datetime.now()
    cutoff_date = now - timedelta(days=max_job_age_days)

    try:
        # Update all jobs as either 'active' (seen recently) or 'inactive' (old)
        cursor.execute(f"""
        UPDATE {TABLE_NAME} 
        SET job_freshness = CASE 
            WHEN last_seen_timestamp >= ? THEN 'active'
            ELSE 'inactive'
        END
        """, (cutoff_date.isoformat(),))
        
        updated_count = cursor.rowcount
        conn.commit()
        logging.info(f"Updated job_freshness for {updated_count} jobs (active/inactive based on {max_job_age_days} day threshold).")

    except Exception as e:
        logging.error(f"Error updating job_freshness categories: {e}")
        conn.rollback()
    # No finally conn.close() as connection is managed by caller

def get_job_age_distribution(max_job_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS) -> Dict:
    """
    Get simplified distribution of jobs by age (active vs old) based on last_seen_timestamp
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cutoff_date = datetime.now() - timedelta(days=max_job_age_days)
        
        # Count active jobs (seen within max_job_age_days)
        cursor.execute(f"""
        SELECT COUNT(*) FROM {TABLE_NAME} 
        WHERE last_seen_timestamp >= ?
        """, (cutoff_date.isoformat(),))
        active_count = cursor.fetchone()[0]
        
        # Count old jobs (not seen within max_job_age_days or NULL timestamp)
        cursor.execute(f"""
        SELECT COUNT(*) FROM {TABLE_NAME} 
        WHERE last_seen_timestamp < ? OR last_seen_timestamp IS NULL
        """, (cutoff_date.isoformat(),))
        old_count = cursor.fetchone()[0]
        
        # Total count
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        total_count = cursor.fetchone()[0]
        
        return {
            "active": active_count,
            "old": old_count,
            "total": total_count,
            "cutoff_date": cutoff_date.isoformat(),
            "max_age_days": max_job_age_days
        }
        
    except Exception as e:
        logging.error(f"Error getting job age distribution: {e}")
        return {"active": 0, "old": 0, "total": 0, "error": str(e)}
    finally:
        conn.close()

def clean_stale_jobs(max_job_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS) -> Dict:
    """
    Remove jobs that are older than the maximum age threshold
    This is an alias for clean_old_jobs to maintain backward compatibility
    """
    return clean_old_jobs(max_job_age_days)

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

def simple_database_cleanup(max_job_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS) -> Dict:
    """
    Simplified database cleanup - just remove old jobs and update job freshness
    This replaces the complex smart_database_refresh function
    """
    cleanup_stats = {
        "timestamp": datetime.now().isoformat(),
        "max_age_days": max_job_age_days,
        "before_stats": get_job_age_distribution(max_job_age_days),
        "actions_taken": []
    }
    
    try:
        # Clean old jobs
        cleanup_result = clean_old_jobs(max_job_age_days)
        cleanup_stats["cleanup_result"] = cleanup_result
        cleanup_stats["actions_taken"].append("removed_old_jobs")
        
        # Update job freshness categories
        init_database_with_freshness_tracking()
        conn = sqlite3.connect(DB_NAME)
        try:
            _update_job_freshness_categories(conn, max_job_age_days)
            cleanup_stats["actions_taken"].append("updated_job_freshness")
        finally:
            conn.close()

        cleanup_stats["after_stats"] = get_job_age_distribution(max_job_age_days)
        
        logging.info(f"🔄 Simple database cleanup completed: {cleanup_stats['actions_taken']}")
        return cleanup_stats
        
    except Exception as e:
        logging.error(f"Error in simple database cleanup: {e}")
        cleanup_stats["error"] = str(e)
        return cleanup_stats

def smart_database_refresh(max_job_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS, force_full_refresh: bool = False) -> Dict:
    """
    Simplified database refresh - now uses simple cleanup approach only
    """
    if force_full_refresh:
        # Full database clear
        clear_result = clear_entire_database()
        return {
            "timestamp": datetime.now().isoformat(),
            "actions_taken": ["full_database_clear"],
            "clear_result": clear_result
        }
    else:
        # Use simple cleanup
        return simple_database_cleanup(max_job_age_days)

def get_database_health_report(max_job_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS) -> Dict:
    """
    Simplified database health report based on active vs old jobs
    """
    age_distribution = get_job_age_distribution(max_job_age_days)
    total_jobs = age_distribution.get("total", 0)
    active_jobs = age_distribution.get("active", 0)
    
    # Calculate freshness ratio (active jobs / total jobs)
    freshness_ratio = active_jobs / total_jobs if total_jobs > 0 else 0
    
    return {
        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "old_jobs": age_distribution.get("old", 0),
        "freshness_ratio": freshness_ratio,
        "age_distribution": age_distribution,
        "health_score": freshness_ratio,  # Simplified health score
        "last_updated": datetime.now().isoformat()
    }

def auto_database_maintenance(max_job_age_days: int = DEFAULT_MAX_JOB_AGE_DAYS) -> Dict:
    """
    Simplified automated database maintenance
    """
    logging.info(f"🔧 Starting simplified database maintenance (max age: {max_job_age_days} days)")
    
    # Get health report first
    age_distribution = get_job_age_distribution(max_job_age_days)
    
    # Decide if maintenance is needed
    maintenance_needed = False
    reasons = []
    
    # Check if we have old jobs that need cleaning
    if age_distribution.get("old", 0) > 0:
        maintenance_needed = True
        reasons.append(f"Found {age_distribution['old']} old jobs to clean")
    
    # Check if we haven't cleaned in a while
    last_cleanup = get_last_cleanup_date()
    if not last_cleanup or (datetime.now() - last_cleanup).days >= 7:
        maintenance_needed = True
        reasons.append("Weekly cleanup is due")
    
    maintenance_result = {
        "maintenance_needed": maintenance_needed,
        "reasons": reasons,
        "age_distribution_before": age_distribution,
        "actions_performed": []
    }
    
    if maintenance_needed:
        logging.info(f"🚨 Maintenance needed: {', '.join(reasons)}")
        
        # Perform simple cleanup
        cleanup_result = simple_database_cleanup(max_job_age_days)
        maintenance_result["cleanup_result"] = cleanup_result
        maintenance_result["actions_performed"] = cleanup_result.get("actions_taken", [])
        
        # Get updated distribution
        maintenance_result["age_distribution_after"] = get_job_age_distribution(max_job_age_days)
        
        logging.info(f"✅ Maintenance completed: {maintenance_result['actions_performed']}")
    else:
        logging.info("✨ Database is clean - no maintenance needed")
    
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
            # Initialize LLM if needed
            current_llm = initialize_llm()
            logging.info(f"Sending batch of {len(jobs_data)} jobs to LLM...")
            response = current_llm.invoke(prompt)
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
        
        # Initialize LLM if needed
        current_llm = initialize_llm()
        if current_llm is None:
            logging.error("LLM initialization failed. Cannot test functionality.")
            return False
            
        response = current_llm.invoke(test_prompt)
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
    Set up simplified scheduled maintenance jobs
    """
    # Daily maintenance at 2 AM
    schedule.every().day.at("02:00").do(lambda: auto_database_maintenance())
    
    # Health check every 6 hours
    schedule.every(6).hours.do(log_database_health)
    
    logging.info("📅 Simplified maintenance jobs scheduled:")
    logging.info("  - Daily maintenance at 2:00 AM")
    logging.info("  - Health checks every 6 hours")

def log_database_health():
    """
    Log database health status for monitoring
    """
    health = get_database_health_report()
    logging.info(f"🏥 Health Check - Freshness: {health['freshness_ratio']:.2f}, Total Jobs: {health['total_jobs']}")
    
    # Alert if health is poor
    if health['freshness_ratio'] < 0.2:
        logging.warning(f"🚨 ALERT: Low freshness ratio {health['freshness_ratio']:.2f} - maintenance needed!")
    
    if health['old_jobs'] > 200:
        logging.warning(f"🚨 ALERT: {health['old_jobs']} old jobs - cleanup recommended!")

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

# Removed complex check_maintenance_needed function - now using simple auto_database_maintenance

def main():
    """Simplified main execution function with basic database maintenance"""
    logging.info("🚀 Starting data enrichment process")
    
    # Check database connection
    if not os.path.exists(DB_NAME):
        logging.error(f"Database {DB_NAME} not found. Run the scraper first.")
        return
    
    # Initialize freshness tracking
    init_database_with_freshness_tracking()
    
    # Run simple maintenance
    maintenance_result = auto_database_maintenance()
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

# Integration functions for main_app.py and admin_app.py

def run_data_enrichment_for_app(app_context="manual", batch_size=10, max_batches=5):
    """
    Run data enrichment optimized for app integration.
    
    Args:
        app_context: "manual" for admin app, "auto" for main app
        batch_size: Number of records to process in each batch
        max_batches: Maximum number of batches to run
    
    Returns:
        dict: Results summary with success status and stats
    """
    try:
        logging.info(f"🚀 Starting data enrichment from {app_context} context")
        
        # Check database exists
        if not os.path.exists(DB_NAME):
            return {
                "success": False,
                "error": f"Database {DB_NAME} not found. Run the scraper first.",
                "stats": None
            }
        
        # Initialize freshness tracking
        init_database_with_freshness_tracking()
        
        # Get initial stats
        initial_stats = get_database_stats()
        if not initial_stats:
            return {
                "success": False,
                "error": "Could not get database statistics",
                "stats": None
            }
        
        # Check if enrichment is needed
        missing_total = (initial_stats['missing_company'] + 
                        initial_stats['missing_industry'] + 
                        initial_stats['missing_description'])
        
        if missing_total == 0:
            logging.info("✅ No missing data found. Nothing to enrich.")
            return {
                "success": True,
                "message": "No enrichment needed - all data is complete",
                "stats": {
                    "initial": initial_stats,
                    "final": initial_stats,
                    "improvements": {"company": 0, "industry": 0, "description": 0}
                }
            }
        
        # Test LLM functionality first
        if not test_llm_functionality():
            return {
                "success": False,
                "error": "LLM test failed. Check API key and connection.",
                "stats": {"initial": initial_stats}
            }
        
        # Run enrichment batches
        batch_count = 0
        wait_time = 2 if app_context == "auto" else 3
        
        logging.info(f"🔄 Running enrichment with {batch_size} records per batch, max {max_batches} batches")
        
        while batch_count < max_batches:
            batch_count += 1
            logging.info(f"📊 Processing batch {batch_count}/{max_batches}")
            
            try:
                result = batch_enrichment(batch_size=batch_size)
                
                if not result:
                    logging.info(f"⚠️ Batch {batch_count} completed with no updates")
                
                # Check remaining work
                current_stats = get_database_stats()
                if current_stats:
                    remaining_work = (current_stats['missing_company'] + 
                                    current_stats['missing_industry'] + 
                                    current_stats['missing_description'])
                    
                    if remaining_work == 0:
                        logging.info("🎉 All missing data has been enriched!")
                        break
                
            except Exception as e:
                msg = str(e)
                if is_rate_limit_error(msg):
                    if app_context == "auto":
                        logging.warning(f"⏰ Rate limit hit - stopping for auto context")
                        break
                    else:
                        logging.warning(f"⏰ Rate limit hit. Waiting {wait_time} seconds...")
                        import time
                        time.sleep(wait_time)
                        wait_time = min(wait_time * 2, 30)
                        batch_count -= 1  # retry this batch
                        continue
                else:
                    logging.error(f"❌ Batch {batch_count} failed: {e}")
                    if app_context == "auto":
                        break  # Don't continue on error in auto mode
            
            # Brief wait between batches
            if batch_count < max_batches:
                import time
                time.sleep(wait_time)
        
        # Get final stats
        final_stats = get_database_stats()
        
        if final_stats:
            # Calculate improvements
            company_improved = initial_stats['missing_company'] - final_stats['missing_company']
            industry_improved = initial_stats['missing_industry'] - final_stats['missing_industry']
            description_improved = initial_stats['missing_description'] - final_stats['missing_description']
            
            total_improved = company_improved + industry_improved + description_improved
            
            logging.info(f"✅ Enrichment completed - {total_improved} fields enriched")
            
            return {
                "success": True,
                "message": f"Enrichment completed successfully - {total_improved} fields enriched",
                "stats": {
                    "initial": initial_stats,
                    "final": final_stats,
                    "improvements": {
                        "company": company_improved,
                        "industry": industry_improved,
                        "description": description_improved,
                        "total": total_improved
                    }
                }
            }
        else:
            return {
                "success": False,
                "error": "Could not get final statistics",
                "stats": {"initial": initial_stats}
            }
            
    except Exception as e:
        logging.error(f"❌ Data enrichment error: {e}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "stats": None
        }

def get_enrichment_status():
    """
    Get current enrichment status for UI display.
    
    Returns:
        dict: Current enrichment status and statistics
    """
    try:
        if not os.path.exists(DB_NAME):
            return {
                "database_exists": False,
                "error": "Database not found"
            }
        
        stats = get_database_stats()
        health = get_database_health_report()
        
        if not stats:
            return {
                "database_exists": True,
                "error": "Could not retrieve statistics"
            }
        
        missing_total = (stats['missing_company'] + 
                        stats['missing_industry'] + 
                        stats['missing_description'])
        
        return {
            "database_exists": True,
            "total_records": stats['total_records'],
            "missing_data": {
                "company": stats['missing_company'],
                "industry": stats['missing_industry'],
                "description": stats['missing_description'],
                "total": missing_total
            },
            "enrichment_percentage": stats['enrichment_percentage'],
            "freshness_ratio": health['freshness_ratio'],
            "recent_jobs_7_days": stats['recent_jobs_7_days'],
            "needs_enrichment": missing_total > 0,
            "api_key_configured": bool(TOGETHER_API_KEY),
            "recommendations": health.get('recommendations', [])
        }
        
    except Exception as e:
        logging.error(f"Error getting enrichment status: {e}")
        return {
            "database_exists": True,
            "error": str(e)
        }

def quick_maintenance_check():
    """
    Quick check if database maintenance is needed.
    
    Returns:
        dict: Maintenance status and recommendations
    """
    try:
        if not os.path.exists(DB_NAME):
            return {"needed": False, "reason": "Database not found"}
        
        # Get database stats and health report
        stats = get_database_stats()
        if not stats:
            return {"needed": False, "reason": "Could not get database stats"}
            
        health_report = get_database_health_report()
        freshness_ratio = health_report.get("freshness_ratio", 0.0)
        
        # Simple criteria for maintenance need
        needs_maintenance = (
            stats["total_records"] == 0 or
            stats["enrichment_percentage"] < 80.0 or
            freshness_ratio < 0.8
        )
        
        reasons = []
        if stats["total_records"] == 0:
            reasons.append("Database is empty")
        if stats["enrichment_percentage"] < 80.0:
            reasons.append(f"Low enrichment: {stats['enrichment_percentage']}%")
        if freshness_ratio < 0.8:
            reasons.append(f"Low freshness: {freshness_ratio}")
        
        return {
            "needed": needs_maintenance,
            "reasons": reasons if needs_maintenance else [],
            "recommended_action": "run simple_database_cleanup" if needs_maintenance else "none",
            "health_score": freshness_ratio,
            "total_records": stats["total_records"],
            "enrichment_percentage": stats["enrichment_percentage"]
        }
        
    except Exception as e:
        logging.error(f"Error checking maintenance: {e}")
        return {"needed": False, "error": str(e)}

def run_quick_maintenance():
    """
    Run quick maintenance suitable for app context.
    
    Returns:
        dict: Maintenance results
    """
    try:
        logging.info("🔧 Running quick maintenance...")
        
        # Run simple maintenance
        result = auto_database_maintenance()
        
        return {
            "success": True,
            "maintenance_performed": result["maintenance_needed"],
            "records_cleaned": result.get("records_cleaned", 0),
            "message": "Quick maintenance completed"
        }
        
    except Exception as e:
        logging.error(f"Error running maintenance: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# Export key functions for app integration
__all__ = [
    'run_data_enrichment_for_app',
    'get_enrichment_status', 
    'quick_maintenance_check',
    'run_quick_maintenance',
    'get_database_stats',
    'get_database_health_report'
]
