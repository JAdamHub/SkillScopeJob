import sqlite3
import logging
import os
import json
from typing import Dict, List, Optional, Tuple
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
                model="meta-llama/Llama-3.3-70B-Instruct-Turbo",  # Latest and most capable model
                api_key=self.api_key,
                temperature=0.1,  # Increased slightly for more balanced responses
                max_tokens=4096,   
                top_p=0.9,         # Increased for more varied responses
                repetition_penalty=1.1  # Reduced to avoid too repetitive conservative assessments
            )
            
            # Test LLM connection
            test_response = self.llm.invoke("Test connection. Reply with: OK")
            logging.info(f"CV Job Evaluator LLM initialized with Llama-3.3-70B-Instruct-Turbo")
            
        except Exception as e:
            logging.error(f"Failed to initialize LLM: {e}")
            raise e
    
    def get_user_profile_data(self, user_session_id: str) -> Optional[Dict]:
        """Get user profile data from database"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            SELECT profile_data FROM user_profiles 
            WHERE user_session_id = ? 
            ORDER BY last_search_timestamp DESC LIMIT 1
            """, (user_session_id,))
            
            result = cursor.fetchone()
            if result:
                return json.loads(result[0])
            return None
            
        except Exception as e:
            logging.error(f"Error getting user profile: {e}")
            return None
        finally:
            conn.close()
    
    def get_top_job_matches(self, user_session_id: str, limit: int = 10) -> List[Dict]:
        """Get top job matches for evaluation"""
        try:
            matches = get_user_job_matches(user_session_id, limit=limit)
            
            # Filter out jobs without sufficient information
            filtered_matches = []
            for job in matches:
                if (job.get('title') and job.get('company') and 
                    job.get('description') and len(job['description']) > 100):
                    filtered_matches.append(job)
            
            return filtered_matches[:limit]
            
        except Exception as e:
            logging.error(f"Error getting job matches: {e}")
            return []
    
    def format_profile_for_evaluation(self, profile_data: Dict) -> str:
        """Format user profile data for AI evaluation"""
        # Extract key information
        skills = (profile_data.get('current_skills_selected', []) + 
                 profile_data.get('current_skills_custom', []))
        
        education = profile_data.get('education_entries', [])
        experience = profile_data.get('work_experience_entries', [])
        overall_field = profile_data.get('overall_field', '')
        total_experience = profile_data.get('total_experience', 'None')
        target_roles = (profile_data.get('target_roles_industries_selected', []) + 
                       profile_data.get('target_roles_industries_custom', []))
        
        # Format education
        education_text = []
        for edu in education:
            edu_line = f"{edu.get('degree', '')} in {edu.get('field_of_study', '')} from {edu.get('institution', '')}"
            if edu.get('graduation_year'):
                edu_line += f" ({edu['graduation_year']})"
            education_text.append(edu_line)
        
        # Format experience
        experience_text = []
        for exp in experience:
            exp_line = f"{exp.get('job_title', '')} at {exp.get('company', '')} - {exp.get('years_in_role', '0')} years"
            if exp.get('skills_responsibilities'):
                exp_line += f". Skills: {exp['skills_responsibilities']}"
            experience_text.append(exp_line)
        
        profile_summary = f"""
CANDIDATE PROFILE:
Overall Field: {overall_field}
Total Experience: {total_experience}
Target Roles: {', '.join(target_roles) if target_roles else 'Not specified'}

SKILLS: {', '.join(skills) if skills else 'None listed'}

EDUCATION:
{chr(10).join(education_text) if education_text else 'None listed'}

WORK EXPERIENCE:
{chr(10).join(experience_text) if experience_text else 'None listed'}

PERSONAL DESCRIPTION: {profile_data.get('personal_description', 'Not provided')}
"""
        return profile_summary
    
    def format_jobs_for_evaluation(self, jobs: List[Dict]) -> str:
        """Format job postings for AI evaluation"""
        jobs_text = []
        
        for i, job in enumerate(jobs, 1):
            # Truncate description to reasonable length
            description = job.get('description', '')
            if len(description) > 800:
                description = description[:800] + "..."
            
            job_text = f"""
JOB #{i}:
Title: {job.get('title', 'N/A')}
Company: {job.get('company', 'N/A')}
Location: {job.get('location', 'N/A')}
Job Type: {job.get('job_type', 'N/A')}
Industry: {job.get('company_industry', 'N/A')}
Remote: {'Yes' if job.get('is_remote') else 'No'}

Job Description:
{description}

Company Description: {job.get('company_description', 'N/A')}
"""
            jobs_text.append(job_text)
        
        return "\n" + "="*80 + "\n".join(jobs_text)
    
    def evaluate_cv_job_matches(self, user_session_id: str, max_jobs: int = 10) -> Dict:
        """
        Evaluate how well user's CV matches available job postings
        """
        logging.info(f"Starting CV-job evaluation for user {user_session_id}")
        
        # Get user profile
        profile_data = self.get_user_profile_data(user_session_id)
        if not profile_data:
            return {"error": "User profile not found"}
        
        # Get job matches
        job_matches = self.get_top_job_matches(user_session_id, max_jobs)
        if not job_matches:
            return {"error": "No job matches found for evaluation"}
        
        logging.info(f"Evaluating {len(job_matches)} jobs against user profile")
        
        # Format data for AI
        profile_text = self.format_profile_for_evaluation(profile_data)
        jobs_text = self.format_jobs_for_evaluation(job_matches)
        
        # Create balanced evaluation prompt
        evaluation_prompt = f"""You are an experienced Danish recruiter with 15+ years of experience. You must evaluate candidates using REALISTIC but FAIR standards that reflect the actual Danish job market. Be honest but constructive.

DANISH RECRUITMENT CONTEXT:
1. STUDENTS vs PROFESSIONALS: A student finishing in 2026 is entry-level but CAN be competitive for appropriate roles
2. EDUCATION MATTERS: Danish companies value education highly - strong academic background counts significantly
3. TRANSFERABLE SKILLS: Skills from projects, internships, and studies ARE valuable and recognized
4. ENTRY LEVEL OPPORTUNITIES: Many Danish companies have graduate programs and entry-level positions
5. GROWTH POTENTIAL: Recruiters look for potential, not just current experience

{profile_text}

JOBS TO EVALUATE:
{jobs_text}

BALANCED SCORING GUIDELINES:
- Student graduating 2026 + Senior role (5+ years required) = 20-35 points (honest about experience gap)
- Student graduating 2026 + Mid-level role (3+ years) = 35-55 points (possible with exceptional profile)
- Student graduating 2026 + Junior/Entry role = 55-80 points (appropriate level match)
- Student graduating 2026 + Graduate/Trainee program = 70-90 points (ideal match)
- Strong academic background in relevant field = +10-15 points bonus
- Relevant project/internship experience = +5-10 points bonus

REALISTIC EXAMPLES:
- "Business Data Science Student 2026" + "Senior Data Scientist 5+ years" = SCORE: 25 (Experience gap too large, but has relevant education)
- "Business Data Science Student 2026" + "Data Analyst Graduate Program" = SCORE: 80 (Excellent match for entry level)
- "Business Data Science Student 2026" + "Junior Business Analyst" = SCORE: 65 (Good entry match with room to grow)

RESPONSE FORMAT:
For each job, respond with exactly this structure:

JOB_1:
MATCH_SCORE: [0-100] - Use the balanced guidelines above
OVERALL_FIT: [Excellent/Good/Fair/Poor/Very Poor]
SENIORITY_MATCH: [Perfect Match/Slight Stretch/Underqualified/Major Gap]
EXPERIENCE_GAP: [X years short/Good match/Perfect fit]
REALITY_CHECK: [Honest assessment of actual interview chances in Danish market]
STRENGTHS: [List genuine matching qualifications from their background]
CRITICAL_GAPS: [Major missing requirements that need addressing]
MINOR_GAPS: [Skills that could be developed or aren't deal-breakers]
RECOMMENDATIONS: [Constructive actions - may include applying despite gaps]
LIKELIHOOD: [High/Medium/Low/Very Low] - Be realistic but not crushing

DANISH RECRUITER MINDSET - BALANCED APPROACH:
- "Education and potential matter as much as experience for entry-level roles"
- "We invest in promising graduates who show the right foundation"
- "Strong academic background can partially compensate for limited work experience"
- "Graduate programs exist specifically for talented students transitioning to work"

REMEMBER: Be honest about limitations but recognize the value of education, projects, and potential. Danish companies DO hire graduates - provide constructive feedback that helps them target appropriate opportunities.

START EVALUATION:"""

        try:
            # Get AI evaluation
            response = self.llm.invoke(evaluation_prompt)
            logging.info(f"Received evaluation response: {len(response)} characters")
            
            # Parse the response with enhanced parsing
            evaluation_results = self.parse_enhanced_evaluation_response(response, job_matches)
            
            # Add metadata and validation
            evaluation_results.update({
                "user_session_id": user_session_id,
                "evaluation_timestamp": datetime.now().isoformat(),
                "jobs_evaluated": len(job_matches),
                "profile_summary": {
                    "overall_field": profile_data.get('overall_field'),
                    "total_experience": profile_data.get('total_experience'),
                    "skills_count": len(profile_data.get('current_skills_selected', []) + 
                                      profile_data.get('current_skills_custom', [])),
                    "education_count": len(profile_data.get('education_entries', [])),
                    "experience_count": len(profile_data.get('work_experience_entries', []))
                },
                "evaluation_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "evaluation_method": "balanced_realistic_danish_market_scoring"
            })
            
            # Apply balanced validation instead of ultra-strict
            self.apply_balanced_validation(evaluation_results, profile_data)
            
            # Store evaluation results
            self.store_evaluation_results(user_session_id, evaluation_results)
            
            return evaluation_results
            
        except Exception as e:
            logging.error(f"Error during AI evaluation: {e}")
            return {"error": f"Evaluation failed: {str(e)}"}

    def apply_balanced_validation(self, evaluation_results: Dict, profile_data: Dict):
        """Apply balanced validation that's realistic but not crushing"""
        total_experience = profile_data.get('total_experience', 'None')
        education_entries = profile_data.get('education_entries', [])
        
        # Determine if candidate is still a student
        is_student = any(
            edu.get('graduation_year', '') and 
            int(edu.get('graduation_year', '0')) > datetime.now().year
            for edu in education_entries
            if edu.get('graduation_year', '').isdigit()
        )
        
        # Check for strong academic background
        has_strong_education = any(
            edu.get('field_of_study', '').lower() in ['computer science', 'data science', 'business', 'engineering', 'economics']
            or 'business' in edu.get('field_of_study', '').lower()
            or 'data' in edu.get('field_of_study', '').lower()
            for edu in education_entries
        )
        
        # Apply balanced scoring adjustments
        for evaluation in evaluation_results.get('evaluations', []):
            job_title = evaluation.get('job_title', '').lower()
            current_score = evaluation.get('match_score', 0)
            
            # Only apply validation if score is unreasonably low or high
            if is_student:
                # Senior roles - reasonable but honest scoring
                if any(word in job_title for word in ['senior', 'lead', 'principal', 'manager', 'director', 'head']):
                    if current_score > 45:  # Cap very optimistic scores
                        new_score = min(current_score, 35)
                        evaluation['match_score'] = new_score
                        evaluation['score_adjustment'] = "Realistic: Senior role requires more experience"
                    elif current_score < 15:  # Ensure minimum reasonable score if they have relevant education
                        if has_strong_education:
                            evaluation['match_score'] = max(current_score, 20)
                            evaluation['score_adjustment'] = "Balanced: Strong education provides foundation"
                
                # Experience requirements in job title/description
                elif any(phrase in job_title for phrase in ['3+', '5+', 'experienced', 'flere års']):
                    if current_score > 60:
                        evaluation['match_score'] = min(current_score, 50)
                        evaluation['score_adjustment'] = "Realistic: Experience gap exists"
                    elif current_score < 25 and has_strong_education:
                        evaluation['match_score'] = max(current_score, 35)
                        evaluation['score_adjustment'] = "Balanced: Education + potential considered"
                
                # Entry level roles - should score well
                elif any(word in job_title for word in ['junior', 'graduate', 'trainee', 'entry', 'studiejob']):
                    if current_score < 55:  # Ensure reasonable minimum for entry roles
                        evaluation['match_score'] = max(current_score, 60)
                        evaluation['score_adjustment'] = "Corrected: Good fit for entry level"
                    elif current_score > 90:  # Cap perfect scores
                        evaluation['match_score'] = min(current_score, 85)
                
                # Regular roles - balanced approach
                else:
                    if current_score < 30 and has_strong_education:
                        evaluation['match_score'] = max(current_score, 40)
                        evaluation['score_adjustment'] = "Balanced: Strong academic foundation"
                    elif current_score > 75:
                        evaluation['match_score'] = min(current_score, 65)
                        evaluation['score_adjustment'] = "Realistic: Some experience gap"
        
        # Recalculate average after balanced adjustments
        adjusted_scores = [eval.get('match_score', 0) for eval in evaluation_results.get('evaluations', [])]
        if adjusted_scores:
            evaluation_results['summary']['average_match_score'] = round(sum(adjusted_scores) / len(adjusted_scores), 1)
            
        logging.info(f"Balanced validation completed. Student: {is_student}, Strong education: {has_strong_education}")

    def parse_enhanced_evaluation_response(self, response: str, jobs: List[Dict]) -> Dict:
        """Parse AI evaluation response with enhanced fields including reality check"""
        results = {
            "evaluations": [],
            "summary": {
                "average_match_score": 0,
                "score_distribution": {},
                "top_recommendations": [],
                "critical_gaps": [],
                "best_matches": []
            }
        }
        
        lines = response.split('\n')
        current_job = None
        current_eval = {}
        match_scores = []
        all_critical_gaps = []
        all_recommendations = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('JOB_'):
                # Save previous evaluation
                if current_eval and current_job is not None:
                    if current_job < len(jobs):
                        current_eval.update({
                            "job_title": jobs[current_job].get('title', ''),
                            "company": jobs[current_job].get('company', ''),
                            "location": jobs[current_job].get('location', ''),
                            "job_url": jobs[current_job].get('job_url', ''),
                            "job_id": jobs[current_job].get('id', ''),
                            "company_industry": jobs[current_job].get('company_industry', '')
                        })
                    results["evaluations"].append(current_eval)
                
                # Start new evaluation
                current_job = int(line.split('_')[1].rstrip(':')) - 1
                current_eval = {"job_number": current_job + 1}
                
            elif line.startswith('MATCH_SCORE:') and current_eval is not None:
                score_text = line.replace('MATCH_SCORE:', '').strip()
                try:
                    # Extract numeric score, handle various formats
                    import re
                    score_match = re.search(r'(\d+)', score_text)
                    if score_match:
                        score = int(score_match.group(1))
                        # Ensure score is within valid range
                        score = max(0, min(100, score))
                        current_eval['match_score'] = score
                        match_scores.append(score)
                    else:
                        # Fallback if no number found
                        current_eval['match_score'] = 25  # Conservative fallback
                        match_scores.append(25)
                        logging.warning(f"Could not parse score from: {score_text}")
                except Exception as e:
                    current_eval['match_score'] = 25  # Safe fallback
                    match_scores.append(25)
                    logging.error(f"Error parsing match score: {e}")
            
            elif line.startswith('OVERALL_FIT:') and current_eval is not None:
                current_eval['overall_fit'] = line.replace('OVERALL_FIT:', '').strip()
            
            elif line.startswith('SENIORITY_MATCH:') and current_eval is not None:
                current_eval['seniority_match'] = line.replace('SENIORITY_MATCH:', '').strip()
            
            elif line.startswith('EXPERIENCE_GAP:') and current_eval is not None:
                current_eval['experience_gap'] = line.replace('EXPERIENCE_GAP:', '').strip()
            
            elif line.startswith('REALITY_CHECK:') and current_eval is not None:
                current_eval['reality_check'] = line.replace('REALITY_CHECK:', '').strip()
            
            elif line.startswith('STRENGTHS:') and current_eval is not None:
                current_eval['strengths'] = line.replace('STRENGTHS:', '').strip()
            
            elif line.startswith('CRITICAL_GAPS:') and current_eval is not None:
                gaps = line.replace('CRITICAL_GAPS:', '').strip()
                current_eval['critical_gaps'] = gaps
                if gaps and gaps.lower() not in ['none', 'none identified', 'n/a']:
                    all_critical_gaps.append(gaps)
            
            elif line.startswith('MINOR_GAPS:') and current_eval is not None:
                current_eval['minor_gaps'] = line.replace('MINOR_GAPS:', '').strip()
            
            elif line.startswith('RECOMMENDATIONS:') and current_eval is not None:
                recs = line.replace('RECOMMENDATIONS:', '').strip()
                current_eval['recommendations'] = recs
                if recs and recs.lower() not in ['none', 'none provided', 'n/a']:
                    all_recommendations.append(recs)
            
            elif line.startswith('LIKELIHOOD:') and current_eval is not None:
                current_eval['likelihood'] = line.replace('LIKELIHOOD:', '').strip()
        
        # Don't forget the last job
        if current_eval and current_job is not None:
            if current_job < len(jobs):
                current_eval.update({
                    "job_title": jobs[current_job].get('title', ''),
                    "company": jobs[current_job].get('company', ''),
                    "location": jobs[current_job].get('location', ''),
                    "job_url": jobs[current_job].get('job_url', ''),
                    "job_id": jobs[current_job].get('id', ''),
                    "company_industry": jobs[current_job].get('company_industry', '')
                })
            results["evaluations"].append(current_eval)
        
        # Calculate summary statistics
        if match_scores:
            results["summary"]["average_match_score"] = round(sum(match_scores) / len(match_scores), 1)
            
            # Score distribution
            results["summary"]["score_distribution"] = {
                "high (70-100)": len([s for s in match_scores if s >= 70]),
                "medium (40-69)": len([s for s in match_scores if 40 <= s < 70]),
                "low (0-39)": len([s for s in match_scores if s < 40])
            }
            
            # Best matches (top 3)
            best_evals = sorted([e for e in results["evaluations"] if 'match_score' in e], 
                              key=lambda x: x.get('match_score', 0), reverse=True)
            results["summary"]["best_matches"] = best_evals[:3]
        
        # Aggregate recommendations and gaps
        results["summary"]["top_recommendations"] = list(set(all_recommendations))[:5]
        results["summary"]["critical_gaps"] = list(set(all_critical_gaps))[:5]
        
        logging.info(f"Parsed {len(results['evaluations'])} job evaluations with balanced scoring")
        return results

    def validate_and_adjust_scores(self, evaluation_results: Dict, profile_data: Dict):
        """Validate scores are realistic based on profile data"""
        total_experience = profile_data.get('total_experience', 'None')
        education_entries = profile_data.get('education_entries', [])
        
        # Determine if candidate is still a student
        is_student = any(
            edu.get('graduation_year', '') and 
            int(edu.get('graduation_year', '0')) > datetime.now().year
            for edu in education_entries
            if edu.get('graduation_year', '').isdigit()
        )
        
        # Determine experience level
        experience_level = "entry"
        if total_experience in ["None", "0-1 year"]:
            experience_level = "entry"
        elif total_experience in ["1-3 years"]:
            experience_level = "junior"
        elif total_experience in ["3-5 years"]:
            experience_level = "mid"
        elif total_experience in ["5-10 years"]:
            experience_level = "senior"
        else:
            experience_level = "expert"
        
        # Adjust scores if they seem unrealistic
        for evaluation in evaluation_results.get('evaluations', []):
            job_title = evaluation.get('job_title', '').lower()
            current_score = evaluation.get('match_score', 0)
            
            # Check for seniority mismatches
            if is_student and any(word in job_title for word in ['senior', 'lead', 'principal', 'manager', 'director']):
                if current_score > 40:
                    evaluation['match_score'] = min(current_score, 35)
                    evaluation['score_adjustment'] = f"Adjusted down: Student cannot qualify for senior role"
            
            elif experience_level == "entry" and any(word in job_title for word in ['senior', 'lead', 'principal']):
                if current_score > 45:
                    evaluation['match_score'] = min(current_score, 40)
                    evaluation['score_adjustment'] = f"Adjusted down: Entry-level cannot qualify for senior role"
            
            elif experience_level == "junior" and any(word in job_title for word in ['senior', 'lead', 'principal']):
                if current_score > 55:
                    evaluation['match_score'] = min(current_score, 50)
                    evaluation['score_adjustment'] = f"Adjusted down: Junior level insufficient for senior role"
        
        # Recalculate average after adjustments
        adjusted_scores = [eval.get('match_score', 0) for eval in evaluation_results.get('evaluations', [])]
        if adjusted_scores:
            evaluation_results['summary']['average_match_score'] = round(sum(adjusted_scores) / len(adjusted_scores), 1)
            
        logging.info(f"Score validation completed. Experience level: {experience_level}, Student: {is_student}")

    def store_evaluation_results(self, user_session_id: str, results: Dict):
        """Store evaluation results in database"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Create evaluation results table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cv_job_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_session_id TEXT,
            evaluation_data TEXT,
            evaluation_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            jobs_evaluated INTEGER,
            average_match_score REAL
        )
        """)
        
        try:
            cursor.execute("""
            INSERT INTO cv_job_evaluations 
            (user_session_id, evaluation_data, jobs_evaluated, average_match_score)
            VALUES (?, ?, ?, ?)
            """, (
                user_session_id,
                json.dumps(results),
                results.get('jobs_evaluated', 0),
                results.get('summary', {}).get('average_match_score', 0)
            ))
            
            conn.commit()
            logging.info(f"Stored evaluation results for user {user_session_id}")
            
        except Exception as e:
            logging.error(f"Error storing evaluation results: {e}")
        finally:
            conn.close()
    
    def get_latest_evaluation(self, user_session_id: str) -> Optional[Dict]:
        """Get the latest evaluation results for a user"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            SELECT evaluation_data FROM cv_job_evaluations 
            WHERE user_session_id = ? 
            ORDER BY evaluation_timestamp DESC LIMIT 1
            """, (user_session_id,))
            
            result = cursor.fetchone()
            if result:
                return json.loads(result[0])
            return None
            
        except Exception as e:
            logging.error(f"Error getting latest evaluation: {e}")
            return None
        finally:
            conn.close()
    
    def generate_improvement_plan(self, user_session_id: str) -> Dict:
        """Generate a personalized improvement plan based on evaluations"""
        evaluation_results = self.get_latest_evaluation(user_session_id)
        if not evaluation_results:
            return {"error": "No evaluation results found"}
        
        profile_data = self.get_user_profile_data(user_session_id)
        if not profile_data:
            return {"error": "No profile data found"}
        
        # Create improvement plan prompt
        improvement_prompt = f"""Based on the CV-job evaluation results, create a personalized career improvement plan.

EVALUATION SUMMARY:
Average Match Score: {evaluation_results.get('summary', {}).get('average_match_score', 0)}%
Jobs Evaluated: {evaluation_results.get('jobs_evaluated', 0)}

COMMON GAPS IDENTIFIED:
{', '.join(evaluation_results.get('summary', {}).get('common_gaps', []))}

TOP RECOMMENDATIONS:
{', '.join(evaluation_results.get('summary', {}).get('top_recommendations', []))}

CURRENT PROFILE:
Field: {profile_data.get('overall_field', '')}
Experience: {profile_data.get('total_experience', '')}
Skills: {', '.join(profile_data.get('current_skills_selected', [])[:10])}

CREATE IMPROVEMENT PLAN:
Provide a structured 6-month improvement plan in this format:

IMMEDIATE ACTIONS (0-2 months):
1. [Specific action with timeline]
2. [Specific action with timeline]
3. [Specific action with timeline]

MEDIUM TERM (2-4 months):
1. [Specific action with timeline]
2. [Specific action with timeline]
3. [Specific action with timeline]

LONG TERM (4-6 months):
1. [Specific action with timeline]
2. [Specific action with timeline]

SKILL PRIORITIES:
1. [Most important skill to develop] - [Why and how]
2. [Second priority] - [Why and how]
3. [Third priority] - [Why and how]

CERTIFICATION RECOMMENDATIONS:
- [Specific certification] - [Cost/time estimate]
- [Specific certification] - [Cost/time estimate]

NETWORKING SUGGESTIONS:
- [Specific networking action]
- [Specific networking action]

Be specific and actionable. Include timeframes and resources where possible."""

        try:
            response = self.llm.invoke(improvement_prompt)
            
            return {
                "user_session_id": user_session_id,
                "improvement_plan": response,
                "generated_timestamp": datetime.now().isoformat(),
                "based_on_evaluation": evaluation_results.get('evaluation_timestamp')
            }
            
        except Exception as e:
            logging.error(f"Error generating improvement plan: {e}")
            return {"error": f"Failed to generate improvement plan: {str(e)}"}


