import os
import sqlite3
import re
import json
import logging
import time
from typing import Dict, List, Optional, Union
from datetime import datetime

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
    from langchain_together import Together
except ImportError as e:
    print(f"Required package not installed: {e}")
    print("Please run: pip install langchain-together")
    exit(1)

# Import existing modules
try:
    from profile_job_matcher import get_user_job_matches, get_database_enrichment_status
    from indeed_scraper import DB_NAME, TABLE_NAME
except ImportError as e:
    print(f"Could not import required modules: {e}")
    exit(1)

# Database and ORM imports
import sqlite3 # Keep for now if other methods still use it (e.g., storing evaluations)
from database_models import (
    SessionLocal, UserProfile, 
    UserProfileTargetRole, UserProfileKeyword, UserProfileSkill,
    UserProfileLanguage, UserProfileJobType, UserProfileLocation,
    UserEducation, UserExperience, CVJobEvaluation, JobEvaluationDetail, JobPosting
) # Add all necessary models
from sqlalchemy.orm import joinedload, Session # Add Session for type hinting

# Configuration
TOGETHER_API_KEY = os.getenv('TOGETHER_API_KEY')

if not TOGETHER_API_KEY:
    print("Please set TOGETHER_API_KEY in your .env file")
    print("Example: TOGETHER_API_KEY=your_api_key_here")
    exit(1)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cv_job_evaluator.log'),
        logging.StreamHandler()
    ]
)

