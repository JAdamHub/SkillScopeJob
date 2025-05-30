import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import sqlite3

from indeed_scraper import scrape_indeed_jobs_with_profile, init_database, DB_NAME, TABLE_NAME

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProfileJobMatcher:
    """
    Integrates user profile data with job scraping to find relevant positions
    """
    
    def __init__(self):
        self.job_type_mapping = {
            # Streamlit app options -> jobspy format
            "Full-time": "fulltime",
            "Part-time": "parttime", 
            "Internship": "internship",
            "Temporary": "contract",
            "Permanent": "fulltime",
            "Student job": "parttime",
            "Volunteer work": "parttime",
            "New graduate": "fulltime",
            "Apprentice": "internship"
        }
        
        self.location_mapping = {
            # Danish locations -> jobspy search terms - updated for Danish communes
            "Danmark": "denmark",
            "Hovedstaden": "copenhagen, denmark",
            "Midtjylland": "aarhus, denmark",
            "Nordjylland": "aalborg, denmark",
            "Sjælland": "zealand, denmark",
            "Syddanmark": "odense, denmark",
            "København": "copenhagen, denmark",
            "Aarhus kommune": "aarhus, denmark",
            "Aalborg kommune": "aalborg, denmark",
            "Odense kommune": "odense, denmark",
            "Esbjerg kommune": "esbjerg, denmark",
            "Randers kommune": "randers, denmark",
            "Kolding kommune": "kolding, denmark",
            "Horsens kommune": "horsens, denmark",
            "Vejle kommune": "vejle, denmark",
            "Roskilde kommune": "roskilde, denmark",
            "Herning kommune": "herning, denmark",
            "Silkeborg kommune": "silkeborg, denmark",
            "Næstved kommune": "naestved, denmark",
            "Fredericia kommune": "fredericia, denmark",
            "Viborg kommune": "viborg, denmark",
            "Køge kommune": "koege, denmark",
            "Holstebro kommune": "holstebro, denmark",
            "Taastrup kommune": "taastrup, denmark",
            "Slagelse kommune": "slagelse, denmark",
            "Hillerød kommune": "hilleroed, denmark",
            "Sønderborg kommune": "soenderborg, denmark",
            "Svendborg kommune": "svendborg, denmark",
            "Hjørring kommune": "hjoerring, denmark",
            "Frederikshavn kommune": "frederikshavn, denmark",
            "Gentofte kommune": "gentofte, denmark",
            "Gladsaxe kommune": "gladsaxe, denmark",
            "Herlev kommune": "herlev, denmark"
        }

    def extract_search_parameters(self, profile_data: Dict) -> Dict:
        """
        Extract and format search parameters from user profile data
        """
        search_params = {
            'job_titles': profile_data.get('job_title_keywords', []),
            'locations': [],
            'job_types': [],
            'remote_preference': profile_data.get('remote_openness', "Don't care"),
            'user_profile': profile_data
        }
        
        # Map locations
        preferred_locations = profile_data.get('preferred_locations_dk', [])
        for location in preferred_locations:
            mapped_location = self.location_mapping.get(location, location.lower() + ", denmark")
            if mapped_location not in search_params['locations']:
                search_params['locations'].append(mapped_location)
        
        # Default location if none specified
        if not search_params['locations']:
            search_params['locations'] = ['copenhagen, denmark']
        
        # Map job types to jobspy format
        desired_job_types = profile_data.get('job_types', [])
        for job_type in desired_job_types:
            mapped_type = self.job_type_mapping.get(job_type)
            if mapped_type and mapped_type not in search_params['job_types']:
                search_params['job_types'].append(mapped_type)
        
        # Default job type if none specified
        if not search_params['job_types']:
            search_params['job_types'] = ['fulltime']
        
        return search_params

    def determine_remote_setting(self, remote_preference: str) -> Optional[bool]:
        """
        Convert remote preference to jobspy is_remote parameter
        """
        if remote_preference == "Primarily Remote":
            return True
        elif remote_preference == "Primarily On-site":
            return False
        else:
            # "Don't care" or "Primarily Hybrid" - let jobspy find all types
            return None

    def run_profile_based_search(self, profile_data: Dict, max_results_per_search: int = 50) -> Dict:
        """
        Run job searches based on user profile and return summary
        """
        logger.info("Starting profile-based job search")
        
        # Initialize database
        init_database()
        
        # Extract search parameters
        search_params = self.extract_search_parameters(profile_data)
        logger.info(f"Search parameters: {search_params}")
        
        # Store user profile in database for reference
        self._store_user_profile(profile_data)
        
        total_inserted = 0
        search_results = {
            'total_jobs_found': 0,
            'searches_performed': [],
            'profile_summary': {
                'user_id': profile_data.get('user_session_id', 'unknown'),
                'target_roles': search_params['job_titles'],
                'locations': search_params['locations'],
                'job_types': search_params['job_types'],
                'remote_preference': search_params['remote_preference']
            }
        }
        
        # Test jobspy before running searches
        logger.info("Testing jobspy compatibility...")
        try:
            from indeed_scraper import test_jobspy_parameters
            test_jobspy_parameters()
        except Exception as e:
            logger.warning(f"Jobspy test failed: {e}")
        
        # Perform searches for each combination of job title and location
        for job_title in search_params['job_titles']:
            for location in search_params['locations']:
                # Limit to one job type to avoid too many combinations
                primary_job_type = search_params['job_types'][0] if search_params['job_types'] else 'fulltime'
                
                search_info = {
                    'job_title': job_title,
                    'location': location, 
                    'job_type': primary_job_type,
                    'timestamp': datetime.now().isoformat(),
                    'jobs_found': 0
                }
                
                try:
                    logger.info(f"Searching: {job_title} | {location} | {primary_job_type}")
                    
                    # Determine remote setting
                    is_remote = self.determine_remote_setting(search_params['remote_preference'])
                    
                    # Use enhanced scraper with profile parameters
                    inserted_count = scrape_indeed_jobs_with_profile(
                        search_term=job_title,
                        location=location,
                        job_type=primary_job_type,
                        is_remote=is_remote,
                        max_results=max_results_per_search
                    )
                    
                    search_info['jobs_found'] = inserted_count
                    total_inserted += inserted_count
                    
                    logger.info(f"Found {inserted_count} new jobs for {job_title} in {location}")
                    
                    # If no jobs found, try with basic search
                    if inserted_count == 0:
                        logger.info(f"Retrying with basic search for {job_title}")
                        try:
                            from indeed_scraper import scrape_indeed_jobs
                            fallback_count = scrape_indeed_jobs(job_title, location)
                            search_info['fallback_jobs_found'] = fallback_count
                            total_inserted += fallback_count
                            logger.info(f"Fallback search found {fallback_count} jobs")
                        except Exception as fallback_error:
                            logger.error(f"Fallback search also failed: {fallback_error}")
                    
                    # Small delay between searches
                    import time
                    time.sleep(3)  # Increased delay to be more respectful
                    
                except Exception as e:
                    logger.error(f"Error in search {job_title}/{location}/{primary_job_type}: {e}")
                    search_info['error'] = str(e)
                
                search_results['searches_performed'].append(search_info)
        
        search_results['total_jobs_found'] = total_inserted
        
        # Log summary
        logger.info(f"Profile-based search completed. Total new jobs: {total_inserted}")
        
        return search_results

    def _store_user_profile(self, profile_data: Dict):
        """
        Store user profile data in database for reference and analytics
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Create profile table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_session_id TEXT,
            profile_data TEXT,
            created_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_search_timestamp DATETIME
        )
        """)
        
        try:
            # Store or update profile
            cursor.execute("""
            INSERT OR REPLACE INTO user_profiles 
            (user_session_id, profile_data, last_search_timestamp)
            VALUES (?, ?, ?)
            """, (
                profile_data.get('user_session_id', 'unknown'),
                json.dumps(profile_data),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            logger.info("User profile stored in database")
            
        except Exception as e:
            logger.error(f"Error storing user profile: {e}")
        finally:
            conn.close()

    def get_profile_job_matches(self, user_session_id: str, limit: int = 50) -> List[Dict]:
        """
        Get job matches for a specific user profile with relevance scoring
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # Get user profile
            cursor.execute("""
            SELECT profile_data FROM user_profiles 
            WHERE user_session_id = ? 
            ORDER BY last_search_timestamp DESC LIMIT 1
            """, (user_session_id,))
            
            profile_row = cursor.fetchone()
            if not profile_row:
                return []
            
            profile_data = json.loads(profile_row[0])
            job_titles = profile_data.get('job_title_keywords', [])
            
            if not job_titles:
                return []
            
            # Build query to find relevant jobs
            title_conditions = []
            params = []
            
            for title in job_titles:
                title_conditions.append("LOWER(title) LIKE ?")
                params.append(f"%{title.lower()}%")
            
            title_condition_sql = " OR ".join(title_conditions)
            
            # Add parameters for description matching - need to add them for each title condition too
            skill_pattern = f"%{' '.join(profile_data.get('current_skills_selected', [])[:3]).lower()}%"
            
            # Create complete parameter list: title params, skill pattern, title params again, skill pattern again, limit
            complete_params = params + [skill_pattern] + params + [skill_pattern, limit]
            
            query = f"""
            SELECT *, 
                   CASE 
                       WHEN ({title_condition_sql}) THEN 3
                       WHEN LOWER(description) LIKE ? THEN 2
                       ELSE 1
                   END as relevance_score
            FROM {TABLE_NAME}
            WHERE ({title_condition_sql})
               OR LOWER(description) LIKE ?
            ORDER BY relevance_score DESC, scraped_timestamp DESC
            LIMIT ?
            """
            
            cursor.execute(query, complete_params)
            jobs = cursor.fetchall()
            
            # Convert to dictionaries
            columns = [description[0] for description in cursor.description]
            job_matches = [dict(zip(columns, job)) for job in jobs]
            
            return job_matches
            
        except Exception as e:
            logger.error(f"Error getting job matches: {e}")
            logger.error(f"Query: {query if 'query' in locals() else 'Query not constructed'}")
            logger.error(f"Params: {complete_params if 'complete_params' in locals() else 'Params not constructed'}")
            return []
        finally:
            conn.close()


# Convenience functions for integration
def run_profile_job_search(profile_data: Dict) -> Dict:
    """
    Convenience function to run job search based on user profile
    """
    matcher = ProfileJobMatcher()
    return matcher.run_profile_based_search(profile_data)

def get_user_job_matches(user_session_id: str, limit: int = 50) -> List[Dict]:
    """
    Convenience function to get job matches for a user
    """
    matcher = ProfileJobMatcher()
    return matcher.get_profile_job_matches(user_session_id, limit)
