import sqlite3
import logging
import os
from typing import Dict, List, Optional

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

def get_database_stats():
    """Get current database statistics."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Total records
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        total_records = cursor.fetchone()[0]
        
        # Records with missing company
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE company IS NULL OR company = ''")
        missing_company = cursor.fetchone()[0]
        
        # Records with missing industry
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE company_industry IS NULL OR company_industry = ''")
        missing_industry = cursor.fetchone()[0]
        
        # Records with missing description
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE company_description IS NULL OR company_description = ''")
        missing_description = cursor.fetchone()[0]
        
        return {
            'total_records': total_records,
            'missing_company': missing_company,
            'missing_industry': missing_industry,
            'missing_description': missing_description
        }
        
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

def main():
    """Main execution function."""
    logging.info("Starting data enrichment process")
    
    # Check database connection
    if not os.path.exists(DB_NAME):
        logging.error(f"Database {DB_NAME} not found. Run the scraper first.")
        return
    
    # Verify API key is loaded
    logging.info(f"API key loaded: {'Yes' if TOGETHER_API_KEY else 'No'}")
    if TOGETHER_API_KEY:
        logging.info(f"API key length: {len(TOGETHER_API_KEY)}")
    
    # Test LLM functionality
    if not test_llm_functionality():
        logging.error("LLM test failed. Check your API key and connection.")
        return
    
    # Get initial stats
    initial_stats = get_database_stats()
    if not initial_stats:
        logging.error("Could not get database statistics")
        return
    
    logging.info("📊 Initial database statistics:")
    logging.info(f"  Total records: {initial_stats['total_records']}")
    logging.info(f"  Missing company: {initial_stats['missing_company']}")
    logging.info(f"  Missing industry: {initial_stats['missing_industry']}")
    logging.info(f"  Missing description: {initial_stats['missing_description']}")
    
    if initial_stats['missing_company'] == 0 and initial_stats['missing_industry'] == 0 and initial_stats['missing_description'] == 0:
        logging.info("✅ No missing data found. Nothing to enrich.")
        return
    
    # Run enrichment batches with smaller batch size for better consistency
    batch_count = 0
    max_batches = 15  # Increased since we're using smaller batches
    batch_size = 8   # Reduced batch size for better LLM consistency
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

    # Get final stats
    final_stats = get_database_stats()
    if final_stats:
        logging.info("📊 Final database statistics:")
        logging.info(f"  Total records: {final_stats['total_records']}")
        logging.info(f"  Missing company: {final_stats['missing_company']}")
        logging.info(f"  Missing industry: {final_stats['missing_industry']}")
        logging.info(f"  Missing description: {final_stats['missing_description']}")
        
        # Calculate improvements
        company_improved = initial_stats['missing_company'] - final_stats['missing_company']
        industry_improved = initial_stats['missing_industry'] - final_stats['missing_industry']
        description_improved = initial_stats['missing_description'] - final_stats['missing_description']
        
        logging.info("🎯 Enrichment results:")
        logging.info(f"  Company names filled: {company_improved}")
        logging.info(f"  Industries filled: {industry_improved}")
        logging.info(f"  Descriptions filled: {description_improved}")
        logging.info(f"  Total fields enriched: {company_improved + industry_improved + description_improved}")
    
    logging.info("✅ Data enrichment process completed")

if __name__ == "__main__":
    main()