class CVJobEvaluator:
    """
    AI-powered CV to job matching evaluator with detailed feedback
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or TOGETHER_API_KEY
        
        # Initialize LLM with the most advanced available model
        try:
            self.llm = Together(
                model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
                api_key=self.api_key,
                temperature=0.1,
                max_tokens=4096,   
                top_p=0.9,
                repetition_penalty=1.1
            )
            
            # Test LLM connection
            test_response = self.llm.invoke("Test connection. Reply with: OK")
            logging.info(f"CV Job Evaluator LLM initialized with Llama-3.3-70B-Instruct-Turbo")
            
        except Exception as e:
            logging.error(f"Failed to initialize LLM: {e}")
            raise e
    
    def get_user_profile_data(self, user_session_id: str) -> Optional[Dict]:
        """Get user profile data from database using SQLAlchemy ORM."""
        session: Session = SessionLocal()
        try:
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
                logging.warning(f"No UserProfile found for user_session_id: {user_session_id} in CVJobEvaluator")
                return None

            profile_dict = {
                "user_session_id": user_profile.user_session_id,
                "submission_timestamp": user_profile.submission_timestamp.isoformat() if user_profile.submission_timestamp else None,
                "user_id_input": user_profile.user_id_input,
                "overall_field": user_profile.overall_field,
                "personal_description": user_profile.personal_description,
                "total_experience": user_profile.total_experience,
                "remote_openness": user_profile.remote_openness,
                "analysis_preference": user_profile.analysis_preference,
                "target_roles_industries_selected": [tr.role_or_industry_name for tr in user_profile.target_roles if tr.role_or_industry_name],
                 # Assuming custom roles are merged into target_roles_industries_selected from the form, 
                 # or would need a separate field if stored differently. For now, this matches profile_job_matcher's typical output.
                "target_roles_industries_custom": [], # Placeholder if this distinct list is needed and not part of target_roles
                "job_title_keywords": [kw.keyword for kw in user_profile.keywords if kw.keyword],
                "current_skills_selected": [s.skill_name for s in user_profile.skills if s.skill_name],
                "current_skills_custom": [], # Placeholder, similar to custom roles
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
            logging.info(f"Retrieved and normalized UserProfile for {user_session_id} in CVJobEvaluator.")
            return profile_dict
            
        except Exception as e:
            logging.error(f"Error getting user profile via SQLAlchemy in CVJobEvaluator: {e}")
            session.rollback() # Rollback on error
            return None
        finally:
            session.close()

    def evaluate_cv_against_specific_jobs(self, user_session_id: str, jobs_list: List[Dict], profile_data: Dict = None) -> Dict:
        """
        Evaluate CV against a specific list of jobs (rather than fetching from database)
        This ensures we analyze exactly the same jobs shown in the UI
        """
        try:
            # Get user profile data if not provided
            if not profile_data:
                profile_data = self.get_user_profile_data(user_session_id)
                if not profile_data:
                    return {"error": "Could not retrieve user profile data"}
            
            # Format the specific jobs for evaluation
            jobs_text = self.format_jobs_for_evaluation(jobs_list)
            
            # Format user profile
            profile_text = self.format_profile_for_evaluation(profile_data)
            
            # Log the evaluation attempt
            logging.info(f"Starting CV evaluation for user {user_session_id} against {len(jobs_list)} specific jobs")
            
            # Try AI evaluation first
            if self.api_key and self.api_key.strip():
                try:
                    # Pass the actual jobs to the AI evaluation
                    evaluation_result = self._evaluate_with_ai(profile_text, jobs_text, len(jobs_list), actual_jobs=jobs_list)
                    
                    # Store evaluation in database with job references
                    self._store_evaluation_result(user_session_id, evaluation_result, jobs_list)
                    
                    # Add metadata
                    evaluation_result.update({
                        'evaluation_timestamp': datetime.now().isoformat(),
                        'jobs_evaluated': len(jobs_list),
                        'evaluation_source': 'specific_jobs_list',
                        'user_session_id': user_session_id
                    })
                    
                    logging.info(f"CV evaluation completed successfully for {len(jobs_list)} jobs")
                    return evaluation_result
                    
                except Exception as ai_error:
                    logging.error(f"AI evaluation failed: {ai_error}")
                    # Fall back to basic evaluation
                    return self._fallback_evaluation(profile_data, jobs_list, str(ai_error))
            else:
                logging.warning("No API key available, using fallback evaluation")
                return self._fallback_evaluation(profile_data, jobs_list, "No API key configured")
                
        except Exception as e:
            logging.error(f"Error in evaluate_cv_against_specific_jobs: {e}")
            return {
                "error": f"Evaluation failed: {str(e)}",
                "evaluation_timestamp": datetime.now().isoformat(),
                "jobs_evaluated": len(jobs_list) if jobs_list else 0
            }

    def _fallback_evaluation(self, profile_data: Dict, jobs_list: List[Dict], error_reason: str) -> Dict:
        """
        Provide basic evaluation when AI is not available
        """
        try:
            evaluations = []
            total_score = 0
            
            # Extract user skills for matching
            user_skills = set()
            user_skills.update(profile_data.get('current_skills_selected', []))
            user_skills.update(profile_data.get('current_skills_custom', []))
            user_skills = {skill.lower().strip() for skill in user_skills if skill}
            
            for job in jobs_list:
                # Basic skill matching
                job_description = job.get('description', '').lower()
                job_title = job.get('title', '').lower()
                
                # Count skill matches
                skill_matches = sum(1 for skill in user_skills if skill in job_description or skill in job_title)
                max_possible_matches = max(len(user_skills), 1)
                match_score = min(90, int((skill_matches / max_possible_matches) * 100))
                
                # Basic assessment
                if match_score >= 70:
                    overall_fit = "Strong match based on skills alignment"
                    likelihood = "Medium"
                elif match_score >= 50:
                    overall_fit = "Moderate match with some skill overlap"
                    likelihood = "Medium"
                else:
                    overall_fit = "Limited match, may require skill development"
                    likelihood = "Low"
                
                evaluation = {
                    'job_title': job.get('title', 'Unknown'),
                    'company': job.get('company', 'Unknown'),
                    'location': job.get('location', 'Unknown'),
                    'match_score': match_score,
                    'overall_fit': overall_fit,
                    'reality_check': f"Basic compatibility assessment - {skill_matches} skills matched",
                    'strengths': f"Matched skills: {', '.join([s for s in user_skills if s in job_description or s in job_title])}" if skill_matches > 0 else "Profile alignment with job requirements",
                    'critical_gaps': "Detailed gap analysis requires AI evaluation",
                    'recommendations': f"Focus on highlighting relevant experience and consider skill development",
                    'seniority_match': 'Not assessed in basic mode',
                    'likelihood': likelihood,
                    'experience_gap': 'Detailed experience analysis requires AI evaluation',
                    'job_url': job.get('job_url', ''),
                    'fallback_mode': True
                }
                
                evaluations.append(evaluation)
                total_score += match_score
            
            # Create summary
            avg_score = int(total_score / len(jobs_list)) if jobs_list else 0
            high_matches = sum(1 for e in evaluations if e['match_score'] >= 70)
            medium_matches = sum(1 for e in evaluations if 50 <= e['match_score'] < 70)
            low_matches = sum(1 for e in evaluations if e['match_score'] < 50)
            
            return {
                'evaluations': evaluations,
                'summary': {
                    'average_match_score': avg_score,
                    'score_distribution': {
                        'high (70-100)': high_matches,
                        'medium (50-69)': medium_matches,
                        'low (0-49)': low_matches
                    }
                },
                'evaluation_model': f'Fallback mode: {error_reason}',
                'evaluation_timestamp': datetime.now().isoformat(),
                'jobs_evaluated': len(jobs_list),
                'fallback_mode': True,
                'evaluation_source': 'specific_jobs_fallback'
            }
            
        except Exception as e:
            logging.error(f"Fallback evaluation failed: {e}")
            return {
                "error": f"Both AI and fallback evaluation failed: {str(e)}",
                "evaluation_timestamp": datetime.now().isoformat(),
                "jobs_evaluated": len(jobs_list) if jobs_list else 0,
                "fallback_mode": True
            }

    def format_profile_for_evaluation(self, profile_data: Dict) -> str:
        """Format user profile data for AI evaluation"""
        
        # Extract profile information
        name = profile_data.get('user_id_input', 'Candidate')
        overall_field = profile_data.get('overall_field', 'Unknown')
        total_experience = profile_data.get('total_experience', 'Unknown')
        personal_description = profile_data.get('personal_description', '')
        
        # Skills
        all_skills = []
        all_skills.extend(profile_data.get('current_skills_selected', []))
        all_skills.extend(profile_data.get('current_skills_custom', []))
        skills_text = ', '.join(all_skills) if all_skills else 'Not specified'
        
        # Target roles
        target_roles = []
        target_roles.extend(profile_data.get('target_roles_industries_selected', []))
        target_roles.extend(profile_data.get('target_roles_industries_custom', []))
        target_roles_text = ', '.join(target_roles) if target_roles else 'Not specified'
        
        # Education
        education_entries = profile_data.get('education_entries', [])
        education_text = ""
        for edu in education_entries:
            if edu.get('degree') and edu.get('field_of_study'):
                education_text += f"- {edu['degree']} in {edu['field_of_study']}"
                if edu.get('institution'):
                    education_text += f" from {edu['institution']}"
                if edu.get('graduation_year'):
                    education_text += f" ({edu['graduation_year']})"
                education_text += "\n"
        
        if not education_text:
            education_text = "Not specified"
        
        # Work experience
        work_entries = profile_data.get('work_experience_entries', [])
        work_text = ""
        for work in work_entries:
            if work.get('job_title') and work.get('company'):
                work_text += f"- {work['job_title']} at {work['company']}"
                if work.get('years_in_role'):
                    work_text += f" ({work['years_in_role']} years)"
                if work.get('skills_responsibilities'):
                    work_text += f" - {work['skills_responsibilities'][:150]}..."
                work_text += "\n"
        
        if not work_text:
            work_text = "Not specified"
        
        # Job preferences
        job_types = ', '.join(profile_data.get('job_types', []))
        locations = ', '.join(profile_data.get('preferred_locations_dk', []))
        languages = ', '.join(profile_data.get('job_languages', []))
        remote_preference = profile_data.get('remote_openness', 'Not specified')
        
        # Format the complete profile
        profile_text = f"""
