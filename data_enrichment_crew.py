import sqlite3
import logging
import os
from typing import Dict, List, Optional
import json
from dataclasses import dataclass

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
    from crewai import Agent, Task, Crew
    from crewai.tools import BaseTool
    from pydantic import BaseModel, Field
    from langchain_together import Together
except ImportError as e:
    print(f"Required packages not installed: {e}")
    print("Please run: pip install crewai langchain-together")
    exit(1)

# Configuration
DB_NAME = 'indeed_jobs.db'
TABLE_NAME = 'job_postings'
TOGETHER_API_KEY = os.getenv('TOGETHER_API_KEY')
BATCH_SIZE = 10  # Set your preferred batch size here

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

@dataclass
class JobRecord:
    """Data class for job records."""
    id: int
    title: str
    company: str
    company_url: str
    job_url: str
    location: str
    is_remote: bool
    job_type: str
    description: str
    date_posted: str
    company_industry: str
    company_description: str
    company_logo: str
    search_term: str
    search_location: str

# Initialize TogetherAI LLM with updated configuration
try:
    llm = Together(
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        api_key=TOGETHER_API_KEY,
        temperature=0.1,
        max_tokens=1024,  # Reduced to prevent long rambling responses
        top_p=0.9,
        repetition_penalty=1.1
    )
    # Test the LLM connection immediately with more detailed error handling
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
    
    # Try a simple test without CrewAI
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

