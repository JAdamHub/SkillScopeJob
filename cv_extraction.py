import warnings
import logging
import os
import json
import re
import uuid
from typing import Dict, List, Optional, Union, Tuple
from pathlib import Path
from datetime import datetime

# Suppress warnings for dependency conflicts and PDF warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", module="pdfminer")

# Document parsing libraries with better error handling
PDF_AVAILABLE = False
DOCX_AVAILABLE = False
TOGETHER_AVAILABLE = False

try:
    import PyPDF2
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError as e:
    print(f"INFO: PDF libraries not available: {e}")
    print("To install: pip install PyPDF2 pdfplumber")

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError as e:
    print(f"INFO: DOCX library not available: {e}")
    print("To install: pip install python-docx")

try:
    from together import Together
    TOGETHER_AVAILABLE = True
except ImportError as e:
    print(f"INFO: Together AI not available: {e}")
    print("To install: pip install together")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMCVExtractor:
    """
    LLM-based CV extraction class that uses Together AI to parse CVs
    and extract structured data using advanced language models.
    """
    
    def __init__(self, api_key: str = None, model: str = "meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo"):
        """
        Initialize the LLM CV extractor
        
        Args:
            api_key: Together AI API key (if not provided, will try to get from environment)
            model: LLM model to use for extraction
        """
        self.supported_formats = ['.pdf', '.docx', '.txt']
        self.model = model
        
        # Initialize Together client
        if not TOGETHER_AVAILABLE:
            raise ImportError("Together AI not available. Install with: pip install together")
        
        api_key = api_key or os.getenv("TOGETHER_API_KEY")
        if not api_key:
            raise ValueError("Together AI API key not provided. Set TOGETHER_API_KEY environment variable or pass api_key parameter.")
        
        self.client = Together(api_key=api_key)
        
        # Define JSON schema for CV extraction
        self.cv_schema = {
            "name": "Full name of the person",
            "email": "Email address", 
            "phone": "Phone number",
            "linkedin": "LinkedIn profile URL",
            "personal_summary": "Brief professional summary",
            "languages": ["List of languages"],
            "skills": {"technical": [], "soft": [], "all": []},
            "education_entries": [],
            "experience_entries": [],
            "suggested_job_title_keywords": [],
            "extraction_success": True,
            "extraction_error": None
        }

    def _check_dependencies(self):
        """Check if required dependencies are available"""
        issues = []
        if not PDF_AVAILABLE:
            issues.append("PDF libraries not available")
        if not DOCX_AVAILABLE:
            issues.append("DOCX library not available")
        if not TOGETHER_AVAILABLE:
            issues.append("Together AI not available")
        return issues

    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats"""
        return self.supported_formats

    def extract_from_file(self, file_path: Union[str, Path]) -> Dict:
        """Extract CV data from a file"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            return self._create_empty_cv_structure(f"File not found: {file_path}")
        
        if file_path.suffix.lower() not in self.supported_formats:
            return self._create_empty_cv_structure(f"Unsupported file format: {file_path.suffix}")
        
        try:
            # Extract text based on file type
            if file_path.suffix.lower() == '.pdf':
                text = self._extract_pdf_text(file_path)
            elif file_path.suffix.lower() == '.docx':
                text = self._extract_docx_text(file_path)
            elif file_path.suffix.lower() == '.txt':
                text = self._extract_txt_text(file_path)
            else:
                return self._create_empty_cv_structure(f"Unsupported file format: {file_path.suffix}")
            
            if not text or len(text.strip()) < 50:
                return self._create_empty_cv_structure("Could not extract readable text from file")
            
            # Process with LLM
            return self.extract_from_text(text)
            
        except Exception as e:
            logger.error(f"Error extracting from file: {e}")
            return self._create_empty_cv_structure(f"File extraction error: {str(e)}")

    def extract_from_text(self, text: str) -> Dict:
        """Extract CV data from text using LLM"""
        if not text or len(text.strip()) < 50:
            return self._create_empty_cv_structure("Text too short for analysis")
        
        try:
            cv_data = self._parse_cv_with_llm(text)
            return self._post_process_cv_data(cv_data)
            
        except Exception as e:
            logger.error(f"Error extracting from text: {e}")
            return self._create_empty_cv_structure(f"Text extraction error: {str(e)}")

    def _parse_cv_with_llm(self, text: str) -> Dict:
        """Parse CV text using LLM"""
        prompt = self._create_extraction_prompt(text)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4000
            )
            
            response_text = response.choices[0].message.content
            logger.info(f"LLM response received: {len(response_text)} characters")
            
            return self._parse_llm_response(response_text)
            
        except Exception as e:
            logger.error(f"LLM parsing error: {e}")
            raise e

    def _create_extraction_prompt(self, cv_text: str) -> str:
        """Create a comprehensive extraction prompt for the LLM"""
        return f"""Extract structured information from this CV/resume. You must respond with ONLY valid JSON, no other text.

CV TEXT:
{cv_text[:3000]}

LANGUAGE EXTRACTION GUIDELINES:
- Look for explicit language mentions (Danish, English, German, etc.)
- Check for phrases like "fluent in", "native speaker", "speaks", "languages", "sprog"
- Look for Danish indicators: "dansk", "danish", "danske"
- Look for English indicators: "engelsk", "english", "fluent english"
- Include both native languages and learned languages
- For Danish CVs, assume Danish proficiency unless stated otherwise
- Look in education section for international programs (often indicate English)
- Check for language courses, certifications, or study abroad programs
- Look for work experience in international companies (may indicate language skills)

EXPERIENCE EXTRACTION:
- Look for job titles, company names, duration (years/months)
- Extract years in role - convert to approximate years (e.g., "2 years 3 months" -> "2.25")
- Extract key skills and responsibilities
- ALWAYS create experience entries if you find any work history

EDUCATION EXTRACTION:
- Look for degree names, field of study, institution names
- Extract graduation years if mentioned
- ALWAYS create education entries if you find any education history

JOB KEYWORD EXTRACTION:
- Generate relevant job search keywords based on experience and skills
- Include variations of job titles mentioned
- Consider Danish job market terms

Respond with ONLY this JSON structure (no extra text, no code blocks, no explanations):

{{
    "name": "Full name of the person or empty string",
    "email": "Email address or empty string",
    "phone": "Phone number or empty string", 
    "linkedin": "LinkedIn profile URL or empty string",
    "personal_summary": "Brief professional summary (2-3 sentences) or empty string",
    "languages": ["List of languages the person speaks"],
    "skills": {{
        "technical": ["List of technical skills"],
        "soft": ["List of soft skills"],
        "all": ["All skills combined"]
    }},
    "education_entries": [
        {{
            "degree": "Degree name",
            "field_of_study": "Field of study",
            "institution": "Institution name",
            "graduation_year": "Year or empty string",
            "id": "unique_id"
        }}
    ],
    "experience_entries": [
        {{
            "job_title": "Job title",
            "company": "Company name",
            "years_in_role": "Number of years as string",
            "skills_responsibilities": "Key responsibilities",
            "id": "unique_id"
        }}
    ],
    "suggested_job_title_keywords": ["List of job search keywords based on experience"],
    "extraction_success": true,
    "extraction_error": null,
    "raw_text_preview": "{cv_text[:200]}..."
}}

IMPORTANT: 
- Return ONLY valid JSON
- No explanations, no markdown, no code blocks
- If a field cannot be determined, use empty string or empty array
- For years_in_role, extract duration and convert to approximate years as string
- Generate meaningful job keywords based on actual experience
- ALWAYS include arrays even if empty
- Ensure all JSON is properly escaped"""

    def _parse_llm_response(self, response: str) -> Dict:
        """Parse LLM response and extract JSON"""
        # Try to find JSON in the response
        response = response.strip()
        
        # Remove code blocks if present
        if response.startswith('```'):
            lines = response.split('\n')
            start_idx = 0
            end_idx = len(lines)
            
            for i, line in enumerate(lines):
                if line.startswith('```') and i == 0:
                    start_idx = 1
                elif line.startswith('```') and i > 0:
                    end_idx = i
                    break
            
            response = '\n'.join(lines[start_idx:end_idx])
        
        # Try to extract JSON from the response
        try:
            # First try: direct JSON parsing
            return json.loads(response)
        except json.JSONDecodeError:
            # Second try: find JSON object in text
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            # Third try: clean and parse
            cleaned = re.sub(r'[^\x20-\x7E\n\r\t]', '', response)  # Remove non-ASCII
            cleaned = re.sub(r'\n+', '\n', cleaned)  # Normalize newlines
            
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response content: {response[:500]}...")
                raise ValueError(f"LLM returned invalid JSON: {str(e)}")

    def _post_process_cv_data(self, cv_data: Dict) -> Dict:
        """Post-process and validate extracted CV data"""
        processed_data = cv_data.copy()
        
        # Ensure required fields exist
        if 'extraction_success' not in processed_data:
            processed_data['extraction_success'] = True
        
        # Combine skills if needed
        if 'skills' in processed_data and isinstance(processed_data['skills'], dict):
            technical = processed_data['skills'].get('technical', [])
            soft = processed_data['skills'].get('soft', [])
            all_skills = list(set(technical + soft))
            processed_data['skills']['all'] = all_skills
        
        # Add unique IDs to entries if missing
        for entry in processed_data.get('education_entries', []):
            if 'id' not in entry:
                entry['id'] = str(uuid.uuid4())
            # Ensure marked_for_removal is set
            if 'marked_for_removal' not in entry:
                entry['marked_for_removal'] = False
        
        for entry in processed_data.get('experience_entries', []):
            if 'id' not in entry:
                entry['id'] = str(uuid.uuid4())
            # Ensure marked_for_removal is set
            if 'marked_for_removal' not in entry:
                entry['marked_for_removal'] = False
        
        return processed_data

    def _create_empty_cv_structure(self, error: str = None) -> Dict:
        """Create empty CV structure with error information"""
        return {
            "name": "",
            "email": "",
            "phone": "",
            "linkedin": "",
            "personal_summary": "",
            "languages": [],
            "skills": {"technical": [], "soft": [], "all": []},
            "education_entries": [],
            "experience_entries": [],
            "suggested_job_title_keywords": [],
            "extraction_success": False,
            "extraction_error": error,
            "raw_text_preview": ""
        }

    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        if not PDF_AVAILABLE:
            raise ImportError("PDF libraries not available")
        
        try:
            import PyPDF2
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            # Fallback to pdfplumber
            try:
                import pdfplumber
                text = ""
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                return text
            except Exception as e2:
                logger.error(f"PDF extraction failed with both libraries: {e}, {e2}")
                raise e

    def _extract_docx_text(self, file_path: Path) -> str:
        """Extract text from DOCX file"""
        if not DOCX_AVAILABLE:
            raise ImportError("DOCX library not available")
        
        try:
            from docx import Document
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
            raise e

    def _extract_txt_text(self, file_path: Path) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.read()

    def suggest_profile_fields(self, cv_data: Dict) -> Dict:
        """Suggest profile fields based on extracted CV data"""
        suggestions = {}
        
        # Overall field suggestion based on education and experience
        education_fields = [edu.get('field_of_study', '') for edu in cv_data.get('education_entries', [])]
        job_titles = [exp.get('job_title', '') for exp in cv_data.get('experience_entries', [])]
        
        # Simple field mapping logic
        all_text = ' '.join(education_fields + job_titles).lower()
        
        if any(word in all_text for word in ['computer', 'software', 'programming', 'developer', 'engineer']):
            suggestions['overall_field'] = 'Software Development'
        elif any(word in all_text for word in ['data', 'analysis', 'analytics', 'science']):
            suggestions['overall_field'] = 'Data Science & AI'
        elif any(word in all_text for word in ['business', 'management', 'marketing']):
            suggestions['overall_field'] = 'International Business'
        elif any(word in all_text for word in ['design', 'ux', 'ui']):
            suggestions['overall_field'] = 'UX/UI Design'
        else:
            suggestions['overall_field'] = cv_data.get('education_entries', [{}])[0].get('field_of_study', '') if cv_data.get('education_entries') else ''
        
        # Target roles based on experience
        suggestions['target_roles'] = [exp.get('job_title', '') for exp in cv_data.get('experience_entries', [])][:3]
        
        # Total experience estimation
        total_years = 0
        for exp in cv_data.get('experience_entries', []):
            years_str = exp.get('years_in_role', '0')
            try:
                years = float(years_str)
                total_years += years
            except:
                pass
        
        if total_years == 0:
            suggestions['total_experience'] = 'None'
        elif total_years <= 1:
            suggestions['total_experience'] = '0-1 year'
        elif total_years <= 3:
            suggestions['total_experience'] = '1-3 years'
        elif total_years <= 5:
            suggestions['total_experience'] = '3-5 years'
        elif total_years <= 10:
            suggestions['total_experience'] = '5-10 years'
        else:
            suggestions['total_experience'] = '10+ years'
        
        return suggestions

