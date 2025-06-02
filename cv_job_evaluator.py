import sqlite3
import logging
import os
import json
import re
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

    def format_jobs_for_evaluation(self, jobs: List[Dict]) -> str:
        """Format job listings for AI evaluation"""
        jobs_text = ""
        
        for i, job in enumerate(jobs):
            job_num = i + 1
            jobs_text += f"""
JOB_{job_num}:
Title: {job.get('title', 'Unknown')}
Company: {job.get('company', 'Unknown')}
Location: {job.get('location', 'Unknown')}
Industry: {job.get('company_industry', 'Unknown')}
Job Type: {job.get('job_type', 'Unknown')}
Description: {job.get('description', 'No description')[:500]}{'...' if len(job.get('description', '')) > 500 else ''}

"""
        
        return jobs_text

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
        job_types = profile_data.get('job_types', [])
        job_keywords = profile_data.get('job_title_keywords', [])
        
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
Desired Job Types: {', '.join(job_types) if job_types else 'Not specified'}
Job Search Keywords: {', '.join(job_keywords) if job_keywords else 'Not specified'}

SKILLS: {', '.join(skills) if skills else 'None listed'}

EDUCATION:
{chr(10).join(education_text) if education_text else 'None listed'}

WORK EXPERIENCE:
{chr(10).join(experience_text) if experience_text else 'None listed'}

PERSONAL DESCRIPTION: {profile_data.get('personal_description', 'Not provided')}

NOTE: Jobs found using enhanced search terms that may include modifiers like "student", "graduate", etc. based on job type preferences."""
        return profile_summary

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
        
        # Create evaluation prompt
        evaluation_prompt = f"""You are a Danish recruiter. Evaluate how well this candidate matches each job. Follow the EXACT format below.

{profile_text}

JOBS TO EVALUATE:
{jobs_text}

RESPONSE FORMAT - Follow this EXACTLY for each job:

JOB_1:
MATCH_SCORE: 65
OVERALL_FIT: Good
SENIORITY_MATCH: Slight Stretch
EXPERIENCE_GAP: 1 year short
REALITY_CHECK: Competitive candidate with strong education, worth applying
STRENGTHS: Strong academic background in relevant field, programming skills match requirements
CRITICAL_GAPS: Limited professional experience, no industry-specific certifications
MINOR_GAPS: Could improve communication skills, learn specific frameworks
RECOMMENDATIONS: Apply to this role, highlight project experience, consider online courses
LIKELIHOOD: Medium