def simple_direct_enrichment(batch_size=15):
    """Direct enrichment processing multiple records in a single LLM call."""
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
        
        # Byg en samlet prompt med alle opslag
        prompt_parts = [
            "Analyze the following job postings and provide missing information for each.",
            "For each job, provide company name (if missing), industry category, and brief company description.",
            "",
            "Jobs to analyze:"
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
            prompt_parts.append(f"Description: {description[:400]}...")
            
            missing_fields = []
            if missing_company:
                missing_fields.append("company name")
            if missing_industry:
                missing_fields.append("industry")
            if missing_description:
                missing_fields.append("company description")
            prompt_parts.append(f"Missing: {', '.join(missing_fields)}")
        
        if not jobs_data:
            logging.info("No jobs need enrichment")
            return True
            
        prompt_parts.extend([
            "",
            "For each job, respond in this exact format:",
            "JOB_ID: [job_id]",
            "COMPANY: [company name if missing]",
            "INDUSTRY: [industry category]", 
            "DESCRIPTION: [brief company description]",
            "",
            "Use these industry categories: Technology, Healthcare, Finance, Retail, Manufacturing, Education, Government, Consulting, Transportation, Energy, Real Estate, Media, Food & Beverage, Hospitality, Construction, Legal, Non-profit",
            "",
            "Only include COMPANY: line if the company was missing. Always include INDUSTRY: and DESCRIPTION: lines.",
            "Keep descriptions to 1-2 sentences max."
        ])
        
        prompt = "\n".join(prompt_parts)
        
        try:
            logging.info(f"Sending batch of {len(jobs_data)} jobs to LLM...")
            response = llm.invoke(prompt)
            logging.info(f"LLM batch response received: {len(response)} characters")
            
            # Parse batch response
            current_job_id = None
            current_updates = {}
            all_updates = {}
            
            for line in response.split('\n'):
                line = line.strip()
                if line.startswith('JOB_ID:'):
                    # Save previous job if exists
                    if current_job_id is not None and current_updates:
                        all_updates[current_job_id] = current_updates
                    
                    # Start new job
                    current_job_id = line.replace('JOB_ID:', '').strip()
                    current_updates = {}
                    
                elif line.startswith('COMPANY:') and current_job_id:
                    company_name = line.replace('COMPANY:', '').strip()
                    if company_name and company_name.lower() not in ['unknown', 'n/a', 'not specified', 'missing']:
                        current_updates['company'] = company_name
                        
                elif line.startswith('INDUSTRY:') and current_job_id:
                    industry = line.replace('INDUSTRY:', '').strip()
                    if industry and industry.lower() not in ['unknown', 'n/a', 'not specified']:
                        current_updates['company_industry'] = industry
                        
                elif line.startswith('DESCRIPTION:') and current_job_id:
                    description = line.replace('DESCRIPTION:', '').strip()
                    if description and len(description) > 10 and description.lower() not in ['unknown', 'n/a', 'not specified']:
                        current_updates['company_description'] = description
            
            # Don't forget the last job
            if current_job_id is not None and current_updates:
                all_updates[current_job_id] = current_updates
            
            logging.info(f"Parsed updates for {len(all_updates)} jobs")
            
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
            
            return updated_count > 0
            
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

def run_enrichment_batch(batch_size=BATCH_SIZE):
    """Run a single batch of data enrichment using direct approach."""
    logging.info("Starting data enrichment batch")
    try:
        # Use direct enrichment instead of CrewAI
        result = simple_direct_enrichment(batch_size=batch_size)
        if result:
            logging.info("Enrichment batch completed successfully")
            return True
        else:
            logging.error("Direct enrichment failed")
            return False
    except Exception as e:
        msg = str(e)
        logging.error(f"Error during enrichment: {msg}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        if is_rate_limit_error(msg):
            return "rate_limit"
        return False

def test_llm_directly():
    """Test LLM functionality directly without CrewAI."""
    logging.info("Testing LLM directly...")
    
    try:
        # Test batch processing format
        batch_test_prompt = """
        Analyze the following job postings and provide missing information for each.
        
        Jobs to analyze:
        
        JOB ID: 1
        Title: Software Engineer
        Company: MISSING
        Description: We are a leading technology company developing mobile applications...
        Missing: company name, industry, company description
        
        JOB ID: 2
        Title: Nurse
        Company: Regional Hospital
        Description: Hospital seeking qualified nurses for patient care...
        Missing: industry, company description
        
        For each job, respond in this exact format:
        JOB_ID: [job_id]
        COMPANY: [company name if missing]
        INDUSTRY: [industry category]
        DESCRIPTION: [brief company description]
        
        Only include COMPANY: line if the company was missing.
        """
        
        response = llm.invoke(batch_test_prompt)
        logging.info(f"Batch test response: {response[:300]}...")
        
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
        
        logging.info(f"Parsed batch updates: {job_updates}")
        
        return True
    except Exception as e:
        logging.error(f"Direct LLM test failed: {e}")
        return False

def simple_enrichment_test():
    """Test enrichment process with a simple approach."""
    logging.info("Running simple enrichment test...")
    
    try:
        # Test the direct enrichment function with 1 record
        result = simple_direct_enrichment(batch_size=1)
        logging.info(f"Simple enrichment test result: {result}")
        return True
        
    except Exception as e:
        logging.error(f"Simple enrichment test failed: {e}")
        return False

def main():
    """Main execution function."""
    logging.info("Starting direct data enrichment process")
    
    # Check database connection
    if not os.path.exists(DB_NAME):
        logging.error(f"Database {DB_NAME} not found. Run the scraper first.")
        return
    
    # Verify API key is loaded
    logging.info(f"API key loaded: {'Yes' if TOGETHER_API_KEY else 'No'}")
    if TOGETHER_API_KEY:
        logging.info(f"API key length: {len(TOGETHER_API_KEY)}")
    
    # Test LLM directly first
    if not test_llm_directly():
        logging.error("Direct LLM test failed. Check your API key and connection.")
        return
    
    # Run simple enrichment test
    if not simple_enrichment_test():
        logging.error("Simple enrichment test failed.")
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
    
    # Run enrichment batches med større batch størrelse
    batch_count = 0
    max_batches = 10  # Øget fra 5 til 10
    total_processed = 0
    batch_size = 15  # Øget fra 3 til 20 opslag ad gangen
    wait_time = 3  # Reduceret ventetid

    logging.info(f"🚀 Starting enrichment with batch size: {batch_size}")

    while batch_count < max_batches:
        batch_count += 1
        logging.info(f"🔄 Running enrichment batch {batch_count}/{max_batches} (batch_size={batch_size})")
        result = run_enrichment_batch(batch_size=batch_size)
        
        if result == "rate_limit":
            logging.warning(f"⏰ Rate limit hit. Waiting {wait_time} seconds before retrying...")
            import time
            time.sleep(wait_time)
            wait_time = min(wait_time * 2, 60)  # exponential backoff, max 1 min
            batch_count -= 1  # retry this batch
            batch_size = max(5, batch_size // 2)  # reduce batch size, minimum 5
            logging.info(f"📉 Reduced batch size to {batch_size}")
            continue
        elif not result:
            logging.error(f"❌ Batch {batch_count} failed")
            break
            
        total_processed += batch_size
        
        # Check if there's more work to do
        current_stats = get_database_stats()
        if current_stats:
            remaining_work = (current_stats['missing_company'] + 
                            current_stats['missing_industry'] + 
                            current_stats['missing_description'])
            
            logging.info(f"📈 Progress update after batch {batch_count}:")
            logging.info(f"  Records processed: {total_processed}")
            logging.info(f"  Remaining missing fields: {remaining_work}")
            
            if remaining_work == 0:
                logging.info("🎉 All missing data has been enriched!")
                break
        
        # Kortere pause mellem batches
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