# Convenience functions for easy import and use
def extract_cv_from_file(file_path: Union[str, Path], api_key: str = None) -> Dict:
    """Convenience function to extract CV data from a file using LLM"""
    extractor = LLMCVExtractor(api_key=api_key)
    return extractor.extract_from_file(file_path)

def extract_cv_from_text(text: str, api_key: str = None) -> Dict:
    """Convenience function to extract CV data from text using LLM"""
    extractor = LLMCVExtractor(api_key=api_key)
    return extractor.extract_from_text(text)

def get_cv_suggestions(cv_data: Dict, api_key: str = None) -> Dict:
    """Convenience function to get profile suggestions"""
    extractor = LLMCVExtractor(api_key=api_key)
    return extractor.suggest_profile_fields(cv_data)

# Legacy compatibility - create an alias for the old class name if needed
CVExtractor = LLMCVExtractor

# Example usage and testing
if __name__ == "__main__":
    print("LLM CV Extractor - Dependency Check")
    print("=" * 40)
    
    # Check for API key
    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        print("❌ TOGETHER_API_KEY environment variable not set")
        print("Please set your Together AI API key:")
        print("export TOGETHER_API_KEY='your-api-key-here'")
        exit(1)
    
    try:
        extractor = LLMCVExtractor(api_key=api_key)
        print(f"Supported formats: {extractor.get_supported_formats()}")
        print(f"PDF Support: {PDF_AVAILABLE}")
        print(f"DOCX Support: {DOCX_AVAILABLE}")
        print(f"Together AI: {TOGETHER_AVAILABLE}")
        
        # Test with sample Danish CV text
        sample_cv_text = """
        Lars Nielsen
        Email: lars.nielsen@example.com
        Phone: +45 12 34 56 78
        LinkedIn: linkedin.com/in/larsnielsen
        
        UDDANNELSE
        Datamatiker, Erhvervsakademi Aarhus, 2020
        STX, Aarhus Gymnasium, 2017
        
        ERFARING
        Software Udvikler
        TechCorp ApS
        2020-2024
        Udvikling af Python applikationer, arbejde med SQL databaser, agile metoder
        
        Praktikant
        StartupXYZ
        2019-2020
        JavaScript, React, Node.js udvikling
        
        FÆRDIGHEDER
        Python, Java, JavaScript, SQL, React, Git, Docker, Scrum, Teamarbejde
        Dansk (modersmål), Engelsk (flydende)
        """
        
        print("\n" + "=" * 40)
        print("Testing with sample Danish CV:")
        print("=" * 40)
        
        result = extractor.extract_from_text(sample_cv_text)
        suggestions = extractor.suggest_profile_fields(result)
        
        print("Extracted CV Data:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("\nProfile Suggestions:")
        print(json.dumps(suggestions, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