# Convenience functions
def evaluate_user_cv_matches(user_session_id: str, max_jobs: int = 10) -> Dict:
    """Convenience function to evaluate CV-job matches"""
    evaluator = CVJobEvaluator()
    return evaluator.evaluate_cv_job_matches(user_session_id, max_jobs)

def get_user_latest_evaluation(user_session_id: str) -> Optional[Dict]:
    """Convenience function to get latest evaluation"""
    evaluator = CVJobEvaluator()
    return evaluator.get_latest_evaluation(user_session_id)

def generate_user_improvement_plan(user_session_id: str) -> Dict:
    """Convenience function to generate improvement plan"""
    evaluator = CVJobEvaluator()
    return evaluator.generate_improvement_plan(user_session_id)

def main():
    """Main function for testing"""
    logging.info("CV Job Evaluator - Test Mode")
    
    # Test with a sample user
    test_user_id = "test_user_123"
    
    try:
        evaluator = CVJobEvaluator()
        results = evaluator.evaluate_cv_job_matches(test_user_id, max_jobs=5)
        
        if "error" in results:
            logging.error(f"Evaluation failed: {results['error']}")
        else:
            logging.info(f"Evaluation completed for {results.get('jobs_evaluated', 0)} jobs")
            logging.info(f"Average match score: {results.get('summary', {}).get('average_match_score', 0)}%")
            
            # Generate improvement plan
            plan = evaluator.generate_improvement_plan(test_user_id)
            if "error" not in plan:
                logging.info("Improvement plan generated successfully")
            
    except Exception as e:
        logging.error(f"Test failed: {e}")

if __name__ == "__main__":
    main()
