import re
import json
import logging
from typing import Dict, List, Optional, Union, Tuple
from pathlib import Path
import uuid
from datetime import datetime
import warnings
import os

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
            raise ValueError("Together AI API key not provided. Set TOGETHER_API_KEY environment variable or pass api_key parameter.")
        
        self.client = Together(api_key=api_key)
        
        # Define JSON schema for CV extraction
        self.cv_schema = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Full name of the person"
                },
                "email": {
                    "type": "string",
                    "description": "Email address"
                },
                "phone": {
                    "type": "string",
                    "description": "Phone number (preferably Danish format)"
                },
                "linkedin": {
                    "type": "string",
                    "description": "LinkedIn profile URL or username"
                },
                "github": {
                    "type": "string",
                    "description": "GitHub profile URL or username"
                },
                "website": {
                    "type": "string",
                    "description": "Personal website or portfolio URL"
                },
                "personal_summary": {
                    "type": "string",
                    "description": "A brief professional summary/description of the person based on their background, experience and skills (2-3 sentences in Danish)"
                },
                "education_entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "degree": {"type": "string", "description": "Degree type (e.g., Bachelor, Master, PhD, Datamatiker)"},
                            "field_of_study": {"type": "string", "description": "Field of study or major"},
                            "institution": {"type": "string", "description": "Educational institution name"},
                            "graduation_year": {"type": "string", "description": "Year of graduation"},
                            "id": {"type": "string", "description": "Unique identifier"},
                            "marked_for_removal": {"type": "boolean", "description": "Always false for new entries"}
                        },
                        "required": ["degree", "field_of_study", "institution", "graduation_year"]
                    }
                },
                "experience_entries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "job_title": {"type": "string", "description": "Job title or position"},
                            "company": {"type": "string", "description": "Company or organization name"},
                            "years_in_role": {"type": "string", "description": "Number of years in this role (as string)"},
                            "skills_responsibilities": {"type": "string", "description": "Key skills and responsibilities (comma-separated)"},
                            "id": {"type": "string", "description": "Unique identifier"},
                            "marked_for_removal": {"type": "boolean", "description": "Always false for new entries"}
                        },
                        "required": ["job_title", "company", "years_in_role"]
                    }
                },
                "skills": {
                    "type": "object",
                    "properties": {
                        "technical": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Technical skills (programming languages, tools, technologies)"
                        },
                        "soft": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Soft skills (leadership, communication, etc.)"
                        },
                        "all": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "All skills combined"
                        }
                    }
                },
                "languages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Spoken languages"
                },
                "suggested_job_title_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of 3-5 relevant job title search keywords that would help find similar positions (e.g., 'software developer', 'python engineer', 'backend developer')",
                    "maxItems": 5
                },
                "suggested_overall_field": {
                    "type": "string",
                    "description": "Suggested primary field based on background (e.g., 'Software Development', 'Data Science & AI', 'Project Management')"
                },
                "suggested_roles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Suggested target roles based on experience"
                },
                "total_experience_years": {
                    "type": "integer",
                    "description": "Total years of professional experience"
                }
            },
            "required": ["name", "education_entries", "experience_entries", "skills", "languages", "personal_summary", "suggested_job_title_keywords"]
        }
        
        # Check library availability on initialization
        self._check_dependencies()

    def _check_dependencies(self):
        """Check and report on available dependencies"""
        status = {
            'PDF Support': PDF_AVAILABLE,
            'DOCX Support': DOCX_AVAILABLE,
            'Together AI': TOGETHER_AVAILABLE
        }
        
        missing = [name for name, available in status.items() if not available]
        if missing:
            logger.info(f"Missing optional dependencies: {', '.join(missing)}")

    def get_supported_formats(self) -> List[str]:
        """Return list of currently supported formats based on available libraries"""
        formats = ['.txt']  # Always supported
        if PDF_AVAILABLE:
            formats.append('.pdf')
        if DOCX_AVAILABLE:
            formats.append('.docx')
        return formats

    def extract_from_file(self, file_path: Union[str, Path]) -> Dict:
        """
        Main extraction method that handles different file formats
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        supported_formats = self.get_supported_formats()
        if file_path.suffix.lower() not in supported_formats:
            raise ValueError(f"Unsupported file format: {file_path.suffix}. Supported: {supported_formats}")
        
        try:
            # Extract text based on file type
            if file_path.suffix.lower() == '.pdf' and PDF_AVAILABLE:
                text = self._extract_pdf_text(file_path)
            elif file_path.suffix.lower() == '.docx' and DOCX_AVAILABLE:
                text = self._extract_docx_text(file_path)
            elif file_path.suffix.lower() == '.txt':
                text = self._extract_txt_text(file_path)
            else:
                raise ValueError(f"Cannot process {file_path.suffix} - required library not available")
            
            # Parse the extracted text using LLM
            cv_data = self._parse_cv_with_llm(text)
            cv_data['extraction_metadata'] = {
                'file_name': file_path.name,
                'file_size': file_path.stat().st_size,
                'extraction_timestamp': datetime.now().isoformat(),
                'file_format': file_path.suffix.lower(),
                'model_used': self.model,
                'extraction_method': 'llm',
                'dependencies_available': {
                    'pdf': PDF_AVAILABLE,
                    'docx': DOCX_AVAILABLE,
                    'together_ai': TOGETHER_AVAILABLE
                }
            }
            
            return cv_data
            
        except Exception as e:
            logger.error(f"Error extracting CV from {file_path}: {str(e)}")
            return self._create_empty_cv_structure(error=str(e))

    def extract_from_text(self, text: str) -> Dict:
        """
        Extract CV data directly from text string using LLM
        """
        try:
            cv_data = self._parse_cv_with_llm(text)
            cv_data['extraction_metadata'] = {
                'extraction_timestamp': datetime.now().isoformat(),
                'source': 'direct_text',
                'model_used': self.model,
                'extraction_method': 'llm'
            }
            return cv_data
        except Exception as e:
            logger.error(f"Error parsing CV text with LLM: {str(e)}")
            return self._create_empty_cv_structure(error=str(e))

    def _parse_cv_with_llm(self, text: str) -> Dict:
        """
        Parse CV text using LLM and return structured data
        """
        # Create the prompt for CV extraction
        prompt = self._create_extraction_prompt(text)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert CV/resume parser. Extract structured information from CVs and return valid JSON that matches the provided schema. Focus on Danish context when applicable (Danish education system, companies, etc.). Be thorough and accurate."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=4000
            )
            
            # Extract the JSON response
            llm_response = response.choices[0].message.content
            cv_data = self._parse_llm_response(llm_response)
            
            # Add generated IDs and default values
            cv_data = self._post_process_cv_data(cv_data)
            
            return cv_data
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {str(e)}")
            raise

    def _create_extraction_prompt(self, cv_text: str) -> str:
        """Create a detailed prompt for CV extraction"""
        return f"""