CANDIDATE PROFILE:

Personal Information:
- Name/ID: {name}
- Field: {overall_field}
- Total Experience: {total_experience}
- Preferred Job Types: {job_types or 'Not specified'}
- Preferred Locations: {locations or 'Not specified'}
- Languages: {languages or 'Not specified'}
- Remote Work Preference: {remote_preference}

Professional Summary:
{personal_description or 'Not provided'}

Target Roles:
{target_roles_text}

Current Skills:
{skills_text}

Education Background:
{education_text}

Work Experience:
{work_text}
"""
        
        return profile_text

    def format_jobs_for_evaluation(self, jobs: List[Dict]) -> str:
        """Format job listings for AI evaluation"""
        jobs_text = ""
        
        for i, job in enumerate(jobs):
            job_num = i + 1
            
            # Clean and format job data
            title = job.get('title', 'Unknown Position')
            company = job.get('company', 'Unknown Company')
            location = job.get('location', 'Unknown Location')
            industry = job.get('company_industry', 'Unknown Industry')
            job_type = job.get('job_type', 'Unknown Type')
            description = job.get('description', 'No description available')
            
            # Truncate description if too long
            if len(description) > 800:
                description = description[:800] + "..."
            
            jobs_text += f"""
JOB_{job_num}:
Title: {title}
Company: {company}
Location: {location}
Industry: {industry}
Job Type: {job_type}
Description: {description}

