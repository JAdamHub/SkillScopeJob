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
        
        # Create SIMPLIFIED evaluation prompt for better parsing
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

JOB_2:
MATCH_SCORE: 45
OVERALL_FIT: Fair
SENIORITY_MATCH: Underqualified
EXPERIENCE_GAP: 3 years short
REALITY_CHECK: Challenging but education is strong foundation
STRENGTHS: Relevant education, some transferable skills
CRITICAL_GAPS: Significant experience gap, missing key technical skills
MINOR_GAPS: Industry knowledge, professional network
RECOMMENDATIONS: Focus on entry-level positions first, build experience
LIKELIHOOD: Low

SCORING GUIDELINES:
- Score 80-100: Excellent match, should definitely apply
- Score 60-79: Good match, competitive candidate
- Score 40-59: Fair match, worth trying with strong application
- Score 20-39: Poor match, significant gaps exist
- Score 0-19: Very poor match, not suitable

For each job, evaluate and respond with the exact format above. Start now:"""

        try:
            # Get AI evaluation with more specific settings
            response = self.llm.invoke(evaluation_prompt)
            logging.info(f"Received evaluation response: {len(response)} characters")
            
            # Debug: Log first part of response
            logging.info(f"Response preview: {response[:500]}...")
            
            # Parse the response with enhanced parsing
            evaluation_results = self.parse_simplified_evaluation_response(response, job_matches)
            
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
                "evaluation_method": "simplified_structured_evaluation",
                "raw_response_preview": response[:300]  # For debugging
            })
            
            # Apply balanced validation
            self.apply_balanced_validation(evaluation_results, profile_data)
            
            # Store evaluation results
            self.store_evaluation_results(user_session_id, evaluation_results)
            
            return evaluation_results
            
        except Exception as e:
            logging.error(f"Error during AI evaluation: {e}")
            # Create fallback evaluation
            return self.create_fallback_evaluation(user_session_id, job_matches, profile_data, str(e))

    def parse_simplified_evaluation_response(self, response: str, jobs: List[Dict]) -> Dict:
        """Parse AI evaluation response with MUCH more robust parsing"""
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
        
        # Don't forget the last section
        if current_section:
            job_sections.append('\n'.join(current_section))
        
        logging.info(f"Found {len(job_sections)} job sections in response")
        
        # Parse each job section
        match_scores = []
        all_critical_gaps = []
        all_recommendations = []
        
        for i, section in enumerate(job_sections):
            if i >= len(jobs):
                break
                
            eval_data = self.parse_single_job_evaluation(section, jobs[i], i)
            if eval_data:
                results["evaluations"].append(eval_data)
                
                # Collect data for summary
                if 'match_score' in eval_data:
                    match_scores.append(eval_data['match_score'])
                
                if eval_data.get('critical_gaps'):
                    all_critical_gaps.append(eval_data['critical_gaps'])
                
                if eval_data.get('recommendations'):
                    all_recommendations.append(eval_data['recommendations'])
        
        # If we didn't get enough evaluations, create simple ones
        if len(results["evaluations"]) < len(jobs):
            logging.warning(f"Only parsed {len(results['evaluations'])} of {len(jobs)} jobs, creating simple evaluations for missing ones")
            for i in range(len(results["evaluations"]), len(jobs)):
                simple_eval = self.create_simple_evaluation(jobs[i], i)
                results["evaluations"].append(simple_eval)
                match_scores.append(simple_eval['match_score'])
        
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
            
            # High likelihood count
            high_likelihood = len([e for e in results["evaluations"] 
                                 if e.get('likelihood', '').lower() in ['high', 'medium']])
            results["summary"]["high_interview_likelihood"] = high_likelihood
        
        # Aggregate recommendations and gaps
        results["summary"]["top_recommendations"] = list(set(all_recommendations))[:5]
        results["summary"]["critical_gaps"] = list(set(all_critical_gaps))[:5]
        
        logging.info(f"Successfully parsed {len(results['evaluations'])} job evaluations")
        logging.info(f"Average score: {results['summary']['average_match_score']}")
        
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
        
        import re
        
        # Extract each field using regex
        for field, pattern in field_patterns.items():
            match = re.search(pattern, section, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                if field == 'match_score':
                    try:
                        score = int(value)
                        eval_data[field] = max(0, min(100, score))  # Ensure valid range
                    except ValueError:
                        eval_data[field] = 40  # Default score
                        logging.warning(f"Could not parse score: {value}")
                else:
                    eval_data[field] = value
            else:
                # Provide defaults for missing fields
                if field == 'match_score':
                    eval_data[field] = 40  # Default score
                else:
                    eval_data[field] = 'Not provided'
        
        return eval_data

    def create_simple_evaluation(self, job: Dict, job_index: int) -> Dict:
        """Create a simple evaluation when AI parsing fails"""
        return {
            "job_number": job_index + 1,
            "job_title": job.get('title', ''),
            "company": job.get('company', ''),
            "location": job.get('location', ''),
            "job_url": job.get('job_url', ''),
            "job_id": job.get('id', ''),
            "company_industry": job.get('company_industry', ''),
            "match_score": 45,  # Neutral score
            "overall_fit": "Fair",
            "seniority_match": "Needs Assessment",
            "experience_gap": "To be determined",
            "reality_check": "Evaluation incomplete - manual review needed",
            "strengths": "Profile shows potential",
            "critical_gaps": "Detailed analysis needed",
            "minor_gaps": "Various skills could be improved",
            "recommendations": "Review job requirements and apply if interested",
            "likelihood": "Medium",
            "parsing_status": "Generated fallback evaluation"
        }

    def create_fallback_evaluation(self, user_session_id: str, jobs: List[Dict], profile_data: Dict, error: str) -> Dict:
        """Create fallback evaluation results when AI evaluation fails"""
        logging.warning(f"Creating fallback evaluation due to error: {error}")
        
        # Create simple evaluations for all jobs
        evaluations = []
        for i, job in enumerate(jobs):
            eval_data = self.create_simple_evaluation(job, i)
            eval_data["error_note"] = "AI evaluation failed, showing placeholder results"
            evaluations.append(eval_data)
        
        # Calculate basic summary
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
                "top_recommendations": ["Manual review recommended", "Check job requirements carefully"],
                "critical_gaps": ["AI evaluation failed - manual analysis needed"],
                "best_matches": evaluations[:3],
                "high_interview_likelihood": 0
            },
            "user_session_id": user_session_id,
            "evaluation_timestamp": datetime.now().isoformat(),
            "jobs_evaluated": len(jobs),
            "evaluation_error": error,
            "evaluation_status": "fallback_used",
            "profile_summary": {
                "overall_field": profile_data.get('overall_field'),
                "total_experience": profile_data.get('total_experience'),
                "skills_count": len(profile_data.get('current_skills_selected', []) + 
                                  profile_data.get('current_skills_custom', [])),
                "education_count": len(profile_data.get('education_entries', [])),
                "experience_count": len(profile_data.get('work_experience_entries', []))
            }
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
