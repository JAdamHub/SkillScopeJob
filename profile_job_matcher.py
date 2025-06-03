from typing import Dict, List, Optional
from datetime import datetime, timedelta
import sqlite3
import json
import logging

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
            'original_job_types': profile_data.get('job_types', []),
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
            # Simple refresh strategy - just log it for now
            refresh_stats["actions_taken"].append("refresh_attempted")
            refresh_stats["after_stats"] = self.get_job_age_distribution()
            return refresh_stats
        except Exception as e:
            logger.error(f"Error in database refresh: {e}")
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
            total_jobs = cursor.fetchone()[0]
            
            return {
                "total": total_jobs,
                "fresh": 0,
                "recent": 0,
                "aging": 0,
                "stale": 0
            }
        except Exception as e:
            logger.error(f"Error getting job age distribution: {e}")
            return {"total": 0, "fresh": 0, "recent": 0, "aging": 0, "stale": 0}
        finally:
            conn.close()

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
        Returns the EXACT jobs that should be used for CV evaluation
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
            
            # Log the top matches for debugging CV evaluation integration
            for i, match in enumerate(final_matches[:5]):
                logger.info(f"Top Match {i+1}: {match.get('title')} at {match.get('company')} (Score: {match.get('relevance_score', 0)})")
            
            return final_matches
            
        except Exception as e:
            logger.error(f"Error getting job matches: {e}", exc_info=True)
            return []
        finally:
            conn.close()

    def _enhanced_keyword_matching(self, cursor, job_keywords: List[str], limit: int) -> List[Dict]:
        """Enhanced keyword matching across title, description, and search_term with NULL safety"""
        matches = []
        
        try:
            # Build comprehensive search query for multiple fields
            search_conditions = []
            params = []
            
            for keyword in job_keywords[:5]:  # Limit to top 5 keywords
                keyword_lower = keyword.lower()
                search_conditions.append("""
                (LOWER(COALESCE(title, '')) LIKE ? OR 
                 LOWER(COALESCE(description, '')) LIKE ? OR 
                 LOWER(COALESCE(search_term, '')) LIKE ?)
                """)
                params.extend([f'%{keyword_lower}%', f'%{keyword_lower}%', f'%{keyword_lower}%'])
            
            if search_conditions:
                query = f"""
                SELECT id, title, company, location, description, job_url, job_type, 
                       company_industry, date_posted, scraped_timestamp, search_term
                FROM job_postings 
                WHERE ({' OR '.join(search_conditions)})
                ORDER BY scraped_timestamp DESC
                LIMIT ?
                """
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                for row in rows:
                    job_dict = {
                        'id': row[0],
                        'title': row[1] or '',
                        'company': row[2] or '',
                        'location': row[3] or '',
                        'description': row[4] or '',
                        'job_url': row[5] or '',
                        'job_type': row[6] or '',
                        'company_industry': row[7] or '',
                        'date_posted': row[8] or '',
                        'scraped_timestamp': row[9] or '',
                        'search_term': row[10] or '',
                        'match_type': 'keyword',
                        'relevance_score': self._calculate_enhanced_relevance_score({
                            'title': row[1] or '', 'description': row[4] or '', 'search_term': row[10] or '',
                            'company': row[2] or '', 'company_industry': row[7] or '', 'scraped_timestamp': row[9] or '',
                            'job_type': row[6] or ''
                        }, job_keywords)
                    }
                    matches.append(job_dict)
            
        except Exception as e:
            logger.error(f"Error in enhanced keyword matching: {e}")
        
        return matches

    def _match_by_field(self, cursor, overall_field: str, limit: int) -> List[Dict]:
        """Match jobs by overall field/industry with NULL safety"""
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
            # Search for field-related keywords in title and description with NULL safety
            search_conditions = []
            params = []
            
            for keyword in keywords[:5]:  # Top 5 field keywords
                search_conditions.append("(LOWER(COALESCE(title, '')) LIKE ? OR LOWER(COALESCE(description, '')) LIKE ?)")
                params.extend([f'%{keyword}%', f'%{keyword}%'])
            
            if search_conditions:
                query = f"""
                SELECT id, title, company, location, description, job_url, job_type, 
                       company_industry, date_posted, scraped_timestamp, search_term
                FROM job_postings 
                WHERE ({' OR '.join(search_conditions)})
                ORDER BY scraped_timestamp DESC
                LIMIT ?
                """
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                for row in rows:
                    job_dict = {
                        'id': row[0],
                        'title': row[1] or '',
                        'company': row[2] or '',
                        'location': row[3] or '',
                        'description': row[4] or '',
                        'job_url': row[5] or '',
                        'job_type': row[6] or '',
                        'company_industry': row[7] or '',
                        'date_posted': row[8] or '',
                        'scraped_timestamp': row[9] or '',
                        'search_term': row[10] or '',
                        'match_type': 'field',
                        'relevance_score': 45  # Base score for field matches
                    }
                    matches.append(job_dict)
                    
        except Exception as e:
            logger.error(f"Error in field matching: {e}")
        
        return matches

    def _match_by_skills(self, cursor, user_skills: List[str], limit: int) -> List[Dict]:
        """Match jobs by user skills in description with NULL safety"""
        matches = []
        
        try:
            if not user_skills:
                return matches
            
            # Search for skills in job descriptions with NULL safety
            search_conditions = []
            params = []
            
            for skill in user_skills[:10]:  # Top 10 skills
                skill_lower = skill.lower()
                search_conditions.append("LOWER(COALESCE(description, '')) LIKE ?")
                params.append(f'%{skill_lower}%')
            
            if search_conditions:
                query = f"""
                SELECT id, title, company, location, description, job_url, job_type, 
                       company_industry, date_posted, scraped_timestamp, search_term
                FROM job_postings 
                WHERE ({' OR '.join(search_conditions)})
                ORDER BY scraped_timestamp DESC
                LIMIT ?
                """
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                for row in rows:
                    job_dict = {
                        'id': row[0],
                        'title': row[1] or '',
                        'company': row[2] or '',
                        'location': row[3] or '',
                        'description': row[4] or '',
                        'job_url': row[5] or '',
                        'job_type': row[6] or '',
                        'company_industry': row[7] or '',
                        'date_posted': row[8] or '',
                        'scraped_timestamp': row[9] or '',
                        'search_term': row[10] or '',
                        'match_type': 'skill',
                        'relevance_score': 40  # Base score for skill matches
                    }
                    matches.append(job_dict)
                    
        except Exception as e:
            logger.error(f"Error in skill matching: {e}")
        
        return matches

    def _get_recent_quality_jobs(self, cursor, limit: int = 30) -> List[Dict]:
        """Get recent, high-quality jobs as fallback with NULL safety"""
        try:
            query = """
            SELECT id, title, company, location, description, job_url, job_type, 
                   company_industry, date_posted, scraped_timestamp, search_term
            FROM job_postings 
            WHERE title IS NOT NULL AND company IS NOT NULL 
            AND description IS NOT NULL AND LENGTH(description) > 100
            ORDER BY scraped_timestamp DESC
            LIMIT ?
            """
            
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            
            matches = []
            for row in rows:
                job_dict = {
                    'id': row[0],
                    'title': row[1] or '',
                    'company': row[2] or '',
                    'location': row[3] or '',
                    'description': row[4] or '',
                    'job_url': row[5] or '',
                    'job_type': row[6] or '',
                    'company_industry': row[7] or '',
                    'date_posted': row[8] or '',
                    'scraped_timestamp': row[9] or '',
                    'search_term': row[10] or '',
                    'match_type': 'recent',
                    'relevance_score': 35  # Base score for recent jobs
                }
                matches.append(job_dict)
            
            return matches
            
        except Exception as e:
            logger.error(f"Error getting recent quality jobs: {e}")
            return []

    def _deduplicate_and_enhance_scoring(self, matches: List[Dict], profile_data: Dict) -> List[Dict]:
        """Remove duplicates and enhance relevance scoring with NULL safety"""
        seen_jobs = set()
        unique_matches = []
        
        for job in matches:
            # FIXED: Add NULL safety for database fields
            title = job.get('title') or ''
            company = job.get('company') or ''
            location = job.get('location') or ''
            
            # Create unique identifier for job
            job_key = (title.lower(), company.lower(), location.lower())
            
            if job_key not in seen_jobs:
                seen_jobs.add(job_key)
                # Enhance relevance score based on comprehensive profile data
                enhanced_score = self._calculate_comprehensive_relevance_score(job, profile_data)
                job['relevance_score'] = enhanced_score
                unique_matches.append(job)
        
        return unique_matches

    def _calculate_enhanced_relevance_score(self, job: Dict, job_keywords: List[str]) -> int:
        """Calculate enhanced relevance score - improved version with null handling"""
        base_score = 40  # Start with reasonable base
        
        # SAFE null handling for all database fields
        title = (job.get('title') or '').lower()
        description = (job.get('description') or '').lower()
        search_term = (job.get('search_term') or '').lower()
        company = (job.get('company') or '').lower()
        company_industry = (job.get('company_industry') or '').lower()
        
        # 1. Title matches (highest weight)
        for keyword in job_keywords:
            if keyword.lower() in title:
                base_score += 15
        
        # 2. Industry matches (new - high weight)
        for keyword in job_keywords:
            if keyword.lower() in company_industry:
                base_score += 12
        
        # 3. Search term matches
        for keyword in job_keywords:
            if keyword.lower() in search_term:
                base_score += 8
        
        # 4. Description matches
        for keyword in job_keywords:
            if keyword.lower() in description:
                base_score += 5
        
        # 5. Company reputation bonus
        reputable_indicators = ['group', 'international', 'global', 'consulting', 'bank', 'technology']
        if any(indicator in company for indicator in reputable_indicators):
            base_score += 5
        
        # 6. Job freshness bonus
        scraped_timestamp = job.get('scraped_timestamp', '')
        if scraped_timestamp:
            try:
                from datetime import datetime
                scraped_date = datetime.fromisoformat(scraped_timestamp)
                days_old = (datetime.now() - scraped_date).days
                if days_old <= 7:
                    base_score += 3
            except:
                pass
        
        # 7. Industry quality bonus
        quality_industries = ['technology', 'finance', 'consulting', 'healthcare', 'energy', 'pharmaceuticals']
        if any(industry in company_industry for industry in quality_industries):
            base_score += 3
        
        # 8. Job type preference
        job_type = (job.get('job_type') or '').lower()
        if job_type == 'fulltime':
            base_score += 2
        
        # Cap the score between 1 and 100
        return max(1, min(100, base_score))

    def _calculate_comprehensive_relevance_score(self, job: Dict, profile_data: Dict) -> int:
        """Calculate comprehensive relevance score based on all profile factors with null handling"""
        base_score = job.get('relevance_score', 40)
        
        # Get profile data
        job_keywords = profile_data.get('job_title_keywords', [])
        user_skills = profile_data.get('current_skills_selected', []) + profile_data.get('current_skills_custom', [])
        overall_field = profile_data.get('overall_field', '')
        total_experience = profile_data.get('total_experience', 'None')
        
        # SAFE null handling for all database fields
        title = (job.get('title') or '').lower()
        description = (job.get('description') or '').lower()
        company_industry = (job.get('company_industry') or '').lower()
        
        # 1. Enhanced keyword matching
        base_score = self._calculate_enhanced_relevance_score(job, job_keywords)
        
        # 2. Skill matching bonus
        skill_matches = 0
        for skill in user_skills[:10]:
            if skill.lower() in description:
                skill_matches += 1
        
        base_score += skill_matches * 2  # 2 points per skill match
        
        # 3. Field alignment bonus
        field_keywords = {
            'Data Science & AI': ['data', 'analytics', 'ai', 'machine learning'],
            'Software Development': ['software', 'developer', 'programming', 'engineer'],
            'Project Management': ['project', 'manager', 'scrum', 'agile'],
            'Finance & Economics': ['finance', 'accounting', 'economics', 'financial']
        }
        
        if overall_field in field_keywords:
            field_matches = sum(1 for kw in field_keywords[overall_field] if kw in title or kw in description)
            base_score += field_matches * 3
        
        # 4. Experience level matching
        experience_bonus = self._calculate_experience_match_bonus(job, total_experience)
        base_score += experience_bonus
        
        # 5. Multiple keyword match bonus
        keyword_matches = sum(1 for keyword in job_keywords if keyword.lower() in title or keyword.lower() in description)
        if keyword_matches >= 2:
            base_score += 5
        
        # Cap the final score
        return max(1, min(100, base_score))

    def _calculate_experience_match_bonus(self, job: Dict, total_experience: str) -> int:
        """Calculate bonus based on experience level matching with null handling"""
        title = (job.get('title') or '').lower()
        description = (job.get('description') or '').lower()
        
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
                return 5
            elif is_mid:
                return -2
            else:
                return -5
        elif total_experience in ['1-3 years', '3-5 years']:
            if is_mid:
                return 5
            elif is_junior:
                return 2
            elif is_senior:
                return -3
            else:
                return 0
        elif total_experience in ['5-10 years', '10-15 years', '15+ years']:
            if is_senior:
                return 5
            elif is_mid:
                return 2
            else:
                return 0
        
        return 0

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
            'existing_matches_after_search': 0,
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
                        # Use correct parameter name for the scraping function
                        results = scrape_indeed_jobs_with_profile(
                            search_term=enhanced_job_title,
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

    def init_database_with_freshness_tracking(self):
        """
        Initialize database with additional columns for tracking job freshness
        """
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute("ALTER TABLE job_postings ADD COLUMN job_freshness TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE job_postings ADD COLUMN enrichment_status TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            cursor.execute("ALTER TABLE job_postings ADD COLUMN user_profile_match REAL")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create indexes for performance
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_freshness ON job_postings(job_freshness)")
        except sqlite3.OperationalError:
            pass  # Index already exists
        
        conn.commit()
        conn.close()

    def get_database_enrichment_status(self) -> Dict:
        """Get database enrichment status"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM job_postings")
            total_count = cursor.fetchone()[0]
            
            return {
                "total_jobs": total_count,
                "status": "operational" if total_count > 0 else "empty"
            }
        except Exception as e:
            return {
                "total_jobs": 0,
                "status": "error",
                "error": str(e)
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