"""
        
        return jobs_text

    def _generate_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        """Generate response with retry logic for API failures"""
        for attempt in range(max_retries):
            try:
                response = self.llm.invoke(prompt)
                return response
            except Exception as e:
                logging.warning(f"LLM generation attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise e
                # Wait before retry
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
        
        raise Exception("All retry attempts failed")

    def store_evaluation_results(self, user_session_id: str, evaluation_results: Dict):
        """Store evaluation results in database for future reference"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # Create evaluation results table if it doesn't exist
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cv_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_session_id TEXT,
                evaluation_data TEXT,
                evaluation_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                jobs_evaluated INTEGER,
                average_score REAL
            )
            """)
            
            # Store the evaluation
            cursor.execute("""
            INSERT INTO cv_evaluations 
            (user_session_id, evaluation_data, jobs_evaluated, average_score)
            VALUES (?, ?, ?, ?)
            """, (
                user_session_id,
                json.dumps(evaluation_results),
                evaluation_results.get('jobs_evaluated', 0),
                evaluation_results.get('summary', {}).get('average_match_score', 0)
            ))
            
            conn.commit()
            logging.info(f"Stored evaluation results for user {user_session_id}")
            
        except Exception as e:
            logging.error(f"Error storing evaluation results: {e}")
        finally:
            conn.close()

    def get_latest_evaluation(self, user_session_id: str) -> Dict:
        """Get the latest evaluation results for a user"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            SELECT evaluation_data FROM cv_evaluations 
            WHERE user_session_id = ? 
            ORDER BY evaluation_timestamp DESC LIMIT 1
            """, (user_session_id,))
            
            result = cursor.fetchone()
            if result:
                return json.loads(result[0])
            else:
                return {"error": "No evaluation found for this user"}
                
        except Exception as e:
            logging.error(f"Error getting latest evaluation: {e}")
            return {"error": f"Database error: {str(e)}"}
        finally:
            conn.close()

    def generate_improvement_plan(self, user_session_id: str) -> Dict:
        """Generate personalized improvement plan based on evaluation results"""
        try:
            # Get latest evaluation
            latest_eval = self.get_latest_evaluation(user_session_id)
            if "error" in latest_eval:
                return {"error": "No evaluation found to base improvement plan on"}
            
            # Get user profile
            profile_data = self.get_user_profile_data(user_session_id)
            if not profile_data:
                return {"error": "User profile not found"}
            
            # Extract key insights from evaluations
            evaluations = latest_eval.get('evaluations', [])
            if not evaluations:
                return {"error": "No job evaluations found"}
            
            # Analyze common gaps and strengths
            common_gaps = []
            common_strengths = []
            avg_score = latest_eval.get('summary', {}).get('average_match_score', 0)
            
            for eval in evaluations:
                if eval.get('critical_gaps'):
                    common_gaps.append(eval['critical_gaps'])
                if eval.get('strengths'):
                    common_strengths.append(eval['strengths'])
            
            # Create improved, more focused improvement plan prompt
            improvement_prompt = f"""Create a concise, actionable 6-month career improvement plan for a Danish job seeker.

PROFILE CONTEXT:
Field: {profile_data.get('overall_field', 'Unknown')}
Experience: {profile_data.get('total_experience', 'Unknown')}
Skills: {', '.join(profile_data.get('current_skills_selected', [])[:5])}
Targets: {', '.join(profile_data.get('target_roles_industries_selected', [])[:3])}

EVALUATION INSIGHTS:
Key Strengths: {' | '.join(common_strengths[:2])}
Main Gaps: {' | '.join(common_gaps[:2])}

OUTPUT STRUCTURE (keep each section to 2-3 bullet points max):

