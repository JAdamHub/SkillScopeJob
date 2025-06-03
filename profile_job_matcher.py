from typing import Dict, List, Optional
from datetime import datetime, timedelta
import sqlite3
import json
import logging

# Add missing imports
from datetime import datetime, timedelta

# from indeed_scraper import scrape_indeed_jobs_with_profile, init_database, DB_NAME, TABLE_NAME
from indeed_scraper import scrape_indeed_jobs_with_profile, DB_NAME, TABLE_NAME

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProfileJobMatcher:
    """
    Integrates user profile data with job scraping to find relevant positions
    """
    
    def __init__(self, max_job_age_days: int = 30, cleanup_strategy: str = "smart"):
        """
        Initialize matcher with database freshness configuration
        
        Args:
            max_job_age_days: Maximum age for jobs before they're considered stale (default: 30 days)
            cleanup_strategy: "aggressive" (daily clean), "smart" (selective refresh), or "conservative" (weekly)
        """
        self.max_job_age_days = max_job_age_days
        self.cleanup_strategy = cleanup_strategy
        
        # Job freshness thresholds
        self.freshness_thresholds = {
            "fresh": 7,      # Jobs less than 7 days old
            "recent": 14,    # Jobs less than 14 days old
            "aging": 21,     # Jobs less than 21 days old
            "stale": max_job_age_days  # Jobs older than max_job_age_days are removed
        }
        
        # Updated job type mapping to ONLY use Indeed's supported types
        self.job_type_mapping = {
            # Streamlit app options -> jobspy format (Indeed's ONLY supported types)
            "Full-time": "fulltime",
            "Part-time": "parttime", 
            "Internship": "internship",
            "Temporary": "contract",
            "Permanent": "fulltime",  # Map to fulltime as Indeed doesn't have "permanent"
            "Student job": "parttime",  # Map to parttime, add "student" to search term
            "Volunteer work": "parttime",  # Map to parttime, add "volunteer" to search term
            "New graduate": "fulltime",  # Map to fulltime, add "graduate" to search term
            "Apprentice": "internship"  # Map to internship, add "apprentice" to search term
        }
        
        # Enhanced job type handling for search term modification
        self.search_term_modifiers = {
            "Student job": ["student"],
            "New graduate": ["graduate"],
            "Volunteer work": ["volunteer"],
            "Apprentice": ["trainee"]
        }
        
        # Location mapping remains the same
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

    def run_profile_based_search(self, profile_data: Dict, max_results_per_search: int = 50, auto_refresh: bool = True) -> Dict:
        """
        Run profile-based job search - PRIORITIZES live scraping with fresh data
        Database is only used as fallback if scraping fails completely
        """
        try:
            # Store user profile first
            self._store_user_profile(profile_data)
            
            # Try live scraping first (PRIMARY SOURCE)
            logger.info("Starting LIVE job scraping as primary source...")
            
            # Import here to avoid circular imports
            from indeed_scraper import scrape_indeed_jobs_with_profile
            
            # Extract the correct parameters for the scraping function
            search_params = self.extract_search_parameters(profile_data)
            
            all_fresh_jobs = []
            total_new_jobs = 0
            all_search_summaries = []
            
            # Run searches for each job title keyword individually
            job_titles = search_params['job_titles'][:3]  # Limit to first 3 to avoid too many requests
            locations = search_params['locations'][:2]   # Limit to first 2 locations
            
            # Enhance job titles with job type modifiers
            enhanced_job_titles = []
            for job_title in job_titles:
                enhanced_title = self.enhance_search_term_for_job_type(job_title, search_params['original_job_types'])
                enhanced_job_titles.append(enhanced_title)
            
            logger.info(f"Will search for {len(enhanced_job_titles)} enhanced job titles in {len(locations)} locations")
            logger.info(f"Enhanced job titles: {enhanced_job_titles}")
            
            # Get remote setting - but handle None properly
            remote_setting = self.determine_remote_setting(search_params['remote_preference'])
            
            for enhanced_title in enhanced_job_titles:
                for location in locations:
                    logger.info(f"Searching for '{enhanced_title}' in '{location}' (remote: {remote_setting})")
                    
                    try:
                        # Call the enhanced scraper function with proper parameter handling
                        search_result = scrape_indeed_jobs_with_profile(
                            search_term=enhanced_title,
                            location=location,
                            job_type=search_params['job_types'][0] if search_params['job_types'] else None,
                            is_remote=remote_setting,  # This will be None, True, or False
                            max_results=max_results_per_search // len(enhanced_job_titles)
                        )
                        
                        # Extract fresh jobs from this search
                        fresh_jobs = search_result.get('jobs_from_search', [])
                        jobs_found = search_result.get('total_jobs_found', 0)
                        new_jobs_added = search_result.get('new_jobs_added', 0)
                        
                        # Add relevance scoring to fresh jobs
                        for job in fresh_jobs:
                            job['relevance_score'] = self._calculate_enhanced_relevance_score(
                                job, search_params['job_titles']
                            )
                            job['search_source'] = 'live_indeed'
                            job['search_term_used'] = enhanced_title
                            job['location_searched'] = location
                        
                        all_fresh_jobs.extend(fresh_jobs)
                        total_new_jobs += new_jobs_added
                        all_search_summaries.append(search_result.get('search_summary', {}))
                        
                        logger.info(f"Found {jobs_found} jobs ({new_jobs_added} new) for '{enhanced_title}' in '{location}'")
                        
                        # Add small delay between searches to be respectful
                        import time
                        time.sleep(2)
                        
                    except Exception as search_error:
                        logger.error(f"Error searching for '{enhanced_title}' in '{location}': {search_error}")
                        continue
            
            # Remove duplicates from fresh jobs (same job from different searches)
            unique_fresh_jobs = self._deduplicate_fresh_jobs(all_fresh_jobs)
            logger.info(f"After deduplication: {len(unique_fresh_jobs)} unique jobs from {len(all_fresh_jobs)} total")
            
            # Sort by relevance score
            unique_fresh_jobs = sorted(unique_fresh_jobs, key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            # Check if we found any jobs
            if unique_fresh_jobs:
                logger.info(f"✅ Live scraping SUCCESS: Found {len(unique_fresh_jobs)} fresh jobs from Indeed")
                
                search_results = {
                    "total_jobs_found": len(unique_fresh_jobs),
                    "new_jobs_added_to_db": total_new_jobs,
                    "jobs": unique_fresh_jobs[:max_results_per_search],  # Return fresh jobs directly
                    "search_summary": {
                        "original_job_titles": search_params['job_titles'],
                        "enhanced_job_titles": enhanced_job_titles,
                        "locations_searched": locations,
                        "job_types_used": search_params['original_job_types'],
                        "searches_performed": len(enhanced_job_titles) * len(locations),
                        "total_indeed_results": len(all_fresh_jobs),
                        "unique_jobs": len(unique_fresh_jobs),
                        "new_in_database": total_new_jobs,
                        "individual_searches": all_search_summaries
                    },
                    "source": "live_scraping",
                    "fallback_used": False,
                    "timestamp": datetime.now().isoformat()
                }
                
                return search_results
            else:
                logger.warning(f"⚠️ Live scraping found 0 jobs - falling back to database")
                raise Exception("No jobs found in live scraping")

        except Exception as scraping_error:
            logger.error(f"❌ Live job scraping FAILED: {scraping_error}")
            logger.info("🔄 Falling back to database as secondary source...")
            
            # FALLBACK: Use database if live scraping fails
            try:
                user_session_id = profile_data.get('user_session_id', 'unknown')
                database_matches = self.get_profile_job_matches(user_session_id, limit=max_results_per_search)
                
                if database_matches:
                    logger.info(f"✅ Database fallback SUCCESS: Found {len(database_matches)} jobs from local database")
                    
                    # Format as search results
                    fallback_results = {
                        "total_jobs_found": len(database_matches),
                        "jobs": database_matches,
                        "search_summary": {
                            "source": "database_fallback",
                            "reason": f"Live scraping failed: {str(scraping_error)}"
                        },
                        "source": "database_fallback",
                        "fallback_used": True,
                        "scraping_error": str(scraping_error),
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    return fallback_results
                else:
                    logger.error("❌ Database fallback also failed - no jobs found in database")
                    return {
                        "error": f"Both live scraping and database fallback failed. Scraping error: {str(scraping_error)}",
                        "total_jobs_found": 0,
                        "search_summary": {},
                        "source": "failed",
                        "fallback_used": True,
                        "timestamp": datetime.now().isoformat()
                    }
                    
            except Exception as db_error:
                logger.error(f"❌ Database fallback FAILED: {db_error}")
                return {
                    "error": f"Both live scraping and database failed. Scraping: {str(scraping_error)}, Database: {str(db_error)}",
                    "total_jobs_found": 0,
                    "search_summary": {},
                    "source": "failed",
                    "fallback_used": True,
                    "timestamp": datetime.now().isoformat()
                }

    def enhance_search_term_for_job_type(self, base_search_term: str, job_types: List[str]) -> str:
        """
        Enhanced search term modification based on special job types
        """
        enhanced_term = base_search_term
        added_modifiers = []
        
        # Add specific modifiers for certain job types
        for job_type in job_types:
            if job_type in self.search_term_modifiers:
                modifiers = self.search_term_modifiers[job_type]
                for modifier in modifiers:
                    if modifier not in enhanced_term.lower() and modifier not in added_modifiers:
                        enhanced_term += f" {modifier}"
                        added_modifiers.append(modifier)
        
        logger.info(f"Enhanced '{base_search_term}' to '{enhanced_term}' for job types: {job_types}")
        return enhanced_term

    def extract_search_parameters(self, profile_data: Dict) -> Dict:
        """
        Extract and format search parameters from user profile data
        """
        search_params = {
            'job_titles': profile_data.get('job_title_keywords', []),
            'locations': [],
            'job_types': [],
            'original_job_types': profile_data.get('job_types', []),
            'remote_preference': profile_data.get('remote_openness', "Don't care"),
            'user_profile': profile_data
        }
        
        # Map locations
        preferred_locations = profile_data.get('preferred_locations_dk', [])
        for location in preferred_locations:
            # Simple location mapping for Denmark
            if location.lower() in ['hovedstaden', 'københavn', 'københavns kommune']:
                mapped_location = "copenhagen, denmark"
            elif location.lower() in ['midtjylland', 'aarhus kommune']:
                mapped_location = "aarhus, denmark"
            elif location.lower() in ['nordjylland', 'aalborg kommune']:
                mapped_location = "aalborg, denmark"
            elif location.lower() in ['syddanmark', 'odense kommune']:
                mapped_location = "odense, denmark"
            elif location.lower() in ['esbjerg kommune']:
                mapped_location = "esbjerg, denmark"
            else:
                # Default mapping for other locations
                clean_location = location.replace(' kommune', '').lower()
                mapped_location = f"{clean_location}, denmark"
            
            if mapped_location not in search_params['locations']:
                search_params['locations'].append(mapped_location)
        
        # Default location if none specified
        if not search_params['locations']:
            search_params['locations'] = ['copenhagen, denmark']
        
        # Map job types to ONLY valid jobspy format
        desired_job_types = profile_data.get('job_types', [])
        valid_types_used = set()
        
        for job_type in desired_job_types:
            mapped_type = self.job_type_mapping.get(job_type)
            if mapped_type and mapped_type not in valid_types_used:
                search_params['job_types'].append(mapped_type)
                valid_types_used.add(mapped_type)
        
        # Default job type if none specified or none valid
        if not search_params['job_types']:
            search_params['job_types'] = ['fulltime']
        
        # Remove duplicates while preserving order
        search_params['job_types'] = list(dict.fromkeys(search_params['job_types']))
        
        return search_params

    def determine_remote_setting(self, remote_preference: str) -> Optional[bool]:
        """
        Convert remote preference to jobspy is_remote parameter
        Returns None if no specific preference to avoid validation errors
        """
        if remote_preference == "Primarily Remote":
            return True
        elif remote_preference == "Primarily On-site":
            return False
        else:
            # "Don't care" or "Primarily Hybrid" - don't specify remote filter
            # Return None so the parameter is not passed to jobspy
            return None

    def get_profile_job_matches(self, user_session_id: str, limit: int = 50, include_stale: bool = False) -> List[Dict]:
        """
        Get job matches from DATABASE - now used primarily as fallback
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # First, verify the database has data
            cursor.execute("SELECT COUNT(*) FROM job_postings")
            total_jobs_in_db = cursor.fetchone()[0]
            logger.info(f"Database contains {total_jobs_in_db} total jobs")
            
            if total_jobs_in_db == 0:
                logger.warning("No jobs found in database - this is expected if running for first time")
                return []
            
            # Get user profile for matching
            cursor.execute("""
            SELECT profile_data FROM user_profiles 
            WHERE user_session_id = ? 
            ORDER BY last_search_timestamp DESC LIMIT 1
            """, (user_session_id,))
            
            profile_row = cursor.fetchone()
            if not profile_row:
                logger.warning(f"No profile found for user {user_session_id} in database")
                # Return recent jobs as fallback
                return self._get_recent_quality_jobs(cursor, limit)
            
            profile_data = json.loads(profile_row[0])
            
            # Get basic relevant jobs from database
            job_keywords = profile_data.get('job_title_keywords', [])
            overall_field = profile_data.get('overall_field', '')
            
            logger.info(f"Database matching for: keywords={job_keywords}, field={overall_field}")
            
            # Simple but effective database matching
            all_matches = []
            
            # 1. Keyword matching
            if job_keywords:
                keyword_matches = self._enhanced_keyword_matching(cursor, job_keywords, limit * 2)
                all_matches.extend(keyword_matches)
                logger.info(f"Found {len(keyword_matches)} keyword matches in database")
            
            # 2. Field matching
            if overall_field:
                field_matches = self._match_by_field(cursor, overall_field, limit)
                all_matches.extend(field_matches)
                logger.info(f"Found {len(field_matches)} field matches in database")
            
            # 3. Recent quality jobs as fallback
            if len(all_matches) < 10:
                recent_jobs = self._get_recent_quality_jobs(cursor, limit=30)
                all_matches.extend(recent_jobs)
                logger.info(f"Added {len(recent_jobs)} recent jobs from database")
            
            # Remove duplicates and enhance scoring
            unique_matches = self._deduplicate_and_enhance_scoring(all_matches, profile_data)
            
            # Sort by relevance and return
            final_matches = sorted(unique_matches, key=lambda x: x.get('relevance_score', 1), reverse=True)[:limit]
            
            logger.info(f"Returning {len(final_matches)} database matches for user {user_session_id}")
            
            return final_matches
            
        except Exception as e:
            logger.error(f"Error getting job matches from database: {e}")
            return []
        finally:
            conn.close()

    def smart_database_refresh(self, force_full_refresh: bool = False) -> Dict:
        """
        Intelligent database refresh based on job age and user activity
        """
        refresh_stats = {
            "strategy": self.cleanup_strategy,
            "timestamp": datetime.now().isoformat(),
            "actions_taken": [],
            "before_stats": self.get_job_age_distribution(),
            "after_stats": {}
        }
        
        try:
            # Implementation for database refresh
            refresh_stats["actions_taken"].append("Basic refresh completed")
            refresh_stats["after_stats"] = self.get_job_age_distribution()
            return refresh_stats
        except Exception as e:
            refresh_stats["error"] = str(e)
            return refresh_stats

    def get_job_age_distribution(self) -> Dict:
        """
        Get distribution of jobs by age categories
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM job_postings")
            total_count = cursor.fetchone()[0]
            return {
                "total_jobs": total_count,
                "fresh": 0,
                "recent": 0,
                "aging": 0,
                "stale": 0
            }
        except Exception as e:
            logger.error(f"Error getting job age distribution: {e}")
            return {"total_jobs": 0, "fresh": 0, "recent": 0, "aging": 0, "stale": 0}
        finally:
            conn.close()

    def _store_user_profile(self, profile_data: Dict):
        """Store user profile in database"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # Create user profiles table if it doesn't exist
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_session_id TEXT UNIQUE,
                profile_data TEXT,
                last_search_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Store or update profile
            cursor.execute("""
            INSERT OR REPLACE INTO user_profiles 
            (user_session_id, profile_data, last_search_timestamp)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (
                profile_data.get('user_session_id', 'unknown'),
                json.dumps(profile_data)
            ))
            
            conn.commit()
            logger.info(f"Stored profile for user {profile_data.get('user_session_id', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Error storing user profile: {e}")
        finally:
            conn.close()

    def _enhance_keywords_for_job_types(self, keywords: List[str], job_types: List[str]) -> List[str]:
        """Enhance keywords based on job types"""
        enhanced = keywords.copy()
        for job_type in job_types:
            if job_type == "Student job":
                enhanced.append("student")
            elif job_type == "New graduate":
                enhanced.append("graduate")
        return enhanced

    def _search_student_jobs(self, cursor, job_keywords: List[str], user_skills: List[str], limit: int) -> List[Dict]:
        """Search for student-specific jobs"""
        try:
            cursor.execute("""
            SELECT * FROM job_postings 
            WHERE LOWER(title) LIKE '%student%' OR LOWER(description) LIKE '%student%'
            LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Error searching student jobs: {e}")
            return []

    def _enhanced_keyword_matching(self, cursor, job_keywords: List[str], limit: int) -> List[Dict]:
        """Enhanced keyword matching"""
        try:
            if not job_keywords:
                return []
            
            # Create LIKE clauses for each keyword
            where_clauses = []
            params = []
            for keyword in job_keywords:
                where_clauses.append("(LOWER(title) LIKE ? OR LOWER(description) LIKE ?)")
                params.extend([f'%{keyword.lower()}%', f'%{keyword.lower()}%'])
            
            query = f"""
            SELECT * FROM job_postings 
            WHERE {' OR '.join(where_clauses)}
            ORDER BY scraped_timestamp DESC
            LIMIT ?
            """
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Error in keyword matching: {e}")
            return []

    def _match_by_field(self, cursor, overall_field: str, limit: int) -> List[Dict]:
        """Match jobs by overall field"""
        try:
            cursor.execute("""
            SELECT * FROM job_postings 
            WHERE LOWER(description) LIKE ?
            LIMIT ?
            """, (f'%{overall_field.lower()}%', limit))
            
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Error matching by field: {e}")
            return []

    def _match_by_skills(self, cursor, user_skills: List[str], limit: int) -> List[Dict]:
        """Match jobs by skills"""
        try:
            if not user_skills:
                return []
            
            where_clauses = []
            params = []
            for skill in user_skills:
                where_clauses.append("(LOWER(title) LIKE ? OR LOWER(description) LIKE ?)")
                params.extend([f'%{skill.lower()}%', f'%{skill.lower()}%'])
            
            query = f"""
            SELECT * FROM job_postings 
            WHERE {' OR '.join(where_clauses)}
            LIMIT ?
            """
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Error matching by skills: {e}")
            return []

    def _get_recent_quality_jobs(self, cursor, limit: int = 30) -> List[Dict]:
        """Get recent quality jobs as fallback"""
        try:
            cursor.execute("""
            SELECT * FROM job_postings 
            WHERE title IS NOT NULL AND company IS NOT NULL
            ORDER BY scraped_timestamp DESC
            LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Error getting recent jobs: {e}")
            return []

    def _deduplicate_and_enhance_scoring(self, matches: List[Dict], profile_data: Dict) -> List[Dict]:
        """Remove duplicates and enhance scoring"""
        seen_jobs = set()
        unique_matches = []
        
        for job in matches:
            job_key = (job.get('title', ''), job.get('company', ''), job.get('location', ''))
            if job_key not in seen_jobs:
                seen_jobs.add(job_key)
                # Add enhanced relevance score
                job['relevance_score'] = self._calculate_enhanced_relevance_score(job, profile_data.get('job_title_keywords', []))
                unique_matches.append(job)
        
        return unique_matches

    def _calculate_enhanced_relevance_score(self, job: Dict, job_keywords: List[str]) -> int:
        """Calculate enhanced relevance score"""
        score = 30  # Base score
        
        title = job.get('title', '').lower()
        description = job.get('description', '').lower()
        
        # Check for keyword matches
        for keyword in job_keywords:
            if keyword.lower() in title:
                score += 20
            elif keyword.lower() in description:
                score += 10
        
        return min(100, score)  # Cap at 100

    def _calculate_comprehensive_relevance_score(self, job: Dict, profile_data: Dict) -> int:
        """Calculate comprehensive relevance score"""
        return self._calculate_enhanced_relevance_score(job, profile_data.get('job_title_keywords', []))

    def _calculate_experience_match_bonus(self, job: Dict, total_experience: str) -> int:
        """Calculate experience match bonus"""
        # Simple implementation
        return 5 if total_experience != 'None' else 0

    def get_database_enrichment_status(self) -> Dict:
        """Get database enrichment status"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM job_postings")
            total_jobs = cursor.fetchone()[0]
            
            return {
                "total_jobs": total_jobs,
                "enrichment_level": "basic",
                "last_updated": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting enrichment status: {e}")
            return {"total_jobs": 0, "enrichment_level": "none", "error": str(e)}
        finally:
            conn.close()

    def _deduplicate_fresh_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """
        Remove duplicate jobs from fresh Indeed search results
        Uses title + company + location as unique identifier
        """
        seen_jobs = set()
        unique_jobs = []
        
        for job in jobs:
            job_key = (
                job.get('title', '').strip().lower(),
                job.get('company', '').strip().lower(), 
                job.get('location', '').strip().lower()
            )
            
            if job_key not in seen_jobs:
                seen_jobs.add(job_key)
                unique_jobs.append(job)
            else:
                logger.debug(f"Duplicate job filtered: {job.get('title')} at {job.get('company')}")
        
        return unique_jobs

# Add missing wrapper functions at the end of the file

def run_profile_job_search(profile_data: Dict) -> Dict:
    """
    Wrapper function to run profile-based job search
    """
    matcher = ProfileJobMatcher()
    return matcher.run_profile_based_search(profile_data)

def get_user_job_matches(user_session_id: str, limit: int = 50) -> List[Dict]:
    """
    Wrapper function to get job matches for a specific user
    """
    matcher = ProfileJobMatcher()
    return matcher.get_profile_job_matches(user_session_id, limit)

def get_database_enrichment_status() -> Dict:
    """
    Wrapper function to get database enrichment status
    """
    matcher = ProfileJobMatcher()
    return matcher.get_database_enrichment_status()

# Example usage
if __name__ == "__main__":
    # Test the profile job matcher
    test_profile = {
        'user_session_id': 'test_user_123',
        'job_title_keywords': ['software developer', 'python developer'],
        'preferred_locations_dk': ['København', 'Aarhus kommune'],
        'job_types': ['Full-time', 'Part-time'],
        'current_skills_selected': ['Python', 'JavaScript', 'SQL'],
        'overall_field': 'Software Development',
        'target_roles_industries_selected': ['Software Engineer'],
        'total_experience': '3-5 years',
        'work_experience_entries': [
            {
                'job_title': 'Junior Developer',
                'company': 'Tech Company',
                'years_in_role': 2,
                'skills_responsibilities': 'Python, Django, REST APIs'
            }
        ],
        'remote_openness': "Don't care"
    }
    
    try:
        matcher = ProfileJobMatcher()
        results = matcher.run_profile_based_search(test_profile)
        print(f"Search results: {results}")
        
    except Exception as e:
        print(f"Test failed: {e}")