For each job, evaluate and respond with the exact format above. Start now:"""

        try:
            # Get AI evaluation
            response = self.llm.invoke(evaluation_prompt)
            logging.info(f"Received evaluation response: {len(response)} characters")
            
            # Parse the response
            evaluation_results = self.parse_simplified_evaluation_response(response, job_matches)
            
            # Add metadata
            evaluation_results.update({
                "user_session_id": user_session_id,
                "evaluation_timestamp": datetime.now().isoformat(),
                "jobs_evaluated": len(job_matches),
                "evaluation_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"
            })
            
            # Apply validation and store results
            self.apply_balanced_validation(evaluation_results, profile_data)
            self.store_evaluation_results(user_session_id, evaluation_results)
            
            return evaluation_results
            
        except Exception as e:
            logging.error(f"Error during AI evaluation: {e}")
            return self.create_fallback_evaluation(user_session_id, job_matches, profile_data, str(e))

    def parse_simplified_evaluation_response(self, response: str, jobs: List[Dict]) -> Dict:
        """Parse AI evaluation response with robust parsing"""
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
        
        # Split response into job sections
        job_sections = []
        current_section = []
        
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('JOB_'):
                if current_section:
                    job_sections.append('\n'.join(current_section))
                current_section = [line]
            elif current_section:
                current_section.append(line)
        
        if current_section:
            job_sections.append('\n'.join(current_section))
        
        # Parse each job section
        match_scores = []
        for i, section in enumerate(job_sections):
            if i >= len(jobs):
                break
                
            eval_data = self.parse_single_job_evaluation(section, jobs[i], i)
            if eval_data:
                results["evaluations"].append(eval_data)
                if 'match_score' in eval_data:
                    match_scores.append(eval_data['match_score'])
        
        # Calculate summary
        if match_scores:
            results["summary"]["average_match_score"] = round(sum(match_scores) / len(match_scores), 1)
            
            # Score distribution
            results["summary"]["score_distribution"] = {
                "high (70-100)": len([s for s in match_scores if s >= 70]),
                "medium (40-69)": len([s for s in match_scores if 40 <= s < 70]),
                "low (0-39)": len([s for s in match_scores if s < 40])
            }
            
            # Best matches
            best_evals = sorted([e for e in results["evaluations"] if 'match_score' in e], 
                              key=lambda x: x.get('match_score', 0), reverse=True)
            results["summary"]["best_matches"] = best_evals[:3]
        
        return results

    def parse_single_job_evaluation(self, section: str, job: Dict, job_index: int) -> Dict:
        """Parse a single job evaluation section"""
        eval_data = {
            "job_number": job_index + 1,
            "job_title": job.get('title', ''),
            "company": job.get('company', ''),
            "location": job.get('location', ''),
            "job_url": job.get('job_url', ''),
            "job_id": job.get('id', ''),
            "company_industry": job.get('company_industry', '')
        }
        
        # Define field patterns to extract
        field_patterns = {
            'match_score': r'MATCH_SCORE:\s*(\d+)',
            'overall_fit': r'OVERALL_FIT:\s*(.+?)(?:\n|$)',
            'seniority_match': r'SENIORITY_MATCH:\s*(.+?)(?:\n|$)',
            'experience_gap': r'EXPERIENCE_GAP:\s*(.+?)(?:\n|$)',
            'reality_check': r'REALITY_CHECK:\s*(.+?)(?:\n|$)',
            'strengths': r'STRENGTHS:\s*(.+?)(?:\n|$)',
            'critical_gaps': r'CRITICAL_GAPS:\s*(.+?)(?:\n|$)',
            'minor_gaps': r'MINOR_GAPS:\s*(.+?)(?:\n|$)',
            'recommendations': r'RECOMMENDATIONS:\s*(.+?)(?:\n|$)',
            'likelihood': r'LIKELIHOOD:\s*(.+?)(?:\n|$)'
        }
        
        # Extract each field using regex
        for field, pattern in field_patterns.items():
            match = re.search(pattern, section, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                if field == 'match_score':
                    try:
                        score = int(value)
                        eval_data[field] = max(0, min(100, score))
                    except ValueError:
                        eval_data[field] = 40
                else:
                    eval_data[field] = value
            else:
                # Provide defaults
                if field == 'match_score':
                    eval_data[field] = 40
                else:
                    eval_data[field] = 'Not provided'
        
        return eval_data

    def create_fallback_evaluation(self, user_session_id: str, jobs: List[Dict], profile_data: Dict, error: str) -> Dict:
        """Create fallback evaluation results when AI evaluation fails"""
        logging.warning(f"Creating fallback evaluation due to error: {error}")
        
        evaluations = []
        for i, job in enumerate(jobs):
            evaluations.append(self.create_simple_evaluation(job, i))
        
        scores = [eval_data['match_score'] for eval_data in evaluations]
        
        return {
            "evaluations": evaluations,
            "summary": {
                "average_match_score": round(sum(scores) / len(scores), 1) if scores else 0,
                "score_distribution": {
                    "high (70-100)": 0,
                    "medium (40-69)": len(scores),
                    "low (0-39)": 0
                },
                "best_matches": evaluations[:3],
            },
            "user_session_id": user_session_id,
            "evaluation_timestamp": datetime.now().isoformat(),
            "jobs_evaluated": len(jobs),
            "evaluation_error": error,
            "evaluation_status": "fallback_used"
        }

    def apply_balanced_validation(self, evaluation_results: Dict, profile_data: Dict):
        """Apply balanced validation that's realistic but not crushing"""
        # Simple validation - just ensure scores are reasonable
        for evaluation in evaluation_results.get('evaluations', []):
            current_score = evaluation.get('match_score', 0)
            # Keep scores between 20-85 for realism
            evaluation['match_score'] = max(20, min(85, current_score))

    def store_evaluation_results(self, user_session_id: str, results: Dict):
        """Store evaluation results in database"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
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
        
        # Create a simple improvement plan
        improvement_plan = f"""Based on your evaluation results, here's a personalized improvement plan:

CURRENT STATUS:
- Average match score: {evaluation_results.get('summary', {}).get('average_match_score', 0)}%
- Jobs evaluated: {evaluation_results.get('jobs_evaluated', 0)}

IMMEDIATE ACTIONS (0-2 months):
1. Update your CV to highlight relevant skills
2. Apply to jobs with 60%+ match scores first
3. Practice common interview questions

MEDIUM TERM (2-4 months):
1. Develop skills mentioned in job descriptions
2. Network with professionals in your field
3. Consider relevant certifications

LONG TERM (4-6 months):
1. Build portfolio projects
2. Gain additional experience through projects
3. Expand your professional network

The system has analyzed your profile and found relevant opportunities. Focus on the highest-scoring matches first."""

        return {
            "user_session_id": user_session_id,
            "improvement_plan": improvement_plan,
            "generated_timestamp": datetime.now().isoformat()
        }

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