CURRENT STATUS:
[One sentence assessment of market position]

IMMEDIATE ACTIONS (0-2 months):
[3 specific, actionable steps they can start immediately]

MEDIUM TERM (2-4 months):
[2-3 skills/certifications to develop based on Danish job market]

LONG TERM (4-6 months):
[2 strategic positioning goals]

SKILL DEVELOPMENT PRIORITIES:
[Top 3 skills ranked by Danish market demand]

CERTIFICATION RECOMMENDATIONS:
[2-3 specific, relevant certifications]

APPLICATION STRATEGY:
[3 tactical improvements for Danish job applications]

NETWORKING SUGGESTIONS:
[2-3 Denmark-specific networking approaches]

Focus on Denmark job market, be specific and actionable. Keep concise - quality over quantity."""
            
            try:
                response = self._generate_with_retry(improvement_prompt, max_retries=2)
                
                return {
                    "user_session_id": user_session_id,
                    "plan_generated": datetime.now().isoformat(),
                    "based_on_evaluation": latest_eval.get('evaluation_timestamp'),
                    "improvement_plan": response,
                    "avg_score_context": avg_score,
                    "jobs_analyzed": len(evaluations)
                }
                
            except Exception as e:
                logging.error(f"LLM failed for improvement plan: {e}")
                # Return basic improvement plan
                return self._create_basic_improvement_plan(profile_data, avg_score, common_gaps)
                
        except Exception as e:
            logging.error(f"Error generating improvement plan: {e}")
            return {"error": f"Failed to generate improvement plan: {str(e)}"}

    def _create_basic_improvement_plan(self, profile_data: Dict, avg_score: float, gaps: List[str]) -> Dict:
        """Create a basic improvement plan when AI is unavailable"""
        field = profile_data.get('overall_field', 'Professional')
        experience = profile_data.get('total_experience', 'Unknown')
        
        basic_plan = f"""
CURRENT STATUS:
You're in the {field} field with {experience} of experience. Your current average match score is {avg_score}%, indicating good potential with room for targeted improvements.

IMMEDIATE ACTIONS (0-2 months):
• Update your CV to better highlight relevant keywords and achievements
• Tailor your applications to specifically address job requirements
• Practice technical interviews and prepare examples of your work
• Set up job alerts and apply to 3-5 positions per week

MEDIUM TERM (2-4 months):
• Develop skills in high-demand areas for your field
• Complete an online course or certification
• Build a portfolio or update your LinkedIn profile

LONG TERM (4-6 months):
• Establish yourself as a thought leader in your area
• Expand your professional network
• Consider advanced certifications or specializations

SKILL DEVELOPMENT PRIORITIES:
• Technical skills relevant to your target roles
• Communication and presentation skills
• Industry-specific knowledge and trends

APPLICATION STRATEGY:
• Use keywords from job postings in your CV
• Provide specific examples and quantifiable achievements
• Address any experience gaps honestly and positively

NETWORKING SUGGESTIONS:
• Join professional associations in your field
• Attend industry meetups and conferences
• Connect with professionals on LinkedIn
"""
        
        return {
            "user_session_id": profile_data.get('user_session_id', 'unknown'),
            "plan_generated": datetime.now().isoformat(),
            "improvement_plan": basic_plan,
            "fallback_mode": True,
            "avg_score_context": avg_score
        }
    
    def _evaluate_with_ai(self, profile_text: str, jobs_text: str, num_jobs: int, actual_jobs: List[Dict] = None) -> Dict:
        """
        Perform AI evaluation using actual job data
        """
        # Create evaluation prompt using the same format as the main method
        evaluation_prompt = f"""You are an expert Danish career counselor and recruiter. Evaluate how well this candidate's CV/profile matches specific job opportunities.

CRITICAL FORMATTING: You must respond with EXACTLY this format for each job. Do not deviate from this structure.

{profile_text}

JOBS TO EVALUATE:
{jobs_text}

RESPONSE FORMAT REQUIRED:
For each job, use EXACTLY this format (no extra text, no markdown, no bullets):

