from typing import Dict, List, Optional
from datetime import datetime, timedelta
import sqlite3
import json
import logging

# Add missing imports
from datetime import datetime, timedelta

# SQLAlchemy imports for ORM-based querying
from sqlalchemy import or_, and_, desc, func as sql_func, cast, String as SQLString
from sqlalchemy.orm import Session
# Assuming JobPosting, UserProfile, etc. are defined in database_models
# and SessionLocal is your session factory
from skillscope.models.database_models import (
    JobPosting, UserProfile, SessionLocal, Base, engine,
    UserProfileTargetRole, UserProfileKeyword, UserProfileSkill,
    UserProfileLanguage, UserProfileJobType, UserProfileLocation,
    UserEducation, UserExperience, JobStatusEnum
)

# from indeed_scraper import scrape_indeed_jobs_with_profile, init_database, DB_NAME, TABLE_NAME
# Keep DB_NAME and TABLE_NAME for now if some parts still need direct SQLite access,
# but aim to phase them out for JobPosting queries.
from skillscope.scrapers.indeed_scraper import scrape_indeed_jobs_with_profile, DB_NAME, TABLE_NAME

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProfileJobMatcher:
    """
    Integrates user profile data with job scraping to find relevant positions
    """
    
    def __init__(self, max_job_age_days: int = 30):
        """
        Initialize matcher with database freshness configuration
        
        Args:
            max_job_age_days: Maximum age for jobs before they're considered stale (default: 30 days)
        """
        self.max_job_age_days = max_job_age_days
        
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

    def _store_normalized_user_profile(self, session: Session, profile_form_data: dict):
        """Store or update user profile in database using SQLAlchemy ORM."""
        user_session_id = profile_form_data.get('user_session_id', 'unknown')
        if user_session_id == 'unknown' and 'user_id_input' in profile_form_data and profile_form_data['user_id_input']:
             user_session_id = profile_form_data['user_id_input']

        if not user_session_id or user_session_id == 'unknown':
            logger.error("Cannot store profile: user_session_id is missing or 'unknown'.")
            return

        user_profile = session.query(UserProfile).filter_by(user_session_id=user_session_id).first()
        
        if not user_profile:
            user_profile = UserProfile(user_session_id=user_session_id)
            session.add(user_profile)
            logger.info(f"Creating new UserProfile for {user_session_id}.")
        else:
            logger.info(f"Updating existing UserProfile for {user_session_id}.")

        submission_ts_str = profile_form_data.get("submission_timestamp")
        if submission_ts_str:
            try:
                user_profile.submission_timestamp = datetime.strptime(submission_ts_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    user_profile.submission_timestamp = datetime.fromisoformat(submission_ts_str)
                except ValueError:
                    logger.warning(f"Could not parse submission_timestamp: {submission_ts_str}. Using current time.")
                    user_profile.submission_timestamp = datetime.now()
        else:
            user_profile.submission_timestamp = datetime.now()

        user_profile.user_id_input = profile_form_data.get("user_id_input")
        user_profile.personal_description = profile_form_data.get("personal_description")
        user_profile.total_experience = profile_form_data.get("total_experience")
        user_profile.remote_openness = profile_form_data.get("remote_openness")
        user_profile.analysis_preference = profile_form_data.get("analysis_preference")
        user_profile.overall_field = profile_form_data.get("overall_field")

        # Helper for updating related collections
        def _update_collection(collection, new_items_data, model_class, name_attr):
            # It is important to manage the session correctly when clearing and adding items
            # to avoid issues with detached instances if objects are not yet persisted.
            # A common pattern is to remove items that are no longer in new_items_data
            # and add new ones. For simplicity here, if cascade delete-orphan is set,
            # clearing and re-adding can work, but be mindful of performance with large collections.
            
            # Convert new_items_data to a set of strings for efficient lookup
            new_item_names = {str(item_name).strip() for item_name in new_items_data if item_name and str(item_name).strip()}
            
            # Remove items from collection that are not in new_item_names
            # Iterate over a copy of the collection for safe removal
            for current_item in list(collection):
                if getattr(current_item, name_attr) not in new_item_names:
                    session.delete(current_item) # or collection.remove(current_item) if cascade works as expected
                else:
                    # Item is already present and should remain, remove it from new_item_names to avoid re-adding
                    new_item_names.remove(getattr(current_item, name_attr))
            
            # Add new items that were not in the collection
            for item_name_to_add in new_item_names:
                 collection.append(model_class(**{name_attr: item_name_to_add}))

        _update_collection(user_profile.target_roles, 
                           profile_form_data.get("target_roles_industries_selected", []) + 
                           [rc.strip() for rc in profile_form_data.get("target_roles_industries_custom", []) if rc.strip()],
                           UserProfileTargetRole, "role_or_industry_name")
        _update_collection(user_profile.keywords, profile_form_data.get("job_title_keywords", []), UserProfileKeyword, "keyword")
        _update_collection(user_profile.skills, 
                           profile_form_data.get("current_skills_selected", []) + 
                           [sc.strip() for sc in profile_form_data.get("current_skills_custom", []) if sc.strip()],
                           UserProfileSkill, "skill_name")
        _update_collection(user_profile.languages, profile_form_data.get("job_languages", []), UserProfileLanguage, "language_name")
        _update_collection(user_profile.job_types, profile_form_data.get("job_types", []), UserProfileJobType, "job_type_name")
        _update_collection(user_profile.preferred_locations, profile_form_data.get("preferred_locations_dk", []), UserProfileLocation, "location_name")

        # For one-to-many like education and experience, clearing and re-adding is often simplest if IDs are not preserved across edits
        # If IDs from the form need to be matched for updates, a more complex merge logic is needed.
        # Assuming cascade="all, delete-orphan" is set on the relationships in UserProfile model.
        user_profile.education_entries.clear()
        for edu_data in profile_form_data.get("education_entries", []):
            user_profile.education_entries.append(UserEducation(
                degree=edu_data.get("degree"),
                field_of_study=edu_data.get("field_of_study"),
                institution=edu_data.get("institution"),
                graduation_year=str(edu_data.get("graduation_year"))
            ))

        user_profile.experience_entries.clear()
        for exp_data in profile_form_data.get("work_experience_entries", []):
            years_in_role_val = 0.0
            try:
                raw_years = exp_data.get("years_in_role", "0")
                if isinstance(raw_years, (int, float)):
                    years_in_role_val = float(raw_years)
                elif isinstance(raw_years, str) and raw_years.strip():
                    years_in_role_val = float(raw_years.strip())
            except ValueError:
                logger.warning(f"Could not parse years_in_role: {exp_data.get('years_in_role')}. Defaulting to 0.")
            
            user_profile.experience_entries.append(UserExperience(
                job_title=exp_data.get("job_title"),
                company=exp_data.get("company"),
                years_in_role=years_in_role_val,
                skills_responsibilities=exp_data.get("skills_responsibilities")
            ))
        
        try:
            session.commit()
            logger.info(f"UserProfile for {user_session_id} saved/updated via SQLAlchemy.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving UserProfile for {user_session_id} via SQLAlchemy: {e}")

    def _get_normalized_profile_dict(self, session: Session, user_session_id: str) -> Optional[Dict]:
        """Fetch UserProfile using SQLAlchemy and convert to a dictionary."""
        from sqlalchemy.orm import joinedload # Import locally if not already at top level of class context

        user_profile = (
            session.query(UserProfile)
            .options(
                joinedload(UserProfile.target_roles),
                joinedload(UserProfile.keywords),
                joinedload(UserProfile.skills),
                joinedload(UserProfile.languages),
                joinedload(UserProfile.job_types),
                joinedload(UserProfile.preferred_locations),
                joinedload(UserProfile.education_entries),
                joinedload(UserProfile.experience_entries),
            )
            .filter(UserProfile.user_session_id == user_session_id)
            .order_by(UserProfile.last_search_timestamp.desc().nullslast(), UserProfile.created_timestamp.desc().nullslast())
            .first()
        )

        if not user_profile:
            logger.warning(f"No UserProfile found for user_session_id: {user_session_id} in _get_normalized_profile_dict")
            return None

        profile_dict = {
            "user_session_id": user_profile.user_session_id,
            "submission_timestamp": user_profile.submission_timestamp.isoformat() if user_profile.submission_timestamp else None,
            "user_id_input": user_profile.user_id_input,
            "personal_description": user_profile.personal_description,
            "total_experience": user_profile.total_experience,
            "remote_openness": user_profile.remote_openness,
            "analysis_preference": user_profile.analysis_preference,
            "overall_field": user_profile.overall_field,
            "target_roles_industries_selected": [tr.role_or_industry_name for tr in user_profile.target_roles if tr.role_or_industry_name],
            "job_title_keywords": [kw.keyword for kw in user_profile.keywords if kw.keyword],
            "current_skills_selected": [s.skill_name for s in user_profile.skills if s.skill_name],
            "job_languages": [lang.language_name for lang in user_profile.languages if lang.language_name],
            "job_types": [jt.job_type_name for jt in user_profile.job_types if jt.job_type_name],
            "preferred_locations_dk": [loc.location_name for loc in user_profile.preferred_locations if loc.location_name],
            "education_entries": [{
                "id": str(edu.id), "degree": edu.degree, "field_of_study": edu.field_of_study,
                "institution": edu.institution, "graduation_year": edu.graduation_year
            } for edu in user_profile.education_entries],
            "work_experience_entries": [{
                "id": str(exp.id), "job_title": exp.job_title, "company": exp.company,
                "years_in_role": exp.years_in_role, 
                "skills_responsibilities": exp.skills_responsibilities
            } for exp in user_profile.experience_entries],
            "created_timestamp": user_profile.created_timestamp.isoformat() if user_profile.created_timestamp else None,
            "last_search_timestamp": user_profile.last_search_timestamp.isoformat() if user_profile.last_search_timestamp else None,
        }
        logger.info(f"Fetched and normalized UserProfile for {user_session_id} to dictionary.")
        return profile_dict

    def run_profile_based_search(self, session: Session, profile_data: Dict, max_results_per_search: int = 50, auto_refresh: bool = True) -> Dict:
        """
        Run profile-based job search - PRIORITIZES live scraping with fresh data
        Database is only used as fallback if scraping fails completely
        """
        try:
            # Store user profile first using the passed session
            if not isinstance(session, Session):
                logger.error("run_profile_based_search did not receive a valid SQLAlchemy Session.")
                # Decide how to handle this: raise error, or attempt to create one (less ideal for consistency)
                # For now, let's log and proceed, but this indicates an issue in the calling code (wrapper)
                # or how the session is managed. Given the wrappers should provide it, this is a safeguard.
                # However, the wrapper functions (global run_profile_job_search) are responsible for session creation.
                # This method (class method) *receives* the session.
                raise TypeError("ProfileJobMatcher.run_profile_based_search expects a valid SQLAlchemy Session.")

            self._store_normalized_user_profile(session, profile_data)
            
            # Try live scraping first (PRIMARY SOURCE)
            logger.info("Starting LIVE job scraping as primary source...")
            
            # Import here to avoid circular imports
            from skillscope.scrapers.indeed_scraper import scrape_indeed_jobs_with_profile
            
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
                database_matches = self.get_profile_job_matches(session, user_session_id, limit=max_results_per_search)
                
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

    def get_profile_job_matches(self, session: Session, user_session_id: str, limit: int = 50, include_stale: bool = False) -> List[Dict]:
        """
        Get job matches from DATABASE - now used primarily as fallback
        Uses SQLAlchemy session for querying JobPosting.
        """
        try:
            # Check if job_postings table has data using SQLAlchemy
            total_jobs_in_db = session.query(sql_func.count(JobPosting.id)).scalar()
            logger.info(f"Database contains {total_jobs_in_db} total jobs in job_postings table (SQLAlchemy count)")

            if total_jobs_in_db == 0:
                logger.warning("No jobs found in job_postings database table - this is expected if running for first time")
                return []

            profile_data = self._get_normalized_profile_dict(session, user_session_id)

            if not profile_data:
                logger.warning(f"No profile found for user {user_session_id} using normalized retrieval.")
                # Fallback to recent jobs using SQLAlchemy
                recent_jobs_models = self._get_recent_quality_jobs(session, limit)
                return [self._job_model_to_dict(job_model) for job_model in recent_jobs_models]

            job_keywords = profile_data.get('job_title_keywords', [])
            overall_field = profile_data.get('overall_field', '')
            user_skills = profile_data.get('current_skills_selected', []) + profile_data.get('current_skills_custom', [])


            logger.info(f"Database matching for: keywords={job_keywords}, field={overall_field}, skills={user_skills}")

            all_matches_models: List[JobPosting] = []

            if job_keywords:
                keyword_matches_models = self._enhanced_keyword_matching(session, job_keywords, limit * 2)
                all_matches_models.extend(keyword_matches_models)
                logger.info(f"Found {len(keyword_matches_models)} keyword matches in database (SQLAlchemy)")

            if overall_field:
                field_matches_models = self._match_by_field(session, overall_field, limit)
                all_matches_models.extend(field_matches_models)
                logger.info(f"Found {len(field_matches_models)} field matches in database (SQLAlchemy)")
            
            if user_skills: # Added skill matching
                skill_matches_models = self._match_by_skills(session, user_skills, limit)
                all_matches_models.extend(skill_matches_models)
                logger.info(f"Found {len(skill_matches_models)} skill matches in database (SQLAlchemy)")


            if len(all_matches_models) < 10: # If not enough matches, get recent quality jobs
                recent_jobs_models = self._get_recent_quality_jobs(session, limit=30)
                all_matches_models.extend(recent_jobs_models)
                logger.info(f"Added {len(recent_jobs_models)} recent jobs from database (SQLAlchemy)")

            # Deduplicate JobPosting model instances based on a unique key (e.g., id or job_url)
            unique_job_models = {job.id: job for job in all_matches_models}.values()
            
            # Convert models to dicts and enhance scoring
            # This part also needs to handle updating user_profile_match in the DB
            unique_matches_dicts = []
            for job_model in unique_job_models:
                job_dict = self._job_model_to_dict(job_model)
                relevance_score = self._calculate_enhanced_relevance_score(job_dict, profile_data.get('job_title_keywords', []))
                job_dict['relevance_score'] = relevance_score
                
                # Update user_profile_match in the database
                job_model.user_profile_match = float(relevance_score) # Ensure it's float
                session.add(job_model) # Add to session for update tracking
                unique_matches_dicts.append(job_dict)
            
            session.commit() # Commit updates to user_profile_match

            final_matches = sorted(unique_matches_dicts, key=lambda x: x.get('relevance_score', 0), reverse=True)[:limit]
            logger.info(f"Returning {len(final_matches)} database matches for user {user_session_id}")
            return final_matches

        except Exception as e:
            logger.error(f"Error getting job matches from database (SQLAlchemy): {e}")
            session.rollback() # Rollback on error
            return []

    def _job_model_to_dict(self, job_model: JobPosting) -> Dict:
        """Converts a JobPosting SQLAlchemy model to a dictionary."""
        return {
            column.name: getattr(job_model, column.name)
            for column in job_model.__table__.columns
        }

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
        """Search for student-specific jobs (Kept as SQLite for now if specific non-ORM logic exists, or refactor to ORM)"""
        # This function was not directly used by get_profile_job_matches in the refactored path.
        # If needed, it should also be converted to SQLAlchemy. For now, marking as potentially deprecated if not used.
        logger.warning("_search_student_jobs is likely deprecated or needs ORM conversion.")
        # ... (original SQLite implementation or raise NotImplementedError) ...
        return []

    def _enhanced_keyword_matching(self, session: Session, job_keywords: List[str], limit: int) -> List[JobPosting]:
        """Enhanced keyword matching using SQLAlchemy."""
        if not job_keywords:
            return []
        
        try:
            keyword_filters = []
            for keyword in job_keywords:
                kw_lower = f'%{keyword.lower()}%'
                keyword_filters.append(or_(
                    JobPosting.title.ilike(kw_lower),
                    JobPosting.description.ilike(kw_lower)
                ))
            
            query = session.query(JobPosting).filter(or_(*keyword_filters))
            
            # Add ordering by scraped_timestamp (assuming newer is better)
            query = query.order_by(desc(JobPosting.scraped_timestamp))
            
            return query.limit(limit).all()
            
        except Exception as e:
            logger.error(f"Error in SQLAlchemy keyword matching: {e}")
            return []

    def _match_by_field(self, session: Session, overall_field: str, limit: int) -> List[JobPosting]:
        """Match jobs by overall field using SQLAlchemy."""
        if not overall_field:
            return []
        try:
            field_lower = f'%{overall_field.lower()}%'
            # Assuming 'description' or 'title' might contain field info.
            # Or if there's a more specific column like 'company_industry' that could match.
            query = session.query(JobPosting).filter(
                or_(
                    JobPosting.description.ilike(field_lower),
                    JobPosting.title.ilike(field_lower),
                    JobPosting.company_industry.ilike(field_lower) # Added industry match
                )
            )
            query = query.order_by(desc(JobPosting.scraped_timestamp)) # Prioritize recent
            return query.limit(limit).all()
        except Exception as e:
            logger.error(f"Error in SQLAlchemy matching by field: {e}")
            return []

    def _match_by_skills(self, session: Session, user_skills: List[str], limit: int) -> List[JobPosting]:
        """Match jobs by skills using SQLAlchemy."""
        if not user_skills:
            return []
        
        try:
            skill_filters = []
            for skill in user_skills:
                skill_lower = f'%{skill.lower()}%'
                skill_filters.append(or_(
                    JobPosting.title.ilike(skill_lower),
                    JobPosting.description.ilike(skill_lower)
                    # Consider matching against a dedicated skills column if it existed in JobPosting
                ))
            
            query = session.query(JobPosting).filter(or_(*skill_filters))
            query = query.order_by(desc(JobPosting.scraped_timestamp)) # Prioritize recent
            
            return query.limit(limit).all()
        except Exception as e:
            logger.error(f"Error in SQLAlchemy matching by skills: {e}")
            return []

    def _get_recent_quality_jobs(self, session: Session, limit: int = 30) -> List[JobPosting]:
        """Get recent quality jobs as fallback using SQLAlchemy."""
        try:
            # Define "quality" jobs (e.g., title and company are not null)
            query = session.query(JobPosting).filter(
                and_(
                    JobPosting.title != None, JobPosting.title != '',
                    JobPosting.company != None, JobPosting.company != ''
                )
            )
            query = query.order_by(desc(JobPosting.scraped_timestamp))
            return query.limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting recent SQLAlchemy jobs: {e}")
            return []

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
                str(job.get('title', '')).strip().lower(),
                str(job.get('company', '')).strip().lower(),
                str(job.get('location', '')).strip().lower()
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
    Wrapper function to run profile-based job search using SQLAlchemy session.
    """
    Base.metadata.create_all(bind=engine) # Ensure schema is up-to-date
    session = SessionLocal()
    try:
        matcher = ProfileJobMatcher()
        # Update user's last search timestamp before running the search
        user_profile = session.query(UserProfile).filter(UserProfile.user_session_id == profile_data.get('user_session_id')).first()
        if user_profile:
            user_profile.last_search_timestamp = datetime.now()
            session.commit()
            logger.info(f"Updated last_search_timestamp for user {profile_data.get('user_session_id')}")
        
        results = matcher.run_profile_based_search(session, profile_data) # Pass the session
        
        # If live scraping was successful and returned jobs, ensure user_profile_match is updated
        # This part is tricky as run_profile_based_search itself might not return JobPosting models directly if it uses indeed_scraper
        # For now, assume run_profile_based_search handles user_profile_match for its live scraped jobs internally
        # or that the database fallback path (get_profile_job_matches) handles it.
        # A more robust solution would be for scrape_indeed_jobs_with_profile to also return job IDs or allow updates.
        
        # Let's refine `run_profile_based_search` to update user_profile_match for newly scraped jobs
        if results.get('source') == 'live_scraping' and results.get('jobs'):
            job_urls_to_update = {job['job_url']: job.get('relevance_score', 0) for job in results['jobs'] if job.get('job_url')}
            if job_urls_to_update:
                job_models_to_update = session.query(JobPosting).filter(JobPosting.job_url.in_(job_urls_to_update.keys())).all()
                for job_model in job_models_to_update:
                    score = job_urls_to_update.get(job_model.job_url)
                    if score is not None:
                        job_model.user_profile_match = float(score)
                session.commit()
                logger.info(f"Updated user_profile_match for {len(job_models_to_update)} live scraped jobs.")

        return results
    except Exception as e:
        logger.error(f"Error in run_profile_job_search wrapper: {e}")
        session.rollback()
        return {"error": str(e), "total_jobs_found": 0, "jobs": [], "source": "error_wrapper"}
    finally:
        session.close()


def get_user_job_matches(user_session_id: str, limit: int = 50) -> List[Dict]:
    """
    Wrapper function to get job matches for a specific user using SQLAlchemy session.
    """
    Base.metadata.create_all(bind=engine) # Ensure schema is up-to-date
    session = SessionLocal()
    try:
        matcher = ProfileJobMatcher()
        # Update user's last search timestamp
        user_profile = session.query(UserProfile).filter(UserProfile.user_session_id == user_session_id).first()
        if user_profile:
            user_profile.last_search_timestamp = datetime.now()
            session.commit()
            logger.info(f"Updated last_search_timestamp for user {user_session_id}")

        return matcher.get_profile_job_matches(session, user_session_id, limit) # Pass the session
    except Exception as e:
        logger.error(f"Error in get_user_job_matches wrapper: {e}")
        session.rollback()
        return []
    finally:
        session.close()

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
        results = matcher.run_profile_based_search(SessionLocal(), test_profile)
        print(f"Search results: {results}")
        
    except Exception as e:
        print(f"Test failed: {e}")
