import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import sqlite3

from indeed_scraper import scrape_indeed_jobs_with_profile, init_database, DB_NAME, TABLE_NAME

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
            "Student job": ["student", "studiejob", "deltid"],
            "New graduate": ["graduate", "nyuddannet", "junior"],
            "Volunteer work": ["volunteer", "frivillig"],
            "Apprentice": ["apprentice", "lærling", "trainee"]
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
                # Add the first modifier that's not already in the search term
                for modifier in modifiers:
                    if modifier.lower() not in enhanced_term.lower() and modifier not in added_modifiers:
                        enhanced_term = f"{enhanced_term} {modifier}"
                        added_modifiers.append(modifier)
                        break  # Only add one modifier per job type
        
        return enhanced_term

    def extract_search_parameters(self, profile_data: Dict) -> Dict:
        """
        Extract and format search parameters from user profile data
        """
        search_params = {
            'job_titles': profile_data.get('job_title_keywords', []),
            'locations': [],
            'job_types': [],
            'original_job_types': profile_data.get('job_types', []),  # Keep original for enhancement
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
        """
        if remote_preference == "Primarily Remote":
            return True
        elif remote_preference == "Primarily On-site":
            return False
        else:
            # "Don't care" or "Primarily Hybrid" - let jobspy find all types
            return None

    def init_database_with_freshness_tracking(self):
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
        
        conn.commit()
        conn.close()

    def clean_stale_jobs(self) -> Dict:
        """
        Remove jobs that are older than the maximum age threshold
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cutoff_date = datetime.now() - timedelta(days=self.max_job_age_days)
            
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
                logger.info(f"Removed {stale_count} stale jobs older than {self.max_job_age_days} days")
            
            # Get remaining job age distribution
            age_distribution = self.get_job_age_distribution()
            
            return {
                "stale_jobs_removed": stale_count,
                "cutoff_date": cutoff_date.isoformat(),
                "remaining_jobs": age_distribution
            }
            
        except Exception as e:
            logger.error(f"Error cleaning stale jobs: {e}")
            return {"error": str(e)}
        finally:
            conn.close()

    def get_job_age_distribution(self) -> Dict:
        """
        Get distribution of jobs by age categories
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            now = datetime.now()
            distribution = {}
            
            for category, days in self.freshness_thresholds.items():
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
            logger.error(f"Error getting job age distribution: {e}")
            return {}
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
            if self.cleanup_strategy == "aggressive" or force_full_refresh:
                # Daily complete refresh - nuclear option
                refresh_stats["actions_taken"].append("full_database_clear")
                self.clear_entire_database()
                
            elif self.cleanup_strategy == "smart":
                # Selective refresh based on job age
                refresh_stats["actions_taken"].append("stale_job_cleanup")
                cleanup_result = self.clean_stale_jobs()
                refresh_stats["cleanup_result"] = cleanup_result
                
                # Check if we need to refresh specific categories
                age_dist = self.get_job_age_distribution()
                
                if age_dist.get("fresh", 0) < 50 and age_dist.get("total", 0) > 0:
                    # Low fresh jobs - trigger targeted refresh
                    refresh_stats["actions_taken"].append("targeted_fresh_job_scraping")
                    
            elif self.cleanup_strategy == "conservative":
                # Weekly cleanup only
                last_cleanup = self.get_last_cleanup_date()
                if not last_cleanup or (datetime.now() - last_cleanup).days >= 7:
                    refresh_stats["actions_taken"].append("weekly_cleanup")
                    cleanup_result = self.clean_stale_jobs()
                    refresh_stats["cleanup_result"] = cleanup_result
                    self.record_cleanup_date()
            
            # Always update freshness tracking
            self.init_database_with_freshness_tracking()
            refresh_stats["after_stats"] = self.get_job_age_distribution()
            
            logger.info(f"Database refresh completed: {refresh_stats['actions_taken']}")
            return refresh_stats
            
        except Exception as e:
            logger.error(f"Error in smart database refresh: {e}")
            refresh_stats["error"] = str(e)
            return refresh_stats

    def clear_entire_database(self):
        """
        Nuclear option: Clear entire job database for fresh start
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute(f"DELETE FROM {TABLE_NAME}")
            conn.commit()
            logger.info("Entire job database cleared for fresh start")
        except Exception as e:
            logger.error(f"Error clearing database: {e}")
        finally:
            conn.close()

    def get_last_cleanup_date(self) -> Optional[datetime]:
        """
        Get the last cleanup date from metadata table
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # Create metadata table if it doesn't exist
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS database_metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            cursor.execute("""
            SELECT value FROM database_metadata 
            WHERE key = 'last_cleanup_date'
            """)
            
            result = cursor.fetchone()
            if result:
                return datetime.fromisoformat(result[0])
            return None
            
        except Exception as e:
            logger.error(f"Error getting last cleanup date: {e}")
            return None
        finally:
            conn.close()

    def record_cleanup_date(self):
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
        except Exception as e:
            logger.error(f"Error recording cleanup date: {e}")
        finally:
            conn.close()

    def get_database_health_report(self) -> Dict:
        """
        Comprehensive database health and freshness report
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "configuration": {
                "max_job_age_days": self.max_job_age_days,
                "cleanup_strategy": self.cleanup_strategy,
                "freshness_thresholds": self.freshness_thresholds
            }
        }
        
        # Job age distribution
        report["age_distribution"] = self.get_job_age_distribution()
        
        # Enrichment status
        report["enrichment_status"] = self.get_database_enrichment_status()
        
        # Cleanup history
        report["last_cleanup"] = self.get_last_cleanup_date()
        
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
        
        return report

    def run_profile_based_search(self, profile_data: Dict, max_results_per_search: int = 50, auto_refresh: bool = True) -> Dict:
        """
        Run job searches based on user profile with automatic database freshness management
        """
        logger.info("Starting profile-based job search with freshness management")
        
        # Optional automatic refresh before search
        if auto_refresh:
            refresh_result = self.smart_database_refresh()
            logger.info(f"Pre-search refresh: {refresh_result.get('actions_taken', [])}")
        
        # Initialize database with freshness tracking
        self.init_database_with_freshness_tracking()
        init_database()
        
        # Extract search parameters
        search_params = self.extract_search_parameters(profile_data)
        logger.info(f"Search parameters: {search_params}")
        
        # Validate job types are supported
        supported_types = ['fulltime', 'parttime', 'internship', 'contract']
        invalid_types = [jt for jt in search_params['job_types'] if jt not in supported_types]
        if invalid_types:
            logger.warning(f"Invalid job types detected and will be filtered: {invalid_types}")
            search_params['job_types'] = [jt for jt in search_params['job_types'] if jt in supported_types]
        
        if not search_params['job_types']:
            logger.warning("No valid job types found, defaulting to fulltime")
            search_params['job_types'] = ['fulltime']
        
        # Store user profile in database for reference
        self._store_user_profile(profile_data)
        
        # Check existing matches before scraping
        user_session_id = profile_data.get('user_session_id', 'unknown')
        existing_matches_before = self.get_profile_job_matches(user_session_id, limit=1000)
        existing_count_before = len(existing_matches_before) if existing_matches_before else 0
        
        total_inserted = 0
        search_results = {
            'total_jobs_found': 0,
            'existing_matches_before_search': existing_count_before,
            'existing_matches_after_search': 0,  # Will be updated after scraping
            'searches_performed': [],
            'profile_summary': {
                'user_id': profile_data.get('user_session_id', 'unknown'),
                'target_roles': search_params['job_titles'],
                'locations': search_params['locations'],
                'job_types': search_params['job_types'],
                'original_job_types': search_params['original_job_types'],
                'remote_preference': search_params['remote_preference']
            }
        }
        
        logger.info(f"Found {existing_count_before} existing relevant jobs before scraping")
        
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
                # Use the first valid job type
                primary_job_type = search_params['job_types'][0]
                
                # Enhance search term based on original job types
                enhanced_job_title = self.enhance_search_term_for_job_type(
                    job_title, 
                    search_params['original_job_types']
                )
                
                search_info = {
                    'job_title': job_title,
                    'enhanced_job_title': enhanced_job_title,
                    'location': location, 
                    'job_type': primary_job_type,
                    'valid_job_type': primary_job_type in supported_types,
                    'original_job_types': search_params['original_job_types'],
                    'timestamp': datetime.now().isoformat(),
                    'jobs_found': 0
                }
                
                try:
                    logger.info(f"Searching: '{enhanced_job_title}' | {location} | {primary_job_type}")
                    
                    # Determine remote setting
                    is_remote = self.determine_remote_setting(search_params['remote_preference'])
                    
                    # Use enhanced scraper with validated parameters
                    inserted_count = scrape_indeed_jobs_with_profile(
                        search_term=enhanced_job_title,
                        location=location,
                        job_type=primary_job_type,
                        is_remote=is_remote,
                        max_results=max_results_per_search
                    )
                    
                    search_info['jobs_found'] = inserted_count
                    total_inserted += inserted_count
                    
                    logger.info(f"Found {inserted_count} new jobs for '{enhanced_job_title}' in {location}")
                    
                    # Fallback strategy if enhanced search finds nothing
                    if inserted_count == 0 and enhanced_job_title != job_title:
                        logger.info(f"Retrying with basic search term: '{job_title}'")
                        try:
                            fallback_count = scrape_indeed_jobs_with_profile(
                                search_term=job_title,
                                location=location,
                                job_type=primary_job_type,
                                is_remote=is_remote,
                                max_results=max_results_per_search
                            )
                            search_info['fallback_jobs_found'] = fallback_count
                            total_inserted += fallback_count
                            logger.info(f"Fallback search found {fallback_count} jobs")
                        except Exception as fallback_error:
                            logger.error(f"Fallback search failed: {fallback_error}")
                    
                    # Respectful delay between searches
                    import time
                    time.sleep(3)
                    
                except Exception as e:
                    logger.error(f"Error in search '{enhanced_job_title}'/{location}/{primary_job_type}: {e}")
                    search_info['error'] = str(e)
                
                search_results['searches_performed'].append(search_info)
        
        # After all searches, check total matches again
        existing_matches_after = self.get_profile_job_matches(user_session_id, limit=1000)
        existing_count_after = len(existing_matches_after) if existing_matches_after else 0
        
        search_results['total_jobs_found'] = total_inserted
        search_results['existing_matches_after_search'] = existing_count_after
        
        # Log comprehensive summary
        logger.info(f"Profile-based search completed:")
        logger.info(f"  - New jobs scraped: {total_inserted}")
        logger.info(f"  - Existing matches before: {existing_count_before}")
        logger.info(f"  - Total relevant matches after: {existing_count_after}")
        
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

    def get_profile_job_matches(self, user_session_id: str, limit: int = 50, include_stale: bool = False) -> List[Dict]:
        """
        Get job matches with freshness filtering
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # Add freshness filtering to existing query
            freshness_condition = ""
            if not include_stale:
                cutoff_date = datetime.now() - timedelta(days=self.max_job_age_days)
                freshness_condition = f"AND scraped_timestamp >= '{cutoff_date.isoformat()}'"
            
            # Get user profile
            cursor.execute("""
            SELECT profile_data FROM user_profiles 
            WHERE user_session_id = ? 
            ORDER BY last_search_timestamp DESC LIMIT 1
            """, (user_session_id,))
            
            profile_row = cursor.fetchone()
            if not profile_row:
                logger.warning(f"No profile found for user {user_session_id}")
                return []
            
            profile_data = json.loads(profile_row[0])
            job_titles = profile_data.get('job_title_keywords', [])
            user_skills = profile_data.get('current_skills_selected', []) + profile_data.get('current_skills_custom', [])
            overall_field = profile_data.get('overall_field', '')
            
            logger.info(f"Profile matching criteria - Keywords: {job_titles}, Skills: {user_skills[:3]}, Field: {overall_field}")
            
            if not job_titles:
                logger.warning("No job title keywords found in profile")
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
            
            # Enhanced query with better scoring
            query = f"""
            SELECT *, 
                   CASE 
                       WHEN ({title_condition_sql}) THEN 3
                       WHEN LOWER(company_industry) LIKE ? AND ? != '%' THEN 2
                       WHEN LOWER(description) LIKE ? AND ? != '%' THEN 2
                       WHEN LOWER(company_description) LIKE ? AND ? != '%' THEN 1
                       ELSE 1
                   END as relevance_score,
                   CASE 
                       WHEN company_industry IS NOT NULL AND company_industry != '' THEN 1
                       ELSE 0
                   END as has_enriched_data,
                   CASE 
                       WHEN julianday('now') - julianday(scraped_timestamp) <= 7 THEN 'fresh'
                       WHEN julianday('now') - julianday(scraped_timestamp) <= 14 THEN 'recent'
                       WHEN julianday('now') - julianday(scraped_timestamp) <= 21 THEN 'aging'
                       ELSE 'stale'
                   END as job_age_category,
                   ROUND(julianday('now') - julianday(scraped_timestamp)) as days_old
            FROM {TABLE_NAME}
            WHERE ({title_condition_sql})
               OR (LOWER(company_industry) LIKE ? AND ? != '%')
               OR (LOWER(description) LIKE ? AND ? != '%')
               OR (LOWER(company_description) LIKE ? AND ? != '%')
               {freshness_condition}
            ORDER BY relevance_score DESC, has_enriched_data DESC, 
                     CASE job_age_category 
                         WHEN 'fresh' THEN 1 
                         WHEN 'recent' THEN 2 
                         WHEN 'aging' THEN 3 
                         ELSE 4 
                     END,
                     scraped_timestamp DESC
            LIMIT ?
            """
            
            # Build complete parameter list - handle empty patterns carefully
            skill_pattern = f"%{skill_keywords}%" if skill_keywords.strip() else "%none%"
            industry_pattern_safe = industry_pattern if overall_field else "%none%"
            
            complete_params = (
                params +  # Title conditions for CASE
                [industry_pattern_safe, overall_field] +  # Industry for CASE with check
                [skill_pattern, skill_keywords] +  # Skills for description CASE with check  
                [skill_pattern, skill_keywords] +  # Skills for company_description CASE with check
                params +  # Title conditions for WHERE
                [industry_pattern_safe, overall_field] +  # Industry for WHERE with check
                [skill_pattern, skill_keywords] +  # Skills for description WHERE with check
                [skill_pattern, skill_keywords] +  # Skills for company_description WHERE with check
                [limit]
            )
            
            logger.info(f"Executing database query with {len(complete_params)} parameters")
            cursor.execute(query, complete_params)
            jobs = cursor.fetchall()
            
            # Convert to dictionaries
            columns = [description[0] for description in cursor.description]
            job_matches = [dict(zip(columns, job)) for job in jobs]
            
            # Log detailed matching statistics
            enriched_count = sum(1 for job in job_matches if job.get('has_enriched_data'))
            score_distribution = {}
            for job in job_matches:
                score = job.get('relevance_score', 1)
                score_distribution[score] = score_distribution.get(score, 0) + 1
            
            logger.info(f"Database query results for user {user_session_id}:")
            logger.info(f"  - Total matches found: {len(job_matches)}")
            logger.info(f"  - Jobs with enriched data: {enriched_count}/{len(job_matches)}")
            logger.info(f"  - Score distribution: {score_distribution}")
            
            # Ensure we return the jobs even if scoring isn't perfect
            if not job_matches and total_jobs_in_db > 0:
                logger.warning("No matches found with current criteria, trying broader search...")
                
                # Fallback: just search by job titles without additional criteria
                fallback_query = f"""
                SELECT *, 2 as relevance_score, 0 as has_enriched_data
                FROM {TABLE_NAME}
                WHERE {title_condition_sql}
                ORDER BY scraped_timestamp DESC
                LIMIT ?
                """
                
                cursor.execute(fallback_query, params + [limit])
                fallback_jobs = cursor.fetchall()
                job_matches = [dict(zip(columns, job)) for job in fallback_jobs]
                
                logger.info(f"Fallback search found {len(job_matches)} matches")
            
            return job_matches
            
        except Exception as e:
            logger.error(f"Error getting job matches from database: {e}")
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

def run_profile_job_search_with_refresh(profile_data: Dict, cleanup_strategy: str = "smart") -> Dict:
    """
    Run job search with intelligent database refresh
    """
    matcher = ProfileJobMatcher(cleanup_strategy=cleanup_strategy)
    return matcher.run_profile_based_search(profile_data, auto_refresh=True)

def get_database_health_report(max_job_age_days: int = 30) -> Dict:
    """
    Get comprehensive database health report
    """
    matcher = ProfileJobMatcher(max_job_age_days=max_job_age_days)
    return matcher.get_database_health_report()

def cleanup_stale_jobs(max_job_age_days: int = 30) -> Dict:
    """
    Clean up stale jobs from database
    """
    matcher = ProfileJobMatcher(max_job_age_days=max_job_age_days)
    return matcher.clean_stale_jobs()

def force_database_refresh() -> Dict:
    """
    Force complete database refresh (nuclear option)
    """
    matcher = ProfileJobMatcher(cleanup_strategy="aggressive")
    return matcher.smart_database_refresh(force_full_refresh=True)