JOB_1:
MATCH_SCORE: 75
OVERALL_FIT: Good
SENIORITY_MATCH: Good Fit
EXPERIENCE_GAP: Missing 2 years of senior experience but strong technical skills compensate
REALITY_CHECK: Strong candidate with 75% compatibility. Good chance of progressing to interview stage if application is well-tailored
STRENGTHS: Excellent Python skills, relevant project experience, strong analytical background matches job requirements well
CRITICAL_GAPS: Senior leadership experience needed, specific domain knowledge in fintech would strengthen application
MINOR_GAPS: Could benefit from certification in data visualization tools, public speaking experience
RECOMMENDATIONS: Emphasize Python projects and analytical achievements in application, consider highlighting transferable leadership experience
LIKELIHOOD: Medium

JOB_2:
MATCH_SCORE: 82
OVERALL_FIT: Excellent
SENIORITY_MATCH: Perfect Match
EXPERIENCE_GAP: No significant gaps, experience level aligns well with requirements
REALITY_CHECK: Excellent candidate with 82% compatibility. High probability of securing interview with proper application
STRENGTHS: Perfect experience match, strong technical skills in required technologies, proven track record in similar roles
CRITICAL_GAPS: None identified - strong alignment across all key requirements
MINOR_GAPS: Additional cloud platform experience would be beneficial but not critical
RECOMMENDATIONS: Apply immediately, highlight specific achievements with quantified results, prepare for technical interview
LIKELIHOOD: High

IMPORTANT RULES:
- Use EXACTLY the field names shown (MATCH_SCORE, OVERALL_FIT, etc.)
- MATCH_SCORE must be a number 0-100
- OVERALL_FIT: Excellent/Good/Fair/Poor
- LIKELIHOOD: High/Medium/Low
- Keep each field response concise but informative
- Be realistic with scores - most jobs should score 40-80%