Please extract structured information from the following CV/resume text and return it as valid JSON.

**CV Text:**
{cv_text}

**Instructions:**
1. Extract all relevant information according to the schema below
2. For Danish CVs, recognize Danish education terms like "Datamatiker", "Erhvervsakademi", "Gymnasium", etc.
3. For experience, calculate years in role based on dates provided
4. Categorize skills into technical and soft skills
5. Suggest appropriate overall field (choose from: "Data Science & AI", "Software Development", "Project Management", "UX/UI Design", "Marketing & Sales", "Finance & Economics", "Engineering", "Healthcare", "International Business")
6. Suggest target roles based on experience and skills
7. Create a brief professional summary (2-3 sentences in English) that describes the person's background, key strengths, and professional profile
8. Generate 3-5 relevant job title search keywords that would help find similar positions (e.g., for a Python developer: ["software developer", "python engineer", "backend developer", "web developer"])
9. If information is missing, use empty strings or empty arrays as appropriate
10. Ensure all required fields are present

**JSON Schema to follow:**
{json.dumps(self.cv_schema, indent=2)}

**Return only valid JSON, no additional text or explanations.**
"""

    def _parse_llm_response(self, response: str) -> Dict:
        """Parse the LLM response and extract JSON"""
        try:
            # Try to find JSON in the response
            response = response.strip()
            
            # Remove any markdown code blocks
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            # Parse JSON
            cv_data = json.loads(response)
            return cv_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.error(f"Response was: {response}")
            raise ValueError(f"LLM returned invalid JSON: {e}")

    def _post_process_cv_data(self, cv_data: Dict) -> Dict:
        """Post-process the CV data to add required fields and fix structure"""
        # Ensure basic structure exists
        cv_data = {**self._create_empty_cv_structure(), **cv_data}
        
        # Add unique IDs to education entries
        for edu in cv_data.get('education_entries', []):
            if 'id' not in edu:
                edu['id'] = str(uuid.uuid4())
            if 'marked_for_removal' not in edu:
                edu['marked_for_removal'] = False
        
        # Add unique IDs to experience entries
        for exp in cv_data.get('experience_entries', []):
            if 'id' not in exp:
                exp['id'] = str(uuid.uuid4())
            if 'marked_for_removal' not in exp:
                exp['marked_for_removal'] = False
            # Ensure skills_responsibilities is a string
            if 'skills_responsibilities' not in exp:
                exp['skills_responsibilities'] = ''
            
            # Handle years_in_role - ensure it's a string representation of a whole number
            years_value = exp.get('years_in_role', '0')
            try:
                # Convert to float first to handle decimal strings, then to int, then back to string
                years_float = float(str(years_value))
                years_int = int(round(years_float))  # Round to nearest integer
                exp['years_in_role'] = str(years_int)
            except (ValueError, TypeError):
                exp['years_in_role'] = '0'
        
        # Ensure skills structure is correct
        if 'skills' not in cv_data:
            cv_data['skills'] = {'technical': [], 'soft': [], 'all': []}
        else:
            skills = cv_data['skills']
            if 'technical' not in skills:
                skills['technical'] = []
            if 'soft' not in skills:
                skills['soft'] = []
            if 'all' not in skills:
                skills['all'] = skills.get('technical', []) + skills.get('soft', [])
        
        # Mark extraction as successful
        cv_data['extraction_success'] = True
        
        return cv_data

    def _create_empty_cv_structure(self, error: str = None) -> Dict:
        """Create empty CV structure matching Streamlit app format"""
        return {
            'name': '',
            'email': '',
            'phone': '',
            'linkedin': '',
            'github': '',
            'website': '',
            'personal_summary': '',
            'education_entries': [],
            'experience_entries': [],
            'skills': {
                'technical': [],
                'soft': [],
                'all': []
            },
            'languages': [],
            'suggested_job_title_keywords': [],
            'total_experience_years': 0,
            'suggested_overall_field': '',
            'suggested_roles': [],
            'extraction_success': error is None,
            'extraction_error': error,
            'raw_text_preview': ''
        }

    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF file using multiple strategies with better error handling"""
        if not PDF_AVAILABLE:
            raise ImportError("PDF parsing libraries not available. Install with: pip install PyPDF2 pdfplumber")
        
        text = ""
        
        # Try pdfplumber first (better for complex layouts)
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    except Exception as e:
                        logger.warning(f"Error extracting page {page_num} with pdfplumber: {e}")
        except Exception as e:
            logger.warning(f"pdfplumber failed completely: {e}")
        
        # Fallback to PyPDF2 if pdfplumber fails or returns empty
        if not text.strip():
            try:
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page_num, page in enumerate(pdf_reader.pages):
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                        except Exception as e:
                            logger.warning(f"Error extracting page {page_num} with PyPDF2: {e}")
            except Exception as e:
                logger.warning(f"PyPDF2 failed: {e}")
        
        if not text.strip():
            raise ValueError("Could not extract any text from PDF file")
        
        return text

    def _extract_docx_text(self, file_path: Path) -> str:
        """Extract text from DOCX file"""
        if not DOCX_AVAILABLE:
            raise ImportError("DOCX parsing library not available. Install python-docx.")
        
        doc = Document(file_path)
        text = ""
        
        # Extract text from paragraphs
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        
        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text += cell.text + " "
                text += "\n"
        
        return text

    def _extract_txt_text(self, file_path: Path) -> str:
        """Extract text from TXT file"""
        encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    return file.read()
            except UnicodeDecodeError:
                continue
        
        raise ValueError("Could not decode text file with any supported encoding")

    def suggest_profile_fields(self, cv_data: Dict) -> Dict:
        """
        Suggest values for Streamlit app fields based on extracted CV data
        """
        suggestions = {}
        
        # Use LLM-suggested overall field
        suggestions['overall_field'] = cv_data.get('suggested_overall_field', 'International Business')
        
        # Use LLM-suggested roles
        suggestions['target_roles'] = cv_data.get('suggested_roles', [])
        
        # Calculate total experience from LLM data
        total_years = cv_data.get('total_experience_years', 0)
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
        elif total_years <= 15:
            suggestions['total_experience'] = '10-15 years'
        else:
            suggestions['total_experience'] = '15+ years'
        
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
