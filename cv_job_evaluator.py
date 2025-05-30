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
        
        # Initialize LLM
        try:
            self.llm = Together(
                model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
                api_key=self.api_key,
                temperature=0.2,  # Lower temperature for more consistent evaluations
                max_tokens=2048,  # More tokens for detailed analysis
                top_p=0.9,
                repetition_penalty=1.1
            )
            
            # Test LLM connection
            test_response = self.llm.invoke("Test connection. Reply with: OK")
            logging.info(f"CV Job Evaluator LLM initialized successfully")
            
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
        
        # Create comprehensive evaluation prompt
        evaluation_prompt = f"""You are a professional career counselor and recruiter. Analyze how well this candidate's profile matches each job posting.

{profile_text}

JOBS TO EVALUATE:
{jobs_text}

EVALUATION TASK:
For each job, provide a detailed evaluation in the exact format below. Do not include any other text.

RESPONSE FORMAT:
For each job, respond with exactly this structure:

JOB_1:
MATCH_SCORE: [0-100]
OVERALL_FIT: [Excellent/Good/Fair/Poor]
STRENGTHS: [3-5 specific strengths the candidate has for this role]
GAPS: [3-5 specific skills/qualifications the candidate lacks]
RECOMMENDATIONS: [3-4 specific actions to improve candidacy]
LIKELIHOOD: [High/Medium/Low - likelihood of getting an interview]

JOB_2:
MATCH_SCORE: [0-100]
OVERALL_FIT: [Excellent/Good/Fair/Poor]
STRENGTHS: [3-5 specific strengths]
GAPS: [3-5 specific gaps]
RECOMMENDATIONS: [3-4 specific recommendations]
LIKELIHOOD: [High/Medium/Low]

Continue for all jobs...

EVALUATION CRITERIA:
- MATCH_SCORE: 0-100 based on skills, experience, education alignment
- STRENGTHS: What candidate brings that matches job requirements
- GAPS: Missing skills, experience, or qualifications
- RECOMMENDATIONS: Specific courses, certifications, or experience to gain
- LIKELIHOOD: Realistic assessment of interview chances

Be honest and constructive. Focus on actionable feedback.

START EVALUATION:"""

        try:
            # Get AI evaluation
            response = self.llm.invoke(evaluation_prompt)
            logging.info(f"Received evaluation response: {len(response)} characters")
            
            # Parse the response
            evaluation_results = self.parse_evaluation_response(response, job_matches)
            
            # Add metadata
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
                }
            })
            
            # Store evaluation results
            self.store_evaluation_results(user_session_id, evaluation_results)
            
            return evaluation_results
            
        except Exception as e:
            logging.error(f"Error during AI evaluation: {e}")
            return {"error": f"Evaluation failed: {str(e)}"}
    
    def parse_evaluation_response(self, response: str, jobs: List[Dict]) -> Dict:
        """Parse AI evaluation response into structured data"""
        results = {
            "evaluations": [],
            "summary": {
                "average_match_score": 0,
                "top_recommendations": [],
                "common_gaps": [],
                "best_matches": []
            }
        }
        
        lines = response.split('\n')
        current_job = None
        current_eval = {}
        match_scores = []
        all_gaps = []
        all_recommendations = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('JOB_'):
                # Save previous evaluation
                if current_eval and current_job is not None:
                    # Add job details to evaluation
                    if current_job < len(jobs):
                        current_eval.update({
                            "job_title": jobs[current_job].get('title', ''),
                            "company": jobs[current_job].get('company', ''),
                            "location": jobs[current_job].get('location', ''),
                            "job_url": jobs[current_job].get('job_url', ''),
                            "job_id": jobs[current_job].get('id', '')
                        })
                    results["evaluations"].append(current_eval)
                
                # Start new evaluation
                current_job = int(line.split('_')[1].rstrip(':')) - 1
                current_eval = {"job_number": current_job + 1}
                
            elif line.startswith('MATCH_SCORE:') and current_eval is not None:
                try:
                    score = int(line.replace('MATCH_SCORE:', '').strip())
                    current_eval['match_score'] = score
                    match_scores.append(score)
                except ValueError:
                    current_eval['match_score'] = 0
                    
            elif line.startswith('OVERALL_FIT:') and current_eval is not None:
                current_eval['overall_fit'] = line.replace('OVERALL_FIT:', '').strip()
                
            elif line.startswith('STRENGTHS:') and current_eval is not None:
                current_eval['strengths'] = line.replace('STRENGTHS:', '').strip()
                
            elif line.startswith('GAPS:') and current_eval is not None:
                gaps = line.replace('GAPS:', '').strip()
                current_eval['gaps'] = gaps
                if gaps:
                    all_gaps.extend([gap.strip() for gap in gaps.split(',')])
                    
            elif line.startswith('RECOMMENDATIONS:') and current_eval is not None:
                recommendations = line.replace('RECOMMENDATIONS:', '').strip()
                current_eval['recommendations'] = recommendations
                if recommendations:
                    all_recommendations.extend([rec.strip() for rec in recommendations.split(',')])
                    
            elif line.startswith('LIKELIHOOD:') and current_eval is not None:
                current_eval['likelihood'] = line.replace('LIKELIHOOD:', '').strip()
        
        # Don't forget the last evaluation
        if current_eval and current_job is not None:
            if current_job < len(jobs):
                current_eval.update({
                    "job_title": jobs[current_job].get('title', ''),
                    "company": jobs[current_job].get('company', ''),
                    "location": jobs[current_job].get('location', ''),
                    "job_url": jobs[current_job].get('job_url', ''),
                    "job_id": jobs[current_job].get('id', '')
                })
            results["evaluations"].append(current_eval)
        
        # Calculate summary statistics
        if match_scores:
            results["summary"]["average_match_score"] = round(sum(match_scores) / len(match_scores), 1)
            
            # Find best matches (top 3)
            sorted_evals = sorted(results["evaluations"], 
                                key=lambda x: x.get('match_score', 0), reverse=True)
            results["summary"]["best_matches"] = [
                {
                    "job_title": eval.get('job_title', ''),
                    "company": eval.get('company', ''),
                    "match_score": eval.get('match_score', 0),
                    "overall_fit": eval.get('overall_fit', '')
                }
                for eval in sorted_evals[:3]
            ]
        
        # Identify common gaps and recommendations
        from collections import Counter
        if all_gaps:
            gap_counts = Counter(all_gaps)
            results["summary"]["common_gaps"] = [gap for gap, count in gap_counts.most_common(5)]
        
        if all_recommendations:
            rec_counts = Counter(all_recommendations)
            results["summary"]["top_recommendations"] = [rec for rec, count in rec_counts.most_common(5)]
        
        logging.info(f"Parsed {len(results['evaluations'])} job evaluations")
        return results
    
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