Start evaluation now:"""

        try:
            # Get AI evaluation with enhanced retry logic
            response = self._generate_with_retry(evaluation_prompt, max_retries=2)
            logging.info(f"Received evaluation response: {len(response)} characters")
            
            # Log first part of response for debugging
            logging.info(f"AI Response preview: {response[:300]}...")
            
            # Simple parsing for specific jobs evaluation
            evaluations = []
            total_score = 0
            
            # Split response by job sections
            job_sections = response.split('JOB_')[1:]  # Remove empty first element
            
            for i, section in enumerate(job_sections[:num_jobs]):
                # Use actual job data if provided, otherwise use defaults
                if actual_jobs and i < len(actual_jobs):
                    job_data = actual_jobs[i]
                    job_title = job_data.get('title', f'Job {i+1}')
                    company = job_data.get('company', 'Unknown')
                    location = job_data.get('location', 'Unknown')
                    job_url = job_data.get('job_url', '')
                    job_id = job_data.get('id', f'job_{i+1}')
                    company_industry = job_data.get('company_industry', 'Unknown')
                else:
                    job_title = f'Job {i+1}'
                    company = 'Unknown'
                    location = 'Unknown'
                    job_url = ''
                    job_id = f'job_{i+1}'
                    company_industry = 'Unknown'
                
                # Basic parsing to extract match score
                match_score = 50  # Default fallback score
                
                # Look for MATCH_SCORE pattern
                import re
                score_match = re.search(r'MATCH_SCORE[:\s]*(\d+)', section, re.IGNORECASE)
                if score_match:
                    try:
                        match_score = int(score_match.group(1))
                        match_score = max(0, min(100, match_score))  # Clamp between 0-100
                    except ValueError:
                        match_score = 50
                
                # Extract other fields with basic regex
                overall_fit = "Fair"
                fit_match = re.search(r'OVERALL[_\s]*FIT[:\s]*([^\n\r]+)', section, re.IGNORECASE)
                if fit_match:
                    overall_fit = fit_match.group(1).strip()
                
                likelihood = "Medium"
                likelihood_match = re.search(r'LIKELIHOOD[:\s]*([^\n\r]+)', section, re.IGNORECASE)
                if likelihood_match:
                    likelihood = likelihood_match.group(1).strip()
                
                # Extract seniority match
                seniority_match = "Requires assessment"
                seniority_search = re.search(r'SENIORITY[_\s]*MATCH[:\s]*([^\n\r]+)', section, re.IGNORECASE)
                if seniority_search:
                    seniority_match = seniority_search.group(1).strip()
                
                # Extract experience gap with better default
                experience_gap = "Experience level appears suitable for this role"
                exp_gap_search = re.search(r'EXPERIENCE[_\s]*GAP[:\s]*([^\n\r]+)', section, re.IGNORECASE)
                if exp_gap_search:
                    experience_gap = exp_gap_search.group(1).strip()
                
                # Extract strengths, gaps, recommendations with fallbacks
                strengths = "Profile shows relevant experience and skills"
                strengths_match = re.search(r'STRENGTHS[:\s]*([^\n\r]+)', section, re.IGNORECASE)
                if strengths_match:
                    strengths = strengths_match.group(1).strip()
                
                critical_gaps = "No critical gaps identified through automated analysis"
                gaps_match = re.search(r'CRITICAL[_\s]*GAPS[:\s]*([^\n\r]+)', section, re.IGNORECASE)
                if gaps_match:
                    critical_gaps = gaps_match.group(1).strip()
                
                # Extract minor gaps
                minor_gaps = "Minor skill enhancements could be beneficial"
                minor_gaps_search = re.search(r'MINOR[_\s]*GAPS[:\s]*([^\n\r]+)', section, re.IGNORECASE)
                if minor_gaps_search:
                    minor_gaps = minor_gaps_search.group(1).strip()
                
                recommendations = "Tailor application to highlight relevant skills and experience"
                rec_match = re.search(r'RECOMMENDATIONS[:\s]*([^\n\r]+)', section, re.IGNORECASE)
                if rec_match:
                    recommendations = rec_match.group(1).strip()
                
                reality_check = f"AI assessment indicates {match_score}% compatibility with this position"
                reality_match = re.search(r'REALITY[_\s]*CHECK[:\s]*([^\n\r]+)', section, re.IGNORECASE)
                if reality_match:
                    reality_check = reality_match.group(1).strip()
                
                evaluation = {
                    'job_number': i + 1,
                    'job_title': job_title,
                    'company': company,
                    'location': location,
                    'job_id': job_id,
                    'job_url': job_url,
                    'company_industry': company_industry,
                    'match_score': match_score,
                    'overall_fit': overall_fit,
                    'seniority_match': seniority_match,
                    'experience_gap': experience_gap,
                    'reality_check': reality_check,
                    'strengths': strengths,
                    'critical_gaps': critical_gaps,
                    'minor_gaps': minor_gaps,
                    'recommendations': recommendations,
                    'likelihood': likelihood,
                    'ai_parsed': True
                }
                
                evaluations.append(evaluation)
                total_score += match_score
            
            # Calculate summary
            avg_score = round(total_score / len(evaluations), 1) if evaluations else 0
            
            high_matches = sum(1 for e in evaluations if e['match_score'] >= 70)
            medium_matches = sum(1 for e in evaluations if 50 <= e['match_score'] < 70)
            low_matches = sum(1 for e in evaluations if e['match_score'] < 50)
            
            evaluation_results = {
                "evaluations": evaluations,
                "summary": {
                    "average_match_score": avg_score,
                    "score_distribution": {
                        "high (70-100)": high_matches,
                        "medium (50-69)": medium_matches,
                        "low (0-49)": low_matches
                    },
                    "best_matches": sorted(evaluations, key=lambda x: x['match_score'], reverse=True)[:3]
                },
                "evaluation_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "evaluation_type": "specific_jobs_ai",
                "parsing_success_rate": round(len(evaluations) / num_jobs * 100, 1) if num_jobs > 0 else 0
            }
            
            logging.info(f"AI evaluation completed successfully for {num_jobs} jobs")
            logging.info(f"Parsing success rate: {evaluation_results['parsing_success_rate']}%")
            
            return evaluation_results
            
        except Exception as e:
            logging.error(f"Error in _evaluate_with_ai: {e}")
            raise e

    def _store_evaluation_result(self, user_session_id: str, evaluation_result: Dict, jobs_list: List[Dict]):
        """
        Store evaluation results in database with job references
        """
        try:
            # Use the existing store_evaluation_results method
            self.store_evaluation_results(user_session_id, evaluation_result)
            logging.info(f"Stored evaluation results for {len(jobs_list)} specific jobs")
            
        except Exception as e:
            logging.error(f"Error storing evaluation result: {e}")
            # Don't raise the error - this is not critical for the evaluation to work
