import os
import sqlite3
import re
import json
import logging
import time
from typing import Dict, List, Optional
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
    
    def get_top_job_matches(self, user_session_id: str, limit: int = 10) -> List[Dict]:
        """Get top job matches specifically from the profile matcher results"""
        try:
            # Import here to avoid circular imports
            from profile_job_matcher import get_user_job_matches
            
            # Get matches using the profile matcher - this ensures we get the EXACT same jobs
            # that the profile matcher identified as relevant
            matches = get_user_job_matches(user_session_id, limit=limit * 2)  # Get more to filter
            
            if not matches:
                logging.warning(f"No job matches found for user {user_session_id}")
                return []
            
            # Enhanced filtering for jobs with sufficient information for AI evaluation
            filtered_matches = []
            for job in matches:
                # Ensure job has the minimum required information for meaningful evaluation
                title = job.get('title', '').strip()
                company = job.get('company', '').strip()
                description = job.get('description', '').strip()
                relevance_score = job.get('relevance_score', 0)
                
                # More lenient filtering to ensure we get jobs for evaluation
                if (title and company and description and 
                    len(description) > 50 and  # Reduced from 100 to 50
                    relevance_score > 10):     # Reduced from 20 to 10
                    
                    # Add match type if missing
                    if 'match_type' not in job:
                        job['match_type'] = 'profile_match'
                    
                    filtered_matches.append(job)
            
            # Sort by relevance score to get the best matches for evaluation
            filtered_matches = sorted(filtered_matches, 
                                    key=lambda x: x.get('relevance_score', 0), 
                                    reverse=True)
            
            # Return top matches up to the limit
            result = filtered_matches[:limit]
            
            logging.info(f"Selected {len(result)} high-quality job matches for CV evaluation from {len(matches)} total matches")
            
            # Enhanced logging of which jobs we're evaluating for debugging
            for i, job in enumerate(result):
                logging.info(f"CV Evaluation Job {i+1}: '{job.get('title')}' at '{job.get('company')}' (Score: {job.get('relevance_score', 0)}%) - Description length: {len(job.get('description', ''))}")
            
            return result
            
        except Exception as e:
            logging.error(f"Error getting job matches for CV evaluation: {e}")
            return []

    def get_user_profile_data(self, user_session_id: str) -> Optional[Dict]:
        """Get user profile data from database with enhanced error handling"""
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
                profile_data = json.loads(result[0])
                logging.info(f"Retrieved profile for user {user_session_id}: {profile_data.get('overall_field', 'Unknown field')}")
                return profile_data
            else:
                logging.warning(f"No profile found for user {user_session_id}")
                return None
            
        except Exception as e:
            logging.error(f"Error getting user profile: {e}")
            return None
        finally:
            conn.close()

    def parse_single_job_evaluation(self, section: str, job: Dict, job_index: int) -> Dict:
        """Parse a single job evaluation section with enhanced pattern matching and more robust extraction"""
        eval_data = {
            "job_number": job_index + 1,
            "job_title": job.get('title', ''),
            "company": job.get('company', ''),
            "location": job.get('location', ''),
            "job_url": job.get('job_url', ''),
            "job_id": job.get('id', ''),
            "company_industry": job.get('company_industry', ''),
            "profile_match_score": job.get('relevance_score', 0),
            "match_type": job.get('match_type', 'unknown')
        }
        
        logging.info(f"Parsing evaluation for: {eval_data['job_title']} at {eval_data['company']}")
        logging.info(f"Section content: {section[:200]}...")
        
        # Enhanced field patterns with more variations and formats
        field_patterns = {
            'match_score': [
                r'MATCH[_\s]*SCORE[:\s]*(\d+)',
                r'Score[:\s]*(\d+)',
                r'Match[:\s]*(\d+)',
                r'(\d+)%?\s*match',
                r'(\d+)/100',
                r'(\d+)\s*out\s*of\s*100',
                r'score[:\s]*(\d+)',
                r'rating[:\s]*(\d+)',
                r'(\d+)%',
                # More flexible patterns
                r'(?:match|score|rating)\D*(\d+)',
                r'(\d{1,2})\s*(?:%|percent|out of)',
            ],
            'overall_fit': [
                r'OVERALL[_\s]*FIT[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Overall[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Fit[:\s]*([^\n\r]+?)(?=\n|$)',
                r'OVERALL_FIT[:\s]*([^\n\r]+?)(?=\n|$)',
                r'(?:Overall|Fit)[:\s]*([A-Za-z\s]+?)(?=\n|\.|,|$)',
            ],
            'seniority_match': [
                r'SENIORITY[_\s]*MATCH[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Seniority[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Level[:\s]*([^\n\r]+?)(?=\n|$)',
                r'SENIORITY_MATCH[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Experience\s+level[:\s]*([^\n\r]+?)(?=\n|$)',
            ],
            'experience_gap': [
                r'EXPERIENCE[_\s]*GAP[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Experience[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Gap[:\s]*([^\n\r]+?)(?=\n|$)',
                r'EXPERIENCE_GAP[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Missing\s+experience[:\s]*([^\n\r]+?)(?=\n|$)',
            ],
            'reality_check': [
                r'REALITY[_\s]*CHECK[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Reality[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Assessment[:\s]*([^\n\r]+?)(?=\n|$)',
                r'REALITY_CHECK[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Realistic\s+assessment[:\s]*([^\n\r]+?)(?=\n|$)',
            ],
            'strengths': [
                r'STRENGTHS[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Strength[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Strong[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Positives[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Your\s+strengths[:\s]*([^\n\r]+?)(?=\n|$)',
            ],
            'critical_gaps': [
                r'CRITICAL[_\s]*GAPS[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Critical[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Missing[:\s]*([^\n\r]+?)(?=\n|$)',
                r'CRITICAL_GAPS[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Key\s+missing[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Major\s+gaps[:\s]*([^\n\r]+?)(?=\n|$)',
            ],
            'minor_gaps': [
                r'MINOR[_\s]*GAPS[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Minor[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Small[:\s]*([^\n\r]+?)(?=\n|$)',
                r'MINOR_GAPS[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Areas\s+for\s+improvement[:\s]*([^\n\r]+?)(?=\n|$)',
            ],
            'recommendations': [
                r'RECOMMENDATIONS[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Recommend[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Advice[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Suggestions[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Action\s+items[:\s]*([^\n\r]+?)(?=\n|$)',
            ],
            'likelihood': [
                r'LIKELIHOOD[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Chance[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Probability[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Success[:\s]*([^\n\r]+?)(?=\n|$)',
                r'Interview\s+chance[:\s]*([^\n\r]+?)(?=\n|$)',
            ]
        }
        
        # Extract each field using multiple patterns with better matching
        fields_found = 0
        extraction_details = {}
        
        for field, patterns in field_patterns.items():
            value_found = False
            extracted_value = None
            pattern_used = None
            
            for pattern in patterns:
                try:
                    matches = re.findall(pattern, section, re.IGNORECASE | re.DOTALL)
                    if matches:
                        # Take the first match
                        match_value = matches[0].strip()
                        
                        if field == 'match_score':
                            # Extract numeric score
                            numbers = re.findall(r'\d+', match_value)
                            if numbers:
                                score = int(numbers[0])
                                if 0 <= score <= 100:  # Valid score range
                                    eval_data[field] = score
                                    extracted_value = score
                                    pattern_used = pattern
                                    logging.info(f"Found match score: {score} using pattern: {pattern}")
                                    fields_found += 1
                                    value_found = True
                                    break
                        else:
                            # For text fields, clean up the match
                            if match_value and len(match_value.strip()) > 2:
                                clean_value = match_value.strip()[:300]  # Limit length
                                eval_data[field] = clean_value
                                extracted_value = clean_value[:50] + "..." if len(clean_value) > 50 else clean_value
                                pattern_used = pattern
                                logging.info(f"Found {field}: {extracted_value}")
                                fields_found += 1
                                value_found = True
                                break
                except Exception as e:
                    logging.warning(f"Pattern matching error for {field} with pattern {pattern}: {e}")
                    continue
            
            # Store extraction details for debugging
            extraction_details[field] = {
                'found': value_found,
                'value': extracted_value,
                'pattern': pattern_used
            }
            
            # Provide intelligent defaults if not found
            if not value_found:
                if field == 'match_score':
                    # Use profile match score as fallback with reasonable adjustment
                    base_score = job.get('relevance_score', 40)
                    adjusted_score = max(25, min(85, base_score + 5))
                    eval_data[field] = adjusted_score
                    logging.warning(f"No AI match score found, using adjusted profile score: {adjusted_score}")
                else:
                    # Provide more helpful default messages
                    default_messages = {
                        'overall_fit': 'Good potential match based on profile scoring',
                        'seniority_match': 'Experience level compatibility needs manual review',
                        'experience_gap': 'Detailed experience analysis not available in AI response',
                        'reality_check': f'Based on profile matching ({job.get("relevance_score", 40)}% compatibility), this position shows potential. Manual review recommended for detailed assessment.',
                        'strengths': 'Your profile shows alignment with key job requirements based on initial matching',
                        'critical_gaps': 'Specific skill gaps require detailed job posting review - AI analysis was not accessible',
                        'minor_gaps': 'Consider reviewing job requirements for additional qualifications',
                        'recommendations': 'Review job posting carefully and tailor application to highlight relevant experience',
                        'likelihood': 'Medium - depends on detailed skill alignment and application quality'
                    }
                    eval_data[field] = default_messages.get(field, 'Analysis not available in AI response')
        
        # Log extraction summary
        logging.info(f"Successfully extracted {fields_found} fields for {eval_data['job_title']}")
        logging.info(f"Extraction details: {extraction_details}")
        
        # Validation: if we found very few fields, log more details
        if fields_found < 4:
            logging.warning(f"Only found {fields_found} fields - possible AI response formatting issue")
            logging.warning(f"Section being parsed: {section}")
        
        # Add flag if this seems to be a parsing issue
        if fields_found < 3:
            eval_data['parsing_warning'] = True
            eval_data['fields_extracted'] = fields_found
        
        return eval_data

    def evaluate_cv_job_matches(self, user_session_id: str, max_jobs: int = 10) -> Dict:
        """
        Evaluate how well user's CV matches the SPECIFIC jobs found by profile matcher
        """
        logging.info(f"Starting CV-job evaluation for user {user_session_id}")
        
        # Get user profile
        profile_data = self.get_user_profile_data(user_session_id)
        if not profile_data:
            return {"error": "User profile not found. Please ensure you've saved your profile first."}
        
        # Get the SPECIFIC job matches that the profile matcher identified
        job_matches = self.get_top_job_matches(user_session_id, max_jobs)
        if not job_matches:
            return {
                "error": "No suitable job matches found for evaluation. Please run job search first to find relevant positions.",
                "user_session_id": user_session_id,
                "profile_field": profile_data.get('overall_field', 'Unknown')
            }
        
        logging.info(f"Evaluating {len(job_matches)} specifically matched jobs against user profile")
        logging.info(f"User profile field: {profile_data.get('overall_field', 'Unknown')}")
        
        # Enhanced logging of which jobs we're evaluating
        for i, job in enumerate(job_matches):
            logging.info(f"Evaluating Job {i+1}: '{job.get('title')}' at '{job.get('company')}' (Relevance: {job.get('relevance_score', 0)}%)")
        
        # Format data for AI with enhanced context
        profile_text = self.format_profile_for_evaluation(profile_data)
        jobs_text = self.format_jobs_for_evaluation(job_matches)
        
        # Create IMPROVED evaluation prompt with clearer formatting instructions
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
            
            # Parse the response with improved error handling
            evaluation_results = self.parse_simplified_evaluation_response(response, job_matches)
            
            # Check if parsing was successful
            parsed_evaluations = evaluation_results.get('evaluations', [])
            if not parsed_evaluations:
                logging.error("No evaluations were successfully parsed from AI response")
                # Try alternative parsing or create fallback
                return self.create_fallback_evaluation(user_session_id, job_matches, profile_data, "AI response parsing failed completely")
            
            # Check for parsing warnings
            parsing_issues = sum(1 for eval in parsed_evaluations if eval.get('parsing_warning', False))
            if parsing_issues > 0:
                logging.warning(f"{parsing_issues} evaluations had parsing issues")
            
            # Add enhanced metadata
            evaluation_results.update({
                "user_session_id": user_session_id,
                "evaluation_timestamp": datetime.now().isoformat(),
                "jobs_evaluated": len(job_matches),
                "evaluation_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "profile_field": profile_data.get('overall_field', 'Unknown'),
                "user_experience_level": profile_data.get('total_experience', 'Unknown'),
                "evaluation_type": "profile_matched_jobs",
                "average_job_relevance": round(sum(job.get('relevance_score', 0) for job in job_matches) / len(job_matches), 1) if job_matches else 0,
                "parsing_success_rate": round((len(parsed_evaluations) - parsing_issues) / len(parsed_evaluations) * 100, 1) if parsed_evaluations else 0
            })
            
            # Apply validation and store results
            self.apply_balanced_validation(evaluation_results, profile_data)
            self.store_evaluation_results(user_session_id, evaluation_results)
            
            logging.info(f"CV evaluation completed successfully for {len(job_matches)} jobs")
            logging.info(f"Parsing success rate: {evaluation_results['parsing_success_rate']}%")
            
            return evaluation_results
            
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Error during AI evaluation: {error_msg}")
            
            # Enhanced error handling with specific error types
            if "503" in error_msg or "502" in error_msg:
                return {
                    "error": "AI service temporarily unavailable. Please try again in a few moments.",
                    "error_type": "service_unavailable",
                    "user_session_id": user_session_id,
                    "jobs_available": len(job_matches),
                    "retry_suggestion": "The evaluation can be retried - your job matches are saved."
                }
            elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
                return {
                    "error": "API rate limit reached. Please wait a few minutes before trying again.",
                    "error_type": "rate_limit",
                    "user_session_id": user_session_id,
                    "jobs_available": len(job_matches)
                }
            else:
                # Fallback evaluation for other errors
                return self.create_fallback_evaluation(user_session_id, job_matches, profile_data, error_msg)

    def parse_simplified_evaluation_response(self, response: str, jobs: List[Dict]) -> Dict:
        """Parse AI evaluation response with enhanced robustness and debugging"""
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
        
        logging.info(f"Parsing AI response: {len(response)} characters")
        logging.info(f"Expected to parse {len(jobs)} job evaluations")
        
        # Log the first 500 characters for debugging
        logging.info(f"Response preview: {response[:500]}...")
        
        # More robust job section detection with multiple strategies
        job_sections = []
        
        # Strategy 1: Look for JOB_X: patterns
        import re
        job_pattern = r'(JOB_\d+:.*?)(?=JOB_\d+:|$)'
        matches = re.findall(job_pattern, response, re.DOTALL | re.IGNORECASE)
        
        if matches:
            job_sections = matches
            logging.info(f"Strategy 1: Found {len(job_sections)} job sections using regex pattern")
        else:
            # Strategy 2: Split by lines containing JOB
            lines = response.split('\n')
            current_section = []
            section_found = False
            
            for line in lines:
                line = line.strip()
                # Look for job section markers (more flexible)
                if (line.startswith('JOB_') or 
                    line.startswith('Job ') or 
                    line.startswith('**JOB') or
                    ('JOB' in line.upper() and any(c.isdigit() for c in line))):
                    
                    if current_section and section_found:
                        job_sections.append('\n'.join(current_section))
                    current_section = [line]
                    section_found = True
                elif current_section and section_found:
                    current_section.append(line)
            
            # Add the last section
            if current_section and section_found:
                job_sections.append('\n'.join(current_section))
            
            logging.info(f"Strategy 2: Found {len(job_sections)} job sections using line parsing")
        
        # Strategy 3: If still no sections, try alternative patterns
        if not job_sections:
            logging.warning("No structured job sections found, attempting alternative parsing")
            # Try to split by numbers or other patterns
            alt_pattern = r'(?:JOB[_\s]*\d+|Job\s+\d+|^\d+\.)'
            parts = re.split(alt_pattern, response, flags=re.IGNORECASE | re.MULTILINE)
            if len(parts) > 1:
                job_sections = [part.strip() for part in parts[1:] if part.strip()]  # Skip first empty part
                logging.info(f"Strategy 3: Alternative parsing found {len(job_sections)} sections")
        
        # If we still have no sections, create a fallback section for each job
        if not job_sections and jobs:
            logging.warning("Creating fallback sections - AI response may not be properly formatted")
            # Try to parse the entire response as one block and extract information
            job_sections = [response] * len(jobs)  # Use same response for all jobs as fallback
        
        logging.info(f"Final: {len(job_sections)} job sections will be processed")
        
        # Parse each job section
        match_scores = []
        for i, section in enumerate(job_sections):
            if i >= len(jobs):
                logging.warning(f"More job sections ({len(job_sections)}) than jobs ({len(jobs)})")
                break
                
            logging.info(f"Processing section {i+1}: {section[:100]}...")
            
            eval_data = self.parse_single_job_evaluation(section, jobs[i], i)
            if eval_data and eval_data.get('match_score', 0) > 0:
                results["evaluations"].append(eval_data)
                match_scores.append(eval_data['match_score'])
                logging.info(f"Successfully parsed evaluation {i+1}: {eval_data.get('job_title')} - Score: {eval_data.get('match_score', 0)}%")
            else:
                logging.warning(f"Failed to parse evaluation {i+1} or got invalid score")
                # Add a fallback evaluation
                fallback_eval = self.create_fallback_single_evaluation(jobs[i], i)
                results["evaluations"].append(fallback_eval)
                match_scores.append(fallback_eval['match_score'])
                logging.info(f"Created fallback evaluation {i+1}: Score: {fallback_eval['match_score']}%")
        
        logging.info(f"Successfully processed {len(results['evaluations'])} evaluations with scores: {match_scores}")
        
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
            
            logging.info(f"Summary calculated: Avg={results['summary']['average_match_score']}%, Distribution={results['summary']['score_distribution']}")
        else:
            logging.error("No valid match scores found in any evaluation - this is a critical parsing failure")
            results["summary"]["average_match_score"] = 0
            results["summary"]["score_distribution"] = {"high (70-100)": 0, "medium (40-69)": 0, "low (0-39)": 0}
        
        return results

    def create_fallback_single_evaluation(self, job: Dict, job_index: int) -> Dict:
        """Create a fallback evaluation when parsing fails"""
        # Use the profile matching score as base
        base_score = job.get('relevance_score', 40)
        # Add some variance to make it more realistic
        adjusted_score = max(25, min(75, base_score + 5))
        
        return {
            "job_number": job_index + 1,
            "job_title": job.get('title', 'Unknown'),
            "company": job.get('company', 'Unknown'),
            "location": job.get('location', 'Unknown'),
            "job_url": job.get('job_url', ''),
            "job_id": job.get('id', ''),
            "company_industry": job.get('company_industry', 'Unknown'),
            "match_score": adjusted_score,
            "profile_match_score": job.get('relevance_score', 0),
            "match_type": job.get('match_type', 'unknown'),
            "overall_fit": "Fair" if adjusted_score >= 50 else "Needs Review",
            "seniority_match": "Parsing failed - using fallback analysis",
            "experience_gap": "Detailed analysis unavailable due to parsing issues",
            "reality_check": f"Basic compatibility assessment: {adjusted_score}% match based on profile scoring. Full AI analysis was not accessible.",
            "strengths": "Profile matching suggests this position aligns with your background",
            "critical_gaps": "Unable to identify specific gaps - manual review recommended",
            "minor_gaps": "Consider reviewing job requirements carefully",
            "recommendations": "Review job posting manually and consider applying if requirements align with your skills",
            "likelihood": "Medium" if adjusted_score >= 50 else "Low",
            "parsing_fallback": True
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

    def apply_balanced_validation(self, evaluation_results: Dict, profile_data: Dict):
        """Apply validation to ensure reasonable scores and feedback"""
        evaluations = evaluation_results.get('evaluations', [])
        
        for evaluation in evaluations:
            # Ensure match scores are reasonable
            match_score = evaluation.get('match_score', 50)
            if match_score > 95:
                evaluation['match_score'] = 95
                evaluation['validation_note'] = 'Score capped at 95% for realism'
            elif match_score < 10:
                evaluation['match_score'] = 15
                evaluation['validation_note'] = 'Score raised to minimum 15%'
            
            # Ensure likelihood matches score
            likelihood = evaluation.get('likelihood', 'Medium')
            if match_score >= 75 and likelihood == 'Low':
                evaluation['likelihood'] = 'Medium'
            elif match_score >= 85 and likelihood in ['Low', 'Medium']:
                evaluation['likelihood'] = 'High'
            elif match_score < 40 and likelihood == 'High':
                evaluation['likelihood'] = 'Low'

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

    def create_fallback_evaluation(self, user_session_id: str, job_matches: List[Dict], profile_data: Dict, error_msg: str) -> Dict:
        """Create a fallback evaluation when AI analysis fails"""
        fallback_evaluations = []
        
        for i, job in enumerate(job_matches):
            # Use profile matching score as basis
            base_score = job.get('relevance_score', 40)
            adjusted_score = max(25, min(85, base_score + 5))
            
            fallback_eval = {
                "job_number": i + 1,
                "job_title": job.get('title', 'Unknown'),
                "company": job.get('company', 'Unknown'),
                "location": job.get('location', 'Unknown'),
                "job_url": job.get('job_url', ''),
                "job_id": job.get('id', ''),
                "company_industry": job.get('company_industry', 'Unknown'),
                "match_score": adjusted_score,
                "profile_match_score": job.get('relevance_score', 0),
                "match_type": job.get('match_type', 'unknown'),
                "overall_fit": "Good" if adjusted_score >= 60 else ("Fair" if adjusted_score >= 40 else "Needs Review"),
                "seniority_match": "AI analysis unavailable - review job requirements manually",
                "experience_gap": "Detailed gap analysis unavailable due to technical issues",
                "reality_check": f"Based on profile matching ({job.get('relevance_score', 40)}% compatibility), this position shows potential. Full AI analysis was not available due to: {error_msg}",
                "strengths": "Profile matching suggests alignment with key requirements",
                "critical_gaps": "Unable to identify specific gaps - manual review recommended",
                "minor_gaps": "Consider reviewing job requirements for additional qualifications",
                "recommendations": "Review job posting carefully and consider applying if requirements align with your skills",
                "likelihood": "Medium" if adjusted_score >= 50 else "Low",
                "fallback_mode": True,
                "fallback_reason": error_msg
            }
            fallback_evaluations.append(fallback_eval)
        
        # Calculate summary
        scores = [e['match_score'] for e in fallback_evaluations]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        
        return {
            "user_session_id": user_session_id,
            "evaluation_timestamp": datetime.now().isoformat(),
            "jobs_evaluated": len(job_matches),
            "evaluation_model": "fallback_mode",
            "fallback_mode": True,
            "fallback_reason": error_msg,
            "evaluations": fallback_evaluations,
            "summary": {
                "average_match_score": avg_score,
                "score_distribution": {
                    "high (70-100)": len([s for s in scores if s >= 70]),
                    "medium (40-69)": len([s for s in scores if 40 <= s < 70]),
                    "low (0-39)": len([s for s in scores if s < 40])
                },
                "best_matches": sorted(fallback_evaluations, key=lambda x: x['match_score'], reverse=True)[:3]
            }
        }

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
            
            # Create improvement plan prompt
            improvement_prompt = f"""
You are a senior career coach creating a personalized 6-month improvement plan. Based on the CV evaluation results, create a detailed development roadmap.

USER PROFILE:
- Field: {profile_data.get('overall_field', 'Unknown')}
- Experience: {profile_data.get('total_experience', 'Unknown')}
- Current Skills: {', '.join(profile_data.get('current_skills_selected', []))}
- Target Roles: {', '.join(profile_data.get('target_roles_industries_selected', []))}

EVALUATION SUMMARY:
- Average Match Score: {avg_score}%
- Jobs Analyzed: {len(evaluations)}
- Common Strengths: {' | '.join(common_strengths[:3])}
- Common Gaps: {' | '.join(common_gaps[:3])}

Create a structured improvement plan with these sections:

CURRENT STATUS:
[Brief assessment of where they stand]

IMMEDIATE ACTIONS (0-2 months):
[3-4 specific actions they can take right away]

MEDIUM TERM (2-4 months):
[2-3 skills/certifications to develop]

LONG TERM (4-6 months):
[Strategic positioning and advanced goals]

SKILL DEVELOPMENT PRIORITIES:
[Top 3 technical/soft skills to focus on]

CERTIFICATION RECOMMENDATIONS:
[Relevant certifications for their field]

APPLICATION STRATEGY:
[How to improve job applications based on gaps found]

NETWORKING SUGGESTIONS:
[Industry-specific networking advice]

Make it actionable, specific, and motivating. Focus on realistic steps they can take.
"""
            
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
