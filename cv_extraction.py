import os
import json
import re
import uuid
import warnings
import logging
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
            raise ImportError("Together AI library not available. Install with: pip install together")
        
        api_key = api_key or os.getenv("TOGETHER_API_KEY")
        if not api_key:
            raise ValueError("Together AI API key required. Set TOGETHER_API_KEY environment variable or provide api_key parameter")
        
        self.client = Together(api_key=api_key)
        
        # Define JSON schema for CV extraction
        self.cv_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "linkedin": {"type": "string"},
                "personal_summary": {"type": "string"},
                "skills": {
                    "type": "object",
                    "properties": {
                        "technical": {"type": "array", "items": {"type": "string"}},
                        "soft": {"type": "array", "items": {"type": "string"}},
                        "all": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "languages": {"type": "array", "items": {"type": "string"}},
                "education_entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "degree": {"type": "string"},
                            "field_of_study": {"type": "string"},
                            "institution": {"type": "string"},
                            "graduation_year": {"type": "string"}
                        }
                    }
                },
                "experience_entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "job_title": {"type": "string"},
                            "company": {"type": "string"},
                            "years_in_role": {"type": "number"},
                            "skills_responsibilities": {"type": "string"}
                        }
                    }
                }
            }
        }

    def _check_dependencies(self):
        """Check which document parsing dependencies are available"""
        return {
            'pdf': PDF_AVAILABLE,
            'docx': DOCX_AVAILABLE,
            'together': TOGETHER_AVAILABLE
        }

    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats based on available dependencies"""
        formats = ['.txt']  # Always supported
        if PDF_AVAILABLE:
            formats.extend(['.pdf'])
        if DOCX_AVAILABLE:
            formats.extend(['.docx'])
        return formats

    def extract_from_file(self, file_path: Union[str, Path]) -> Dict:
        """Extract CV data from a file"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            return self._create_empty_cv_structure(f"File not found: {file_path}")
        
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
                return self._create_empty_cv_structure("No readable text found in file")
            
            # Process with LLM
            return self.extract_from_text(text)
            
        except Exception as e:
            logger.error(f"Error extracting from file {file_path}: {e}")
            return self._create_empty_cv_structure(f"Error reading file: {str(e)}")

    def extract_from_text(self, text: str) -> Dict:
        """Extract CV data from raw text using LLM"""
        if not text or len(text.strip()) < 20:
            return self._create_empty_cv_structure("Text too short or empty")
        
        try:
            # Parse with LLM
            cv_data = self._parse_cv_with_llm(text)
            
            # Post-process and validate
            cv_data = self._post_process_cv_data(cv_data)
            cv_data['extraction_success'] = True
            cv_data['raw_text_preview'] = text[:500] + "..." if len(text) > 500 else text
            
            return cv_data
            
        except Exception as e:
            logger.error(f"Error extracting from text: {e}")
            return self._create_empty_cv_structure(f"LLM extraction failed: {str(e)}")

    def _parse_cv_with_llm(self, text: str) -> Dict:
        """Parse CV text using LLM"""
        prompt = self._create_extraction_prompt(text)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert CV parser. Extract structured data from CVs and return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2048
            )
            
            response_text = response.choices[0].message.content
            return self._parse_llm_response(response_text)
            
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            raise e

    def _create_extraction_prompt(self, cv_text: str) -> str:
        """Create extraction prompt for LLM"""
        return f"""
Parse this CV/resume and extract structured information. Return ONLY valid JSON with this exact structure:

{{
    "name": "full name",
    "email": "email address",
    "phone": "phone number",
    "linkedin": "linkedin profile",
    "personal_summary": "professional summary or objective",
    "skills": {{
        "technical": ["list", "of", "technical", "skills"],
        "soft": ["list", "of", "soft", "skills"],
        "all": ["combined", "list", "of", "all", "skills"]
    }},
    "languages": ["list", "of", "languages"],
    "education_entries": [
        {{
            "degree": "degree name",
            "field_of_study": "field of study",
            "institution": "institution name",
            "graduation_year": "year"
        }}
    ],
    "experience_entries": [
        {{
            "job_title": "job title",
            "company": "company name",
            "years_in_role": 2.5,
            "skills_responsibilities": "key skills and responsibilities"
        }}
    ],
    "suggested_job_title_keywords": ["keyword1", "keyword2", "keyword3"]
}}

CV Text:
{cv_text[:3000]}
"""

    def _parse_llm_response(self, response: str) -> Dict:
        """Parse LLM response into structured data"""
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # If direct JSON parsing fails, try to parse line by line
        return self._create_empty_cv_structure("Could not parse LLM response as JSON")

    def _post_process_cv_data(self, cv_data: Dict) -> Dict:
        """Post-process and validate CV data"""
        # Ensure required fields exist
        defaults = {
            'name': '',
            'email': '',
            'phone': '',
            'linkedin': '',
            'personal_summary': '',
            'skills': {'technical': [], 'soft': [], 'all': []},
            'languages': [],
            'education_entries': [],
            'experience_entries': [],
            'suggested_job_title_keywords': []
        }
        
        for key, default_value in defaults.items():
            if key not in cv_data:
                cv_data[key] = default_value
        
        # Add unique IDs to entries
        for entry in cv_data.get('education_entries', []):
            entry['id'] = str(uuid.uuid4())
            entry['marked_for_removal'] = False
        
        for entry in cv_data.get('experience_entries', []):
            entry['id'] = str(uuid.uuid4())
            entry['marked_for_removal'] = False
        
        return cv_data

    def _create_empty_cv_structure(self, error: str = None) -> Dict:
        """Create empty CV structure with error information"""
        import uuid
        return {
            'extraction_success': False,
            'extraction_error': error,
            'name': '',
            'email': '',
            'phone': '',
            'linkedin': '',
            'personal_summary': '',
            'skills': {'technical': [], 'soft': [], 'all': []},
            'languages': [],
            'education_entries': [],
            'experience_entries': [],
            'suggested_job_title_keywords': []
        }

    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        if not PDF_AVAILABLE:
            raise ImportError("PDF libraries not available")
        
        text = ""
        try:
            # Try pdfplumber first
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception:
            # Fallback to PyPDF2
            try:
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
            except Exception as e:
                raise Exception(f"Could not extract text from PDF: {e}")
        
        return text.strip()

    def _extract_docx_text(self, file_path: Path) -> str:
        """Extract text from DOCX file"""
        if not DOCX_AVAILABLE:
            raise ImportError("DOCX library not available")
        
        try:
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            raise Exception(f"Could not extract text from DOCX: {e}")

    def _extract_txt_text(self, file_path: Path) -> str:
        """Extract text from TXT file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except UnicodeDecodeError:
            # Try different encodings
            for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as file:
                        return file.read().strip()
                except:
                    continue
            raise Exception("Could not decode text file")
        except Exception as e:
            raise Exception(f"Could not read text file: {e}")

    def suggest_profile_fields(self, cv_data: Dict) -> Dict:
        """Generate suggestions for profile fields based on CV data"""
        suggestions = {}
        
        # Suggest overall field based on education and experience
        education_fields = [entry.get('field_of_study', '') for entry in cv_data.get('education_entries', [])]
        job_titles = [entry.get('job_title', '') for entry in cv_data.get('experience_entries', [])]
        
        all_text = ' '.join(education_fields + job_titles).lower()
        
        if any(term in all_text for term in ['software', 'programming', 'developer', 'engineer']):
            suggestions['overall_field'] = 'Software Development'
        elif any(term in all_text for term in ['data', 'analytics', 'science', 'machine learning']):
            suggestions['overall_field'] = 'Data Science & AI'
        elif any(term in all_text for term in ['project', 'management', 'manager']):
            suggestions['overall_field'] = 'Project Management'
        elif any(term in all_text for term in ['design', 'ux', 'ui', 'graphic']):
            suggestions['overall_field'] = 'UX/UI Design'
        else:
            suggestions['overall_field'] = 'Software Development'  # Default
        
        # Suggest target roles based on recent experience
        recent_jobs = cv_data.get('experience_entries', [])[:2]  # Last 2 jobs
        suggestions['target_roles'] = [job.get('job_title', '') for job in recent_jobs if job.get('job_title')]
        
        # Calculate total experience
        total_years = sum(entry.get('years_in_role', 0) for entry in cv_data.get('experience_entries', []))
        if total_years >= 15:
            suggestions['total_experience'] = '15+ years'
        elif total_years >= 10:
            suggestions['total_experience'] = '10-15 years'
        elif total_years >= 5:
            suggestions['total_experience'] = '5-10 years'
        elif total_years >= 3:
            suggestions['total_experience'] = '3-5 years'
        elif total_years >= 1:
            suggestions['total_experience'] = '1-3 years'
        else:
            suggestions['total_experience'] = '0-1 year'
        
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
        print("WARNING: TOGETHER_API_KEY not found in environment")
        print("Set it with: export TOGETHER_API_KEY=your_key_here")
    
    try:
        # Check dependencies
        extractor = LLMCVExtractor(api_key=api_key) if api_key else None
        print("CV extractor initialized successfully")
        
    except Exception as e:
        print(f"Error initializing CV extractor: {e}")