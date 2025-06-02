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

    def get_profile_job_matches(self, user_session_id: str, limit: int = 50) -> List[Dict]:
        """
        Get job matches using SIMPLE search_term based matching - much faster and more reliable
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # First, verify the database has data
            cursor.execute("SELECT COUNT(*) FROM job_postings")
            total_jobs_in_db = cursor.fetchone()[0]
            logger.info(f"Total jobs in job_postings table: {total_jobs_in_db}")
            
            if total_jobs_in_db == 0:
                logger.warning("job_postings table is empty - no jobs to match against")
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
                # Return recent jobs as fallback
                return self._get_recent_jobs_simple(cursor, limit)
            
            profile_data = json.loads(profile_row[0])
            
            # Extract matching criteria
            job_keywords = profile_data.get('job_title_keywords', [])
            user_skills = profile_data.get('current_skills_selected', []) + profile_data.get('current_skills_custom', [])
            overall_field = profile_data.get('overall_field', '')
            job_types = profile_data.get('job_types', [])
            total_experience = profile_data.get('total_experience', 'None')
            
            logger.info(f"Simple matching: keywords={job_keywords}, job_types={job_types}")
            
            # SUPER SIMPLE STRATEGY: Match based on search_term first, then add filters
            all_matches = []
            
            # 1. PRIMARY: Direct search_term matching (jobs found by these exact keywords)
            if job_keywords:
                search_term_matches = self._match_by_search_terms(cursor, job_keywords, limit * 2)
                logger.info(f"Search term matching found {len(search_term_matches)} jobs")
                all_matches.extend(search_term_matches)
            
            # 2. SECONDARY: Add job type filtering (student job, etc.)
            if job_types and all_matches:
                all_matches = self._filter_by_job_types(all_matches, job_types)
                logger.info(f"After job type filtering: {len(all_matches)} jobs")
            
            # 3. TERTIARY: Add simple skill bonus scoring
            if user_skills and all_matches:
                all_matches = self._add_skill_bonus_scoring(all_matches, user_skills)
            
            # 4. FALLBACK: If we don't have enough matches, add some recent jobs
            if len(all_matches) < 10:
                recent_matches = self._get_recent_jobs_simple(cursor, limit)
                logger.info(f"Adding {len(recent_matches)} recent jobs as fallback")
                all_matches.extend(recent_matches)
            
            # Remove duplicates and add experience-based scoring
            unique_matches = self._deduplicate_and_add_experience_scoring(all_matches, total_experience)
            
            # Sort by relevance score and return
            final_matches = sorted(unique_matches, key=lambda x: x.get('relevance_score', 1), reverse=True)[:limit]
            
            if final_matches:
                scores = [m.get('relevance_score', 1) for m in final_matches]
                logger.info(f"Final result: {len(final_matches)} matches with scores {min(scores)}-{max(scores)}")
            else:
                logger.warning("No matches found")
            
            return final_matches
            
        except Exception as e:
            logger.error(f"Error getting job matches: {e}", exc_info=True)
            return []
        finally:
            conn.close()

    def _match_by_search_terms(self, cursor, job_keywords: List[str], limit: int) -> List[Dict]:
        """Match jobs where search_term contains our keywords - MOST RELIABLE method"""
        matches = []
        
        try:
            # Create search patterns for search_term column
            search_patterns = []
            params = []
            
            for keyword in job_keywords[:5]:  # Max 5 keywords
                # Direct match in search_term
                search_patterns.append("LOWER(search_term) LIKE ?")
                params.append(f"%{keyword.lower()}%")
            
            if not search_patterns:
                return matches
            
            where_clause = " OR ".join(search_patterns)
            
            query = f"""
            SELECT 
                id, title, company, company_url, job_url, location, is_remote, job_type, 
                description, date_posted, company_industry, company_description, 
                company_logo, scraped_timestamp, search_term, search_location
            FROM job_postings
            WHERE {where_clause}
            ORDER BY scraped_timestamp DESC
            LIMIT ?
            """
            
            params.append(limit)
            cursor.execute(query, params)
            jobs = cursor.fetchall()
            
            columns = [
                'id', 'title', 'company', 'company_url', 'job_url', 'location', 'is_remote', 
                'job_type', 'description', 'date_posted', 'company_industry', 
                'company_description', 'company_logo', 'scraped_timestamp', 
                'search_term', 'search_location'
            ]
            
            for job in jobs:
                job_dict = dict(zip(columns, job))
                job_dict['match_type'] = 'search_term'
                job_dict['relevance_score'] = 70  # High base score for search_term matches
                matches.append(job_dict)
            
            logger.info(f"Found {len(matches)} jobs matching search terms")
            return matches
            
        except Exception as e:
            logger.error(f"Error in search_term matching: {e}")
            return []

    def _filter_by_job_types(self, matches: List[Dict], job_types: List[str]) -> List[Dict]:
        """Filter and score jobs based on selected job types"""
        filtered_matches = []
        
        for job in matches:
            title = job.get('title', '').lower()
            description = job.get('description', '').lower()
            base_score = job.get('relevance_score', 50)
            
            # Check for job type keywords and adjust score
            score_adjustment = 0
            matched_types = []
            
            for job_type in job_types:
                if job_type == "Student job":
                    if any(word in title or word in description for word in ['student', 'studiejob', 'deltid']):
                        score_adjustment += 20
                        matched_types.append('student')
                
                elif job_type == "New graduate":
                    if any(word in title or word in description for word in ['graduate', 'nyuddannet', 'junior', 'entry']):
                        score_adjustment += 15
                        matched_types.append('graduate')
                
                elif job_type == "Internship":
                    if any(word in title or word in description for word in ['intern', 'praktik', 'trainee']):
                        score_adjustment += 20
                        matched_types.append('internship')
                
                elif job_type == "Part-time":
                    if any(word in title or word in description for word in ['part-time', 'deltid', 'part time']):
                        score_adjustment += 10
                        matched_types.append('part-time')
                
                elif job_type == "Full-time":
                    if any(word in title or word in description for word in ['full-time', 'fuldtid', 'full time']):
                        score_adjustment += 5
                        matched_types.append('full-time')
            
            # Update job with new score and matched types
            job['relevance_score'] = min(100, base_score + score_adjustment)
            job['matched_job_types'] = matched_types
            
            # Include all jobs (don't filter out), just adjust scores
            filtered_matches.append(job)
        
        return filtered_matches

    def _add_skill_bonus_scoring(self, matches: List[Dict], user_skills: List[str]) -> List[Dict]:
        """Add bonus points for skill matches in title/description"""
        for job in matches:
            title = job.get('title', '').lower()
            description = job.get('description', '').lower()
            base_score = job.get('relevance_score', 50)
            
            skill_bonus = 0
            matched_skills = []
            
            for skill in user_skills[:5]:  # Top 5 skills
                if len(skill) >= 3:  # Only meaningful skills
                    if skill.lower() in title:
                        skill_bonus += 8  # Higher bonus for title matches
                        matched_skills.append(skill)
                    elif skill.lower() in description:
                        skill_bonus += 3  # Lower bonus for description matches
                        matched_skills.append(skill)
            
            # Cap skill bonus
            skill_bonus = min(20, skill_bonus)
            
            job['relevance_score'] = min(100, base_score + skill_bonus)
            job['matched_skills'] = matched_skills[:3]  # Store top 3 matched skills
        
        return matches

    def _deduplicate_and_add_experience_scoring(self, all_matches: List[Dict], total_experience: str) -> List[Dict]:
        """Remove duplicates and add experience-based scoring"""
        # Remove duplicates by job ID
        seen_ids = set()
        unique_matches = []
        
        for match in all_matches:
            job_id = match.get('id')
            if job_id not in seen_ids:
                seen_ids.add(job_id)
                unique_matches.append(match)
        
        # Add experience-based scoring
        experience_score = self._get_experience_score(total_experience)
        
        for match in unique_matches:
            title = match.get('title', '').lower()
            base_score = match.get('relevance_score', 50)
            
            # Experience matching adjustment
            experience_adjustment = 0
            
            if experience_score <= 30:  # Entry level/Student
                if any(word in title for word in ['senior', 'lead', 'manager', 'director']):
                    experience_adjustment = -15  # Penalty for too senior roles
                elif any(word in title for word in ['junior', 'entry', 'student', 'graduate', 'trainee']):
                    experience_adjustment = 10   # Bonus for appropriate level
            
            elif experience_score >= 70:  # Senior level
                if any(word in title for word in ['senior', 'lead', 'principal', 'manager']):
                    experience_adjustment = 10   # Bonus for senior roles
                elif any(word in title for word in ['junior', 'entry', 'trainee']):
                    experience_adjustment = -10  # Penalty for too junior roles
            
            match['relevance_score'] = max(1, min(100, base_score + experience_adjustment))
        
        return unique_matches

    def _get_recent_jobs_simple(self, cursor, limit: int) -> List[Dict]:
        """Get recent jobs as fallback with minimal scoring"""
        try:
            cursor.execute("""
            SELECT 
                id, title, company, company_url, job_url, location, is_remote, job_type, 
                description, date_posted, company_industry, company_description, 
                company_logo, scraped_timestamp, search_term, search_location
            FROM job_postings
            ORDER BY scraped_timestamp DESC
            LIMIT ?
            """, (limit,))
            
            jobs = cursor.fetchall()
            columns = [
                'id', 'title', 'company', 'company_url', 'job_url', 'location', 'is_remote', 
                'job_type', 'description', 'date_posted', 'company_industry', 
                'company_description', 'company_logo', 'scraped_timestamp', 
                'search_term', 'search_location'
            ]
            
            matches = []
            for job in jobs:
                job_dict = dict(zip(columns, job))
                job_dict['match_type'] = 'recent'
                job_dict['relevance_score'] = 30  # Lower score for fallback jobs
                matches.append(job_dict)
            
            return matches
            
        except Exception as e:
            logger.error(f"Error getting recent jobs: {e}")
            return []

    def _get_experience_score(self, total_experience: str) -> int:
        """Convert experience string to numeric score"""
        experience_mapping = {
            'None': 10,
            '0-1 year': 20,
            '1-3 years': 35, 
            '3-5 years': 50,
            '5-10 years': 70,
            '10-15 years': 85,
            '15+ years': 95
        }
        return experience_mapping.get(total_experience, 30)

    def get_database_enrichment_status(self) -> Dict:
        """
        Get statistics about database enrichment status
        Returns information about how many jobs have enhanced data
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # Check if the table exists
            cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='job_postings'
            """)
            
            if not cursor.fetchone():
                return {
                    'total_jobs': 0,
                    'enriched_jobs': 0,
                    'enrichment_percentage': 0,
                    'has_industry_data': 0,
                    'has_description_data': 0,
                    'status': 'No job_postings table found'
                }
            
            # Get total job count
            cursor.execute("SELECT COUNT(*) FROM job_postings")
            total_jobs = cursor.fetchone()[0]
            
            if total_jobs == 0:
                return {
                    'total_jobs': 0,
                    'enriched_jobs': 0,
                    'enrichment_percentage': 0,
                    'has_industry_data': 0,
                    'has_description_data': 0,
                    'status': 'No jobs in database'
                }
            
            # Count jobs with company industry data
            cursor.execute("""
            SELECT COUNT(*) FROM job_postings 
            WHERE company_industry IS NOT NULL 
            AND company_industry != '' 
            AND company_industry != 'Unknown'
            """)
            has_industry_data = cursor.fetchone()[0]
            
            # Count jobs with description data
            cursor.execute("""
            SELECT COUNT(*) FROM job_postings 
            WHERE description IS NOT NULL 
            AND description != '' 
            AND LENGTH(description) > 50
            """)
            has_description_data = cursor.fetchone()[0]
            
            # Count jobs with both description and some company info
            cursor.execute("""
            SELECT COUNT(*) FROM job_postings 
            WHERE description IS NOT NULL 
            AND description != '' 
            AND LENGTH(description) > 50
            AND company IS NOT NULL 
            AND company != ''
            """)
            enriched_jobs = cursor.fetchone()[0]
            
            enrichment_percentage = (enriched_jobs / total_jobs * 100) if total_jobs > 0 else 0
            
            # Determine status
            if enrichment_percentage >= 80:
                status = 'Well enriched'
            elif enrichment_percentage >= 50:
                status = 'Moderately enriched'
            elif enrichment_percentage >= 20:
                status = 'Partially enriched'
            else:
                status = 'Poorly enriched'
            
            return {
                'total_jobs': total_jobs,
                'enriched_jobs': enriched_jobs,
                'enrichment_percentage': round(enrichment_percentage, 1),
                'has_industry_data': has_industry_data,
                'has_description_data': has_description_data,
                'status': status
            }
            
        except Exception as e:
            logger.error(f"Error getting database enrichment status: {e}")
            return {
                'total_jobs': 0,
                'enriched_jobs': 0,
                'enrichment_percentage': 0,
                'has_industry_data': 0,
                'has_description_data': 0,
                'status': f'Error: {str(e)}'
            }
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
