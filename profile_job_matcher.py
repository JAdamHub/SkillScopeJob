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
        Get job matches for a specific user profile with relevance scoring using enriched data
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
            user_skills = profile_data.get('current_skills_selected', []) + profile_data.get('current_skills_custom', [])
            overall_field = profile_data.get('overall_field', '')
            
            if not job_titles:
                return []
            
            # Build comprehensive matching query using enriched data
            title_conditions = []
            params = []
            
            # Add title matching conditions
            for title in job_titles:
                title_conditions.append("LOWER(title) LIKE ?")
                params.append(f"%{title.lower()}%")
            
            title_condition_sql = " OR ".join(title_conditions)
            
            # Create skills pattern for description matching
            skill_keywords = " ".join(user_skills[:5]).lower() if user_skills else ""
            
            # Create industry pattern matching
            industry_pattern = f"%{overall_field.lower()}%" if overall_field else "%"
            
            query = f"""
            SELECT *, 
                   CASE 
                       WHEN ({title_condition_sql}) THEN 5
                       WHEN LOWER(company_industry) LIKE ? THEN 4
                       WHEN LOWER(description) LIKE ? THEN 3
                       WHEN LOWER(company_description) LIKE ? THEN 2
                       ELSE 1
                   END as relevance_score,
                   CASE 
                       WHEN company_industry IS NOT NULL AND company_industry != '' THEN 1
                       ELSE 0
                   END as has_enriched_data
            FROM {TABLE_NAME}
            WHERE ({title_condition_sql})
               OR LOWER(company_industry) LIKE ?
               OR LOWER(description) LIKE ?
               OR LOWER(company_description) LIKE ?
            ORDER BY relevance_score DESC, has_enriched_data DESC, scraped_timestamp DESC
            LIMIT ?
            """
            
            # Build complete parameter list:
            # 1. Title conditions (for relevance scoring)
            # 2. Industry pattern (for relevance scoring)  
            # 3. Skills pattern (for relevance scoring)
            # 4. Skills pattern (for company description relevance scoring)
            # 5. Title conditions again (for WHERE clause)
            # 6. Industry pattern (for WHERE clause)
            # 7. Skills pattern (for WHERE clause)
            # 8. Skills pattern (for company description WHERE clause)
            # 9. Limit
            complete_params = (
                params +  # Title conditions for CASE
                [industry_pattern] +  # Industry for CASE
                [f"%{skill_keywords}%"] +  # Skills for description CASE
                [f"%{skill_keywords}%"] +  # Skills for company_description CASE
                params +  # Title conditions for WHERE
                [industry_pattern] +  # Industry for WHERE
                [f"%{skill_keywords}%"] +  # Skills for description WHERE
                [f"%{skill_keywords}%"] +  # Skills for company_description WHERE
                [limit]
            )
            
            cursor.execute(query, complete_params)
            jobs = cursor.fetchall()
            
            # Convert to dictionaries
            columns = [description[0] for description in cursor.description]
            job_matches = [dict(zip(columns, job)) for job in jobs]
            
            # Log matching statistics
            enriched_count = sum(1 for job in job_matches if job.get('has_enriched_data'))
            logger.info(f"Found {len(job_matches)} job matches for user {user_session_id}")
            logger.info(f"Jobs with enriched data: {enriched_count}/{len(job_matches)}")
            
            return job_matches
            
        except Exception as e:
            logger.error(f"Error getting job matches: {e}")
            logger.error(f"Profile data keys: {list(profile_data.keys()) if 'profile_data' in locals() else 'Profile not loaded'}")
            return []
        finally:
            conn.close()

    def get_database_enrichment_status(self) -> Dict:
        """
        Get statistics about database enrichment status
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # Total records
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            total_records = cursor.fetchone()[0]
            
            # Records with enriched company info
            cursor.execute(f"""
            SELECT COUNT(*) FROM {TABLE_NAME} 
            WHERE company_industry IS NOT NULL AND company_industry != ''
            """)
            enriched_industry = cursor.fetchone()[0]
            
            cursor.execute(f"""
            SELECT COUNT(*) FROM {TABLE_NAME} 
            WHERE company_description IS NOT NULL AND company_description != ''
            """)
            enriched_description = cursor.fetchone()[0]
            
            # Records with company info
            cursor.execute(f"""
            SELECT COUNT(*) FROM {TABLE_NAME} 
            WHERE company IS NOT NULL AND company != ''
            """)
            has_company = cursor.fetchone()[0]
            
            # Recent scraping activity
            cursor.execute(f"""
            SELECT COUNT(*) FROM {TABLE_NAME} 
            WHERE date(scraped_timestamp) >= date('now', '-7 days')
            """)
            recent_jobs = cursor.fetchone()[0]
            
            return {
                'total_records': total_records,
                'has_company': has_company,
                'enriched_industry': enriched_industry,
                'enriched_description': enriched_description,
                'enrichment_percentage': round((enriched_industry / total_records * 100) if total_records > 0 else 0, 1),
                'recent_jobs_7_days': recent_jobs
            }
            
        except Exception as e:
            logger.error(f"Error getting enrichment status: {e}")
            return {}
        finally:
            conn.close()

    def get_enhanced_job_matches(self, user_session_id: str, limit: int = 50, 
                                filter_enriched_only: bool = False) -> List[Dict]:
        """
        Get job matches with enhanced filtering options for enriched data
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
            user_skills = profile_data.get('current_skills_selected', []) + profile_data.get('current_skills_custom', [])
            overall_field = profile_data.get('overall_field', '')
            target_roles = profile_data.get('target_roles_industries_selected', []) + profile_data.get('target_roles_industries_custom', [])
            
            if not job_titles:
                return []
            
            # Build enhanced query
            where_conditions = []
            params = []
            
            # Title matching
            title_conditions = []
            for title in job_titles:
                title_conditions.append("LOWER(title) LIKE ?")
                params.append(f"%{title.lower()}%")
            
            if title_conditions:
                where_conditions.append(f"({' OR '.join(title_conditions)})")
            
            # Industry matching using enriched data
            if overall_field:
                where_conditions.append("LOWER(company_industry) LIKE ?")
                params.append(f"%{overall_field.lower()}%")
            
            # Target roles matching
            if target_roles:
                role_conditions = []
                for role in target_roles:
                    role_conditions.append("(LOWER(title) LIKE ? OR LOWER(company_industry) LIKE ?)")
                    params.extend([f"%{role.lower()}%", f"%{role.lower()}%"])
                if role_conditions:
                    where_conditions.append(f"({' OR '.join(role_conditions)})")
            
            # Skills matching in description
            if user_skills:
                skill_condition = " OR ".join(["LOWER(description) LIKE ?" for _ in user_skills[:3]])
                where_conditions.append(f"({skill_condition})")
                params.extend([f"%{skill.lower()}%" for skill in user_skills[:3]])
            
            # Filter for enriched data only if requested
            if filter_enriched_only:
                where_conditions.append("company_industry IS NOT NULL AND company_industry != ''")
            
            where_clause = " OR ".join(where_conditions) if where_conditions else "1=1"
            
            # Enhanced relevance scoring
            query = f"""
            SELECT *, 
                   CASE 
                       WHEN LOWER(title) LIKE ? THEN 10
                       WHEN LOWER(company_industry) = LOWER(?) THEN 8
                       WHEN LOWER(company_industry) LIKE ? THEN 6
                       WHEN LOWER(description) LIKE ? THEN 4
                       WHEN LOWER(company_description) LIKE ? THEN 3
                       ELSE 1
                   END as relevance_score,
                   CASE 
                       WHEN company_industry IS NOT NULL AND company_industry != '' 
                            AND company_description IS NOT NULL AND company_description != '' THEN 2
                       WHEN company_industry IS NOT NULL AND company_industry != '' THEN 1
                       ELSE 0
                   END as enrichment_level
            FROM {TABLE_NAME}
            WHERE {where_clause}
            ORDER BY relevance_score DESC, enrichment_level DESC, scraped_timestamp DESC
            LIMIT ?
            """
            
            # Parameters for relevance scoring
            primary_title = job_titles[0] if job_titles else ""
            skill_pattern = f"%{' '.join(user_skills[:3]).lower()}%" if user_skills else "%"
            
            relevance_params = [
                f"%{primary_title.lower()}%",  # Title exact match
                overall_field,  # Industry exact match
                f"%{overall_field.lower()}%",  # Industry partial match
                skill_pattern,  # Skills in description
                skill_pattern   # Skills in company description
            ]
            
            all_params = relevance_params + params + [limit]
            
            cursor.execute(query, all_params)
            jobs = cursor.fetchall()
            
            # Convert to dictionaries
            columns = [description[0] for description in cursor.description]
            job_matches = [dict(zip(columns, job)) for job in jobs]
            
            return job_matches
            
        except Exception as e:
            logger.error(f"Error getting enhanced job matches: {e}")
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

def get_enhanced_user_job_matches(user_session_id: str, limit: int = 50, filter_enriched_only: bool = False) -> List[Dict]:
    """
    Convenience function to get enhanced job matches for a user
    """
    matcher = ProfileJobMatcher()
    return matcher.get_enhanced_job_matches(user_session_id, limit, filter_enriched_only)

def get_database_enrichment_status() -> Dict:
    """
    Convenience function to get database enrichment status
    """
    matcher = ProfileJobMatcher()
    return matcher.get_database_enrichment_status()
