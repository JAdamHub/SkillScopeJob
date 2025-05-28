import sqlite3
import logging
import os
from typing import Dict, List, Optional
import json
from dataclasses import dataclass

try:
    from crewai import Agent, Task, Crew, Process
    from crewai_tools import tool
    from langchain_community.llms import Together
except ImportError:
    print("CrewAI not installed. Please run: pip install crewai crewai-tools langchain-community")
    exit(1)

# Configuration
DB_NAME = 'indeed_jobs.db'
TABLE_NAME = 'job_postings'
TOGETHER_API_KEY = os.getenv('TOGETHER_API_KEY')

if not TOGETHER_API_KEY:
    print("Please set TOGETHER_API_KEY environment variable")
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

# Initialize TogetherAI LLM
llm = Together(
    model="meta-llama/Llama-2-70b-chat-hf",
    together_api_key=TOGETHER_API_KEY,
    temperature=0.1,
    max_tokens=1024
)

@tool
def get_incomplete_records(batch_size: int = 10) -> str:
    """Get job records with missing data from database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"""
        SELECT id, title, company, company_url, job_url, location, is_remote, 
               job_type, description, date_posted, company_industry, 
               company_description, company_logo, search_term, search_location
        FROM {TABLE_NAME}
        WHERE (company IS NULL OR company = '' OR 
               company_industry IS NULL OR company_industry = '' OR
               company_description IS NULL OR company_description = '')
        AND (description IS NOT NULL AND description != '')
        LIMIT ?
        """, (batch_size,))
        
        records = cursor.fetchall()
        
        if not records:
            return "No incomplete records found."
        
        job_data = []
        for record in records:
            job = JobRecord(*record)
            job_dict = {
                'id': job.id,
                'title': job.title,
                'company': job.company,
                'location': job.location,
                'description': job.description[:500] + "..." if len(job.description) > 500 else job.description,
                'company_industry': job.company_industry,
                'company_description': job.company_description,
                'missing_fields': []
            }
            
            # Identify missing fields
            if not job.company or job.company.strip() == '':
                job_dict['missing_fields'].append('company')
            if not job.company_industry or job.company_industry.strip() == '':
                job_dict['missing_fields'].append('company_industry')
            if not job.company_description or job.company_description.strip() == '':
                job_dict['missing_fields'].append('company_description')
                
            job_data.append(job_dict)
        
        return json.dumps(job_data, indent=2)
        
    except Exception as e:
        logging.error(f"Error getting incomplete records: {e}")
        return f"Error: {e}"
    finally:
        conn.close()

@tool
def update_job_record(job_id: int, updates: str) -> str:
    """Update job record with enriched data."""
    try:
        update_data = json.loads(updates)
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        set_clauses = []
        values = []
        
        for field, value in update_data.items():
            if field in ['company', 'company_industry', 'company_description'] and value:
                set_clauses.append(f"{field} = ?")
                values.append(value.strip())
        
        if not set_clauses:
            return "No valid updates provided"
        
        values.append(job_id)
        query = f"UPDATE {TABLE_NAME} SET {', '.join(set_clauses)} WHERE id = ?"
        
        cursor.execute(query, values)
        conn.commit()
        
        if cursor.rowcount > 0:
            logging.info(f"Updated job record {job_id} with: {list(update_data.keys())}")
            return f"Successfully updated job {job_id}"
        else:
            return f"No record found with id {job_id}"
            
    except json.JSONDecodeError:
        return "Invalid JSON format for updates"
    except Exception as e:
        logging.error(f"Error updating record {job_id}: {e}")
        return f"Error: {e}"
    finally:
        conn.close()

# Define Agents
data_analyst_agent = Agent(
    role='Data Quality Analyst',
    goal='Identify missing or incomplete data in job records and determine what information can be extracted from existing fields',
    backstory="""You are an expert data analyst specializing in job market data. 
    You excel at identifying patterns and extracting valuable information from job descriptions 
    to fill missing company details. You have deep knowledge of Danish and international companies.""",
    verbose=True,
    allow_delegation=False,
    llm=llm,
    tools=[get_incomplete_records]
)

data_enrichment_agent = Agent(
    role='Data Enrichment Specialist',
    goal='Extract missing company information from job descriptions and enrich incomplete records',
    backstory="""You are a data enrichment specialist with expertise in analyzing job descriptions 
    to extract company names, industries, and company descriptions. You can identify company information 
    even when it's embedded within job descriptions. You understand business terminology and can 
    categorize companies into appropriate industries.""",
    verbose=True,
    allow_delegation=False,
    llm=llm,
    tools=[update_job_record]
)

# Define Tasks
data_analysis_task = Task(
    description="""
    Analyze the job records database to identify records with missing data. Focus on:
    1. Records where 'company' field is empty but company name might be in the description
    2. Records missing 'company_industry' that could be inferred from job title, description, or company name
    3. Records missing 'company_description' that could be extracted from job description
    
    Get a batch of incomplete records and provide a detailed analysis of what's missing and what can potentially be filled.
    """,
    agent=data_analyst_agent,
    expected_output="A detailed analysis of incomplete job records with identification of missing fields and potential data sources for enrichment."
)

data_enrichment_task = Task(
    description="""
    Based on the analysis of incomplete records, enrich the data by:
    
    1. **Company Name Extraction**: If company field is empty, carefully analyze the job description to find the company name. Look for patterns like:
       - "We are [Company Name]"
       - "Join [Company Name]"
       - Company names mentioned in context
       - Domain names that might indicate company names
    
    2. **Industry Classification**: Determine the company industry based on:
       - Job description content
       - Company name (if known)
       - Job responsibilities and requirements
       - Use standard industry categories like: Technology, Healthcare, Finance, Retail, Manufacturing, Consulting, etc.
    
    3. **Company Description**: Extract or create a brief company description based on:
       - Information provided in the job description about the company
       - Company mission, values, or business description mentioned
       - Keep it concise (1-2 sentences)
    
    For each record, return the enriched data in JSON format with only the fields that need updating.
    Be conservative - only fill fields where you're confident about the accuracy.
    
    Process each record individually and update them one by one.
    """,
    agent=data_enrichment_agent,
    expected_output="Updated job records with enriched company information where missing data has been successfully identified and filled.",
    context=[data_analysis_task]
)

# Define Crew
enrichment_crew = Crew(
    agents=[data_analyst_agent, data_enrichment_agent],
    tasks=[data_analysis_task, data_enrichment_task],
    verbose=2,
    process=Process.sequential
)

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

def run_enrichment_batch():
    """Run a single batch of data enrichment."""
    logging.info("Starting data enrichment batch")
    
    try:
        result = enrichment_crew.kickoff()
        logging.info("Enrichment batch completed successfully")
        return True
        
    except Exception as e:
        logging.error(f"Error during enrichment: {e}")
        return False

def main():
    """Main execution function."""
    logging.info("Starting CrewAI data enrichment process")
    
    # Check database connection
    if not os.path.exists(DB_NAME):
        logging.error(f"Database {DB_NAME} not found. Run the scraper first.")
        return
    
    # Get initial stats
    initial_stats = get_database_stats()
    if not initial_stats:
        logging.error("Could not get database statistics")
        return
    
    logging.info("Initial database statistics:")
    logging.info(f"  Total records: {initial_stats['total_records']}")
    logging.info(f"  Missing company: {initial_stats['missing_company']}")
    logging.info(f"  Missing industry: {initial_stats['missing_industry']}")
    logging.info(f"  Missing description: {initial_stats['missing_description']}")
    
    if initial_stats['missing_company'] == 0 and initial_stats['missing_industry'] == 0 and initial_stats['missing_description'] == 0:
        logging.info("No missing data found. Nothing to enrich.")
        return
    
    # Run enrichment batches
    batch_count = 0
    max_batches = 10  # Limit batches to avoid excessive API calls
    
    while batch_count < max_batches:
        batch_count += 1
        logging.info(f"Running enrichment batch {batch_count}")
        
        if not run_enrichment_batch():
            logging.error(f"Batch {batch_count} failed")
            break
        
        # Check if there's more work to do
        current_stats = get_database_stats()
        if current_stats and (current_stats['missing_company'] == 0 and 
                             current_stats['missing_industry'] == 0 and 
                             current_stats['missing_description'] == 0):
            logging.info("All missing data has been enriched!")
            break
        
        # Small delay between batches
        import time
        time.sleep(2)
    
    # Get final stats
    final_stats = get_database_stats()
    if final_stats:
        logging.info("Final database statistics:")
        logging.info(f"  Total records: {final_stats['total_records']}")
        logging.info(f"  Missing company: {final_stats['missing_company']}")
        logging.info(f"  Missing industry: {final_stats['missing_industry']}")
        logging.info(f"  Missing description: {final_stats['missing_description']}")
        
        # Calculate improvements
        company_improved = initial_stats['missing_company'] - final_stats['missing_company']
        industry_improved = initial_stats['missing_industry'] - final_stats['missing_industry']
        description_improved = initial_stats['missing_description'] - final_stats['missing_description']
        
        logging.info("Enrichment results:")
        logging.info(f"  Company names filled: {company_improved}")
        logging.info(f"  Industries filled: {industry_improved}")
        logging.info(f"  Descriptions filled: {description_improved}")
    
    logging.info("Data enrichment process completed")

if __name__ == "__main__":
    main()
