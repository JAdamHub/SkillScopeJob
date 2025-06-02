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
                for modifier in modifiers:
                    if modifier not in enhanced_term.lower() and modifier not in added_modifiers:
                        enhanced_term += f" {modifier}"
                        added_modifiers.append(modifier)
        
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
                cursor.execute(f"""
                DELETE FROM {TABLE_NAME} 
                WHERE scraped_timestamp < ?
                """, (cutoff_date.isoformat(),))
                conn.commit()
                logger.info(f"Removed {stale_count} stale jobs older than {cutoff_date}")
            
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
                cutoff_date = now - timedelta(days=days)
                cursor.execute(f"""
                SELECT COUNT(*) FROM {TABLE_NAME} 
                WHERE scraped_timestamp >= ?
                """, (cutoff_date.isoformat(),))
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
                cleanup_result = self.clean_stale_jobs()
                refresh_stats["actions_taken"].append(f"Cleaned {cleanup_result.get('stale_jobs_removed', 0)} stale jobs")
                
            elif self.cleanup_strategy == "smart":
                age_dist = self.get_job_age_distribution()
                if age_dist.get("stale", 0) > 50:  # Clean if more than 50 stale jobs
                    cleanup_result = self.clean_stale_jobs()
                    refresh_stats["actions_taken"].append(f"Smart cleanup: {cleanup_result.get('stale_jobs_removed', 0)} jobs removed")
                    
            elif self.cleanup_strategy == "conservative":
                last_cleanup = self.get_last_cleanup_date()
                if not last_cleanup or (datetime.now() - last_cleanup).days >= 7:
                    cleanup_result = self.clean_stale_jobs()
                    refresh_stats["actions_taken"].append(f"Weekly cleanup: {cleanup_result.get('stale_jobs_removed', 0)} jobs removed")
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
                for job_type in search_params['job_types']:
                    # Enhance search term based on job types
                    enhanced_job_title = self.enhance_search_term_for_job_type(job_title, search_params['original_job_types'])
                    
                    search_info = {
                        'original_job_title': job_title,
                        'enhanced_job_title': enhanced_job_title,
                        'location': location,
                        'job_type': job_type,
                        'remote_setting': self.determine_remote_setting(search_params['remote_preference'])
                    }
                    
                    logger.info(f"Searching for: {enhanced_job_title} in {location} ({job_type})")
                    
                    try:
                        # Run the actual job search
                        results = scrape_indeed_jobs_with_profile(
                            job_title=enhanced_job_title,
                            location=location,
                            job_type=job_type,
                            is_remote=search_info['remote_setting'],
                            max_results=max_results_per_search
                        )
                        
                        jobs_found = results.get('jobs_inserted', 0)
                        total_inserted += jobs_found
                        
                        search_info.update({
                            'jobs_found': jobs_found,
                            'search_successful': True,
                            'error': None
                        })
                        
                        logger.info(f"Search completed: {jobs_found} jobs found for {enhanced_job_title}")
                        
                    except Exception as e:
                        logger.error(f"Search failed for {enhanced_job_title}: {e}")
                        search_info.update({
                            'jobs_found': 0,
                            'search_successful': False,
                            'error': str(e)
                        })
                    
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
        IMPROVED job matching using multi-field search with better relevance scoring
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # First, verify the database has data
            cursor.execute("SELECT COUNT(*) FROM job_postings")
            total_jobs_in_db = cursor.fetchone()[0]
            logger.info(f"Total jobs in job_postings table: {total_jobs_in_db}")
            
            if total_jobs_in_db == 0:
                logger.warning("No jobs found in database")
                return []
            
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
            
            # Extract matching criteria
            job_keywords = profile_data.get('job_title_keywords', [])
            user_skills = profile_data.get('current_skills_selected', []) + profile_data.get('current_skills_custom', [])
            overall_field = profile_data.get('overall_field', '')
            job_types = profile_data.get('job_types', [])
            total_experience = profile_data.get('total_experience', 'None')
            
            logger.info(f"Enhanced matching: keywords={job_keywords}, skills={user_skills[:5]}, field={overall_field}")
            
            # ENHANCED MULTI-FIELD MATCHING STRATEGY
            all_matches = []
            
            # 1. PRIMARY: Multi-field keyword matching (title, description, search_term)
            if job_keywords:
                keyword_matches = self._enhanced_keyword_matching(cursor, job_keywords, limit * 3)
                all_matches.extend(keyword_matches)
                logger.info(f"Found {len(keyword_matches)} keyword matches")
            
            # 2. SECONDARY: Field-based matching (using overall_field)
            if overall_field:
                field_matches = self._match_by_field(cursor, overall_field, limit)
                all_matches.extend(field_matches)
                logger.info(f"Found {len(field_matches)} field matches")
            
            # 3. TERTIARY: Skill-based matching
            if user_skills:
                skill_matches = self._match_by_skills(cursor, user_skills, limit)
                all_matches.extend(skill_matches)
                logger.info(f"Found {len(skill_matches)} skill matches")
            
            # 4. FALLBACK: Recent high-quality jobs
            if len(all_matches) < 20:
                recent_jobs = self._get_recent_quality_jobs(cursor, limit=30)
                all_matches.extend(recent_jobs)
                logger.info(f"Added {len(recent_jobs)} recent quality jobs as fallback")
            
            # Remove duplicates and enhance scoring
            unique_matches = self._deduplicate_and_enhance_scoring(all_matches, profile_data)
            
            # Sort by enhanced relevance score and return
            final_matches = sorted(unique_matches, key=lambda x: x.get('relevance_score', 1), reverse=True)[:limit]
            
            logger.info(f"Returning {len(final_matches)} job matches with enhanced scoring for user {user_session_id}")
            
            return final_matches
            
        except Exception as e:
            logger.error(f"Error getting job matches: {e}", exc_info=True)
            return []
        finally:
            conn.close()

    def _enhanced_keyword_matching(self, cursor, job_keywords: List[str], limit: int) -> List[Dict]:
        """Enhanced keyword matching across title, description, and search_term"""
        matches = []
        
        try:
            # Create comprehensive search query
            search_conditions = []
            params = []
            
            for keyword in job_keywords[:5]:  # Limit to first 5 keywords
                keyword_lower = keyword.lower()
                # Search in multiple fields with different weights
                search_conditions.append("""
                (title LIKE ? OR description LIKE ? OR search_term LIKE ? OR company_industry LIKE ?)
                """)
                # Add the same keyword 4 times for the 4 fields
                params.extend([f"%{keyword_lower}%"] * 4)
            
            if not search_conditions:
                return matches

            query = f"""
            SELECT *, 
                   CASE 
                       WHEN title LIKE ? THEN 'title_match'
                       WHEN search_term LIKE ? THEN 'search_term_match'
                       WHEN description LIKE ? THEN 'description_match'
                       WHEN company_industry LIKE ? THEN 'industry_match'
                       ELSE 'other_match'
                   END as match_type_detail
            FROM job_postings 
            WHERE ({' OR '.join(search_conditions)})
            AND job_status = 'active'
            ORDER BY 
                CASE 
                    WHEN title LIKE ? THEN 1
                    WHEN search_term LIKE ? THEN 2
                    WHEN company_industry LIKE ? THEN 3
                    ELSE 4
                END,
                scraped_timestamp DESC
            LIMIT ?
            """
            
            # Add parameters for the CASE statements and ORDER BY
            first_keyword = f"%{job_keywords[0].lower()}%"
            case_params = [first_keyword] * 7  # For CASE and ORDER BY clauses
            all_params = params + case_params + [limit]
            
            cursor.execute(query, all_params)
            rows = cursor.fetchall()
            
            # Convert to dictionaries
            column_names = [description[0] for description in cursor.description]
            for row in rows:
                job_dict = dict(zip(column_names, row))
                job_dict['match_type'] = 'enhanced_keyword'
                job_dict['relevance_score'] = self._calculate_enhanced_relevance_score(job_dict, job_keywords)
                matches.append(job_dict)
            
            logger.info(f"Enhanced keyword matching found {len(matches)} jobs")
            
        except Exception as e:
            logger.error(f"Error in enhanced keyword matching: {e}")

        return matches

    def _match_by_field(self, cursor, overall_field: str, limit: int) -> List[Dict]:
        """Match jobs by overall field/industry"""
        matches = []
        
        # Map overall fields to industry keywords
        field_keywords = {
            'Data Science & AI': ['data', 'analytics', 'ai', 'machine learning', 'artificial intelligence', 'statistics'],
            'Software Development': ['software', 'developer', 'programming', 'engineer', 'coding', 'tech'],
            'Project Management': ['project', 'manager', 'scrum', 'agile', 'coordination'],
            'UX/UI Design': ['design', 'ux', 'ui', 'user experience', 'graphic', 'creative'],
            'Marketing & Sales': ['marketing', 'sales', 'business development', 'customer', 'communication'],
            'Finance & Economics': ['finance', 'accounting', 'economics', 'financial', 'banking'],
            'Engineering': ['engineering', 'technical', 'mechanical', 'civil', 'electrical'],
            'Healthcare': ['health', 'medical', 'healthcare', 'clinical', 'pharmaceutical']
        }
        
        keywords = field_keywords.get(overall_field, [])
        if not keywords:
            return matches
        
        try:
            # Search in company_industry and description
            search_conditions = []
            params = []
            
            for keyword in keywords[:4]:  # Use top 4 keywords for the field
                search_conditions.append("(company_industry LIKE ? OR description LIKE ? OR title LIKE ?)")
                params.extend([f"%{keyword}%"] * 3)
            
            query = f"""
            SELECT * FROM job_postings 
            WHERE ({' OR '.join(search_conditions)})
            AND job_status = 'active'
            ORDER BY scraped_timestamp DESC
            LIMIT ?
            """
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            column_names = [description[0] for description in cursor.description]
            for row in rows:
                job_dict = dict(zip(column_names, row))
                job_dict['match_type'] = 'field_match'
                job_dict['relevance_score'] = 50  # Base score for field matches
                matches.append(job_dict)
            
        except Exception as e:
            logger.error(f"Error in field matching: {e}")
        
        return matches

    def _match_by_skills(self, cursor, user_skills: List[str], limit: int) -> List[Dict]:
        """Match jobs by user skills in description"""
        matches = []
        
        try:
            search_conditions = []
            params = []
            
            for skill in user_skills[:8]:  # Use top 8 skills
                search_conditions.append("description LIKE ?")
                params.append(f"%{skill.lower()}%")
            
            if not search_conditions:
                return matches
            
            query = f"""
            SELECT * FROM job_postings 
            WHERE ({' OR '.join(search_conditions)})
            AND job_status = 'active'
            ORDER BY scraped_timestamp DESC
            LIMIT ?
            """
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            column_names = [description[0] for description in cursor.description]
            for row in rows:
                job_dict = dict(zip(column_names, row))
                job_dict['match_type'] = 'skill_match'
                job_dict['relevance_score'] = 45  # Base score for skill matches
                matches.append(job_dict)
                
        except Exception as e:
            logger.error(f"Error in skill matching: {e}")
        
        return matches

    def _get_recent_quality_jobs(self, cursor, limit: int = 30) -> List[Dict]:
        """Get recent, high-quality jobs as fallback"""
        try:
            # Get recent jobs from reputable companies or with good indicators
            query = f"""
            SELECT * FROM job_postings 
            WHERE job_status = 'active'
            AND (
                company_industry IS NOT NULL 
                OR company IN (
                    SELECT company FROM job_postings 
                    WHERE company_industry IN ('Technology', 'Finance', 'Healthcare', 'Energy', 'Consulting')
                    GROUP BY company 
                    HAVING COUNT(*) >= 2
                )
            )
            ORDER BY scraped_timestamp DESC
            LIMIT ?
            """
            
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            
            column_names = [description[0] for description in cursor.description]
            recent_jobs = []
            for row in rows:
                job_dict = dict(zip(column_names, row))
                job_dict['match_type'] = 'recent_quality'
                job_dict['relevance_score'] = 35  # Lower base score for fallback jobs
                recent_jobs.append(job_dict)
            
            return recent_jobs
            
        except Exception as e:
            logger.error(f"Error getting recent quality jobs: {e}")
            return []

    def _deduplicate_and_enhance_scoring(self, matches: List[Dict], profile_data: Dict) -> List[Dict]:
        """Remove duplicates and enhance relevance scoring"""
        seen_jobs = set()
        unique_matches = []
        
        for job in matches:
            # Create unique identifier
            job_id = f"{job.get('title', '')}-{job.get('company', '')}-{job.get('location', '')}"
            
            if job_id not in seen_jobs:
                seen_jobs.add(job_id)
                
                # Enhanced scoring based on multiple factors
                enhanced_score = self._calculate_comprehensive_relevance_score(job, profile_data)
                job['relevance_score'] = enhanced_score
                
                unique_matches.append(job)
        
        return unique_matches

    def _calculate_enhanced_relevance_score(self, job: Dict, job_keywords: List[str]) -> int:
        """Calculate enhanced relevance score - improved version"""
        base_score = 40  # Start with reasonable base
        
        title = job.get('title', '').lower()
        description = job.get('description', '').lower()
        search_term = job.get('search_term', '').lower()
        company = job.get('company', '').lower()
        company_industry = job.get('company_industry', '').lower()
        
        # 1. Title matches (highest weight)
        for keyword in job_keywords:
            if keyword.lower() in title:
                base_score += 20  # Increased from 15
        
        # 2. Industry matches (new - high weight)
        for keyword in job_keywords:
            if keyword.lower() in company_industry:
                base_score += 15
        
        # 3. Search term matches
        for keyword in job_keywords:
            if keyword.lower() in search_term:
                base_score += 12  # Increased from 10
        
        # 4. Description matches
        for keyword in job_keywords:
            if keyword.lower() in description:
                base_score += 6  # Increased from 5
        
        # 5. Company reputation bonus
        reputable_indicators = ['group', 'international', 'global', 'consulting', 'bank', 'technology']
        if any(indicator in company for indicator in reputable_indicators):
            base_score += 8
        
        # 6. Job freshness bonus
        scraped_timestamp = job.get('scraped_timestamp', '')
        if scraped_timestamp:
            try:
                scraped_date = datetime.fromisoformat(scraped_timestamp.replace('Z', '+00:00'))
                days_old = (datetime.now() - scraped_date).days
                if days_old <= 3:
                    base_score += 15  # Very fresh
                elif days_old <= 7:
                    base_score += 10
                elif days_old <= 14:
                    base_score += 5
            except:
                pass
        
        # 7. Industry quality bonus
        quality_industries = ['technology', 'finance', 'consulting', 'healthcare', 'energy', 'pharmaceuticals']
        if any(industry in company_industry for industry in quality_industries):
            base_score += 10
        
        # 8. Job type preference
        job_type = job.get('job_type', '').lower()
        if job_type == 'fulltime':
            base_score += 5
        
        # Cap the score between 1 and 100
        return max(1, min(100, base_score))

    def _calculate_comprehensive_relevance_score(self, job: Dict, profile_data: Dict) -> int:
        """Calculate comprehensive relevance score based on all profile factors"""
        base_score = job.get('relevance_score', 40)
        
        # Get profile data
        job_keywords = profile_data.get('job_title_keywords', [])
        user_skills = profile_data.get('current_skills_selected', []) + profile_data.get('current_skills_custom', [])
        overall_field = profile_data.get('overall_field', '')
        total_experience = profile_data.get('total_experience', 'None')
        
        title = job.get('title', '').lower()
        description = job.get('description', '').lower()
        company_industry = job.get('company_industry', '').lower()
        
        # 1. Enhanced keyword matching
        base_score = self._calculate_enhanced_relevance_score(job, job_keywords)
        
        # 2. Skill matching bonus
        skill_matches = 0
        for skill in user_skills[:10]:  # Check top 10 skills
            if skill.lower() in description or skill.lower() in title:
                skill_matches += 1
                base_score += 3
        
        # 3. Field alignment bonus
        field_keywords = {
            'Data Science & AI': ['data', 'analytics', 'ai', 'machine learning'],
            'Software Development': ['software', 'developer', 'programming', 'engineer'],
            'Project Management': ['project', 'manager', 'scrum', 'agile'],
            'Finance & Economics': ['finance', 'accounting', 'economics', 'financial']
        }
        
        if overall_field in field_keywords:
            for field_keyword in field_keywords[overall_field]:
                if field_keyword in company_industry or field_keyword in title:
                    base_score += 8
                    break
        
        # 4. Experience level matching
        experience_bonus = self._calculate_experience_match_bonus(job, total_experience)
        base_score += experience_bonus
        
        # 5. Multiple keyword match bonus
        keyword_matches = sum(1 for keyword in job_keywords if keyword.lower() in title or keyword.lower() in description)
        if keyword_matches >= 2:
            base_score += keyword_matches * 5
        
        # Cap the final score
        return max(1, min(100, base_score))

    def _match_by_search_terms(self, cursor, job_keywords: List[str], limit: int) -> List[Dict]:
        """Match jobs where search_term contains our keywords - MOST RELIABLE method"""
        matches = []
        
        try:
            # Create search patterns for search_term column
            search_patterns = []
            params = []
            
            for keyword in job_keywords[:5]:  # Limit to first 5 keywords
                search_patterns.append("search_term LIKE ?")
                params.append(f"%{keyword.lower()}%")
            
            if not search_patterns:
                return matches

            query = f"""
            SELECT * FROM job_postings 
            WHERE ({' OR '.join(search_patterns)})
            AND job_status = 'active'
            ORDER BY scraped_timestamp DESC
            LIMIT ?
            """
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert to dictionaries
            column_names = [description[0] for description in cursor.description]
            for row in rows:
                job_dict = dict(zip(column_names, row))
                job_dict['match_type'] = 'search_term'
                job_dict['relevance_score'] = self._calculate_enhanced_relevance_score(job_dict, job_keywords)
                matches.append(job_dict)
            
            logger.info(f"Found {len(matches)} jobs matching search terms: {job_keywords}")
            
        except Exception as e:
            logger.error(f"Error in search term matching: {e}")

        return matches

    def _add_skill_bonus_scoring(self, matches: List[Dict], user_skills: List[str]) -> List[Dict]:
        """Add bonus points for skill matches in title/description"""
        for job in matches:
            skill_bonus = 0
            title_desc = (job.get('title', '') + ' ' + job.get('description', '')).lower()
            
            for skill in user_skills[:10]:  # Check top 10 skills
                if skill.lower() in title_desc:
                    skill_bonus += 2
            
            # Update relevance score
            current_score = job.get('relevance_score', 40)
            job['relevance_score'] = min(100, current_score + skill_bonus)
        
        return matches

    def _filter_by_job_types(self, matches: List[Dict], preferred_job_types: List[str]) -> List[Dict]:
        """Filter matches by preferred job types"""
        mapped_types = []
        for job_type in preferred_job_types:
            mapped_type = self.job_type_mapping.get(job_type)
            if mapped_type:
                mapped_types.append(mapped_type)
        
        if not mapped_types:
            return matches
        
        filtered_matches = []
        for job in matches:
            job_type = job.get('job_type', '').lower()
            if job_type in mapped_types:
                # Boost relevance for matching job type
                job['relevance_score'] = job.get('relevance_score', 40) + 10
                filtered_matches.append(job)
            else:
                # Still include but with lower score
                job['relevance_score'] = job.get('relevance_score', 40) - 5
                filtered_matches.append(job)
        
        return filtered_matches

    def _get_recent_jobs(self, cursor, limit: int = 20) -> List[Dict]:
        """Get recent jobs as fallback"""
        try:
            cursor.execute(f"""
            SELECT * FROM job_postings 
            WHERE job_status = 'active'
            ORDER BY scraped_timestamp DESC
            LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            column_names = [description[0] for description in cursor.description]
            
            recent_jobs = []
            for row in rows:
                job_dict = dict(zip(column_names, row))
                job_dict['match_type'] = 'recent'
                job_dict['relevance_score'] = 30  # Lower base score for fallback jobs
                recent_jobs.append(job_dict)
            
            return recent_jobs
            
        except Exception as e:
            logger.error(f"Error getting recent jobs: {e}")
            return []

    def _deduplicate_and_add_experience_scoring(self, matches: List[Dict], total_experience: str) -> List[Dict]:
        """Remove duplicates and add experience-based scoring"""
        seen_jobs = set()
        unique_matches = []
        
        for job in matches:
            # Create unique identifier
            job_id = f"{job.get('title', '')}-{job.get('company', '')}-{job.get('location', '')}"
            
            if job_id not in seen_jobs:
                seen_jobs.add(job_id)
                
                # Add experience matching bonus
                experience_bonus = self._calculate_experience_match_bonus(job, total_experience)
                current_score = job.get('relevance_score', 40)
                job['relevance_score'] = min(100, current_score + experience_bonus)
                
                unique_matches.append(job)
        
        return unique_matches

    def _calculate_experience_match_bonus(self, job: Dict, total_experience: str) -> int:
        """Calculate bonus based on experience level matching"""
        title = job.get('title', '').lower()
        description = job.get('description', '').lower()
        
        # Experience level indicators
        senior_indicators = ['senior', 'lead', 'principal', 'architect', 'manager', 'director']
        junior_indicators = ['junior', 'graduate', 'entry', 'trainee', 'intern', 'assistant']
        mid_indicators = ['developer', 'engineer', 'analyst', 'specialist', 'consultant']
        
        # Check job seniority level
        is_senior = any(indicator in title for indicator in senior_indicators)
        is_junior = any(indicator in title for indicator in junior_indicators)
        is_mid = not is_senior and not is_junior and any(indicator in title for indicator in mid_indicators)
        
        # Match with user experience
        if total_experience in ['None', '0-1 year']:
            if is_junior:
                return 15
            elif is_mid:
                return 5
            else:
                return -5
        elif total_experience in ['1-3 years', '3-5 years']:
            if is_mid:
                return 15
            elif is_junior:
                return 10
            elif is_senior:
                return 0
        elif total_experience in ['5-10 years', '10-15 years', '15+ years']:
            if is_senior:
                return 15
            elif is_mid:
                return 10
            else:
                return 5
        
        return 0

    def get_database_enrichment_status(self) -> Dict:
        """Get database enrichment status"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM job_postings")
            total_jobs = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM job_postings WHERE company_industry IS NOT NULL AND company_industry != ''")
            enriched_jobs = cursor.fetchone()[0]
            
            enrichment_ratio = enriched_jobs / max(total_jobs, 1)
            
            return {
                "total_jobs": total_jobs,
                "enriched_jobs": enriched_jobs,
                "enrichment_ratio": round(enrichment_ratio, 2),
                "status": "good" if enrichment_ratio > 0.8 else "needs_improvement"
            }
            
        except Exception as e:
            logger.error(f"Error getting enrichment status: {e}")
            return {"error": str(e)}
        finally:
            conn.close()

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
        'preferred_locations_dk': ['København', 'Aarhus kommun'],
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
        # Test search
        print("Testing profile-based job search...")
        results = run_profile_job_search(test_profile)
        print(f"Search completed. Results: {results}")
        
        # Test getting matches
        print("\nTesting job matches retrieval...")
        matches = get_user_job_matches('test_user_123', limit=10)
        print(f"Found {len(matches) if matches else 0} job matches")
        
        # Test database enrichment status
        print("\nTesting database enrichment status...")
        enrichment_status = get_database_enrichment_status()
        print(f"Enrichment status: {enrichment_status}")
        
    except Exception as e:
        print(f"Test failed: {e}")
