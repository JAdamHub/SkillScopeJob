import os
import sys
import uuid
import csv
import json
import logging
import re
import streamlit as st
import streamlit.components.v1 as components
import sqlite3
from datetime import datetime
from typing import List, Dict

# Add the project root to Python path for proper imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Set page config at the top level
if 'page_config_set' not in st.session_state:
    st.set_page_config(
        page_title="🎯 Advanced Career Profile",
        page_icon="🌟",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.session_state.page_config_set = True

# Import LLM-based CV extraction functionality
try:
    from skillscope.core.cv_extraction import LLMCVExtractor
    CV_EXTRACTION_AVAILABLE = True
except ImportError as e:
    CV_EXTRACTION_AVAILABLE = False
    CV_EXTRACTION_ERROR = str(e)

# Import job matching functionality
try:
    from skillscope.core.profile_job_matcher import run_profile_job_search, get_user_job_matches
    JOB_MATCHING_AVAILABLE = True
except ImportError as e:
    JOB_MATCHING_AVAILABLE = False
    JOB_MATCHING_ERROR = str(e)

# Import CV-job evaluation functionality
try:
    from skillscope.core.cv_job_evaluator import CVJobEvaluator
    CV_EVALUATION_AVAILABLE = True
    
    # Create wrapper functions that work with the class
    def evaluate_user_cv_matches(user_session_id: str, max_jobs: int = 10) -> Dict:
        evaluator = CVJobEvaluator()
        return evaluator.evaluate_cv_job_matches(user_session_id, max_jobs)
    
    def get_user_latest_evaluation(user_session_id: str) -> Dict:
        evaluator = CVJobEvaluator()
        return evaluator.get_latest_evaluation(user_session_id)
    
    def generate_user_improvement_plan(user_session_id: str) -> Dict:
        evaluator = CVJobEvaluator()
        return evaluator.generate_improvement_plan(user_session_id)
        
except ImportError as e:
    CV_EVALUATION_AVAILABLE = False
    CV_EVALUATION_ERROR = str(e)

# Import data enrichment functionality
try:
    from skillscope.core.data_enrichment import run_data_enrichment_for_app, get_enrichment_status
    DATA_ENRICHMENT_AVAILABLE = True
except ImportError as e:
    DATA_ENRICHMENT_AVAILABLE = False
    DATA_ENRICHMENT_ERROR = str(e)

# --- Constants for file names ---
ROLES_INDUSTRIES_ONTOLOGY_FILE = "data/ontologies/roles_industries_ontology.csv"
SKILL_ONTOLOGY_FILE = "data/ontologies/skill_ontology.csv"
USER_PROFILE_LOG_FILE = "data/logs/advanced_user_profile_log.csv"

# --- Helper functions to load ontologies (with dummy creation) ---
def load_ontology_data(file_path: str, column_name: str, default_items: list, is_education_ontology: bool = False) -> list | dict:
    """Load data from a CSV ontology file. Creates a dummy file if it doesn't exist.
       For education ontology, return a dict with lists for each column.
    """
    if not os.path.exists(file_path):
        print(f"INFO: Ontology file not found: {file_path}. Creating a dummy file.")
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if is_education_ontology:
                    # Specific headers for education ontology
                    writer.writerow(["degree_name", "field_of_study_name", "institution_name"])
                    for deg, fos, inst in default_items:
                        writer.writerow([deg, fos, inst])
                else:
                    writer.writerow([column_name]) # Header
                    for item in default_items:
                        writer.writerow([item])
        except Exception as e:
            print(f"ERROR: Could not create dummy ontology file {file_path}: {e}")
            if is_education_ontology:
                return { "degree_name": [], "field_of_study_name": [], "institution_name": [] }
            return default_items

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if is_education_ontology:
                education_data = { "degree_name": set(), "field_of_study_name": set(), "institution_name": set() }
                expected_cols = ["degree_name", "field_of_study_name", "institution_name"]
                if not all(col in reader.fieldnames for col in expected_cols):
                    print(f"ERROR: One or more required columns {expected_cols} missing in {file_path}")
                    return {col: [] for col in expected_cols} # Return empty lists
                for row in reader:
                    if row.get("degree_name"): 
                        education_data["degree_name"].add(row["degree_name"])
                    if row.get("field_of_study_name"): 
                        education_data["field_of_study_name"].add(row["field_of_study_name"])
                    if row.get("institution_name"): 
                        education_data["institution_name"].add(row["institution_name"])
                return {k: sorted(list(v)) for k, v in education_data.items()}
            else:
                if column_name not in reader.fieldnames:
                    print(f"ERROR: Column '{column_name}' missing in {file_path}")
                    return default_items 
                items = [row[column_name] for row in reader if row.get(column_name)]
                return sorted(list(set(items)))
    except Exception as e:
        print(f"ERROR: Error loading ontology file {file_path}: {e}")
        if is_education_ontology:
            return { "degree_name": [], "field_of_study_name": [], "institution_name": [] }
        return default_items

# --- Initialize Session State for dynamic lists ---
def initialize_session_state():
    if 'education_entries' not in st.session_state:
        st.session_state.education_entries = []
    if 'experience_entries' not in st.session_state:
        st.session_state.experience_entries = []
    if 'user_id' not in st.session_state:
        st.session_state.user_id = ""
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    # Initialize job search state variables
    if 'job_search_started' not in st.session_state:
        st.session_state.job_search_started = False
    if 'job_search_completed' not in st.session_state:
        st.session_state.job_search_completed = False
    if 'job_search_results' not in st.session_state:
        st.session_state.job_search_results = None

# --- Functions to handle dynamic input fields (education, experience) ---
def add_education_entry_callback():
    st.session_state.education_entries.append({
        "degree": "", "field_of_study": "", "institution": "", "graduation_year": "", "id": str(uuid.uuid4()), "marked_for_removal": False
    })

def add_experience_entry_callback():
    st.session_state.experience_entries.append({
        "job_title": "", "company": "", "years_in_role": "0", "skills_responsibilities": "", "id": str(uuid.uuid4()), "marked_for_removal": False
    })

# --- Function to log user profile ---
def log_user_profile(data: dict):
    log_file_exists = os.path.isfile(USER_PROFILE_LOG_FILE)
    # Updated LOG_HEADERS
    log_headers = [
        "submission_timestamp", "user_session_id", "user_id_input",
        "target_roles_industries_selected", "target_roles_industries_custom",
        "overall_field", "personal_description", "job_title_keywords",
        "current_skills_selected", "current_skills_custom",
        "education_entries", "total_experience", "work_experience_entries", 
        "job_languages", "job_types", "preferred_locations_dk",
        "remote_openness", "analysis_preference"
    ]
    try:
        with open(USER_PROFILE_LOG_FILE, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=log_headers, extrasaction='ignore')
            if not log_file_exists or os.path.getsize(USER_PROFILE_LOG_FILE) == 0:
                writer.writeheader()
            row_to_write = data.copy()
            for key_to_json in ["education_entries", "work_experience_entries", 
                                "target_roles_industries_selected", "target_roles_industries_custom",
                                "current_skills_selected", "current_skills_custom",
                                "job_languages", "job_types", "preferred_locations_dk"]:
                if key_to_json in row_to_write and isinstance(row_to_write[key_to_json], list):
                    row_to_write[key_to_json] = json.dumps(row_to_write[key_to_json])
            writer.writerow(row_to_write)
        return True
    except Exception as e:
        st.error(f"Error logging profile: {e}")
        print(f"ERROR logging profile: {e}")
        return False

# --- Streamlit App UI ---
def run_app():
    # Ensure os is available in function scope
    import os
    
    st.title("🎯 Advanced Career Profile & Goal Setting")
    st.markdown("Define your detailed profile for precise career insights. 🚀")

    initialize_session_state()

    # --- CV Upload Section with LLM ---
    if CV_EXTRACTION_AVAILABLE:
        st.header("🤖 AI-Powered CV Upload & Auto-Fill")
        
        # Determine if expander should be expanded based on extraction status
        cv_extracted = st.session_state.get('cv_suggestions') is not None
        expander_expanded = not cv_extracted  # Open if no CV extracted yet, closed if CV already extracted
        
        with st.expander("📄 Upload your CV for intelligent profile completion", expanded=expander_expanded):
            # API Key configuration
            api_key = os.getenv('TOGETHER_API_KEY')

            # Model selection
            model_options = [
                "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
                "meta-llama/Llama-4-Scout-17B-16E-Instruct",
                "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "mistralai/Mixtral-8x7B-Instruct-v0.1"
            ]
            selected_model = st.selectbox(
                "AI Model 🧠", 
                options=model_options,
                index=0,
                help="Choose AI model for CV analysis. Larger models are more accurate but slower."
            )
            
            st.markdown("### 📤 CV Upload")
            uploaded_file = st.file_uploader(
                "Select your CV file", 
                type=['pdf', 'docx', 'txt'],
                help="Supported formats: PDF, DOCX, TXT"
            )
            
            col1, col2 = st.columns(2)
            extract_button = col1.button(
                "🤖 Extract data with AI", 
                disabled=uploaded_file is None or not api_key.strip()
            )
            clear_button = col2.button("🗑️ Clear all fields")
            
            if extract_button and uploaded_file and api_key.strip():
                with st.spinner("🧠 AI is analyzing your CV... This may take a moment."):
                    try:
                        # Save uploaded file temporarily
                        temp_file_path = f"temp_cv_{st.session_state.session_id}.{uploaded_file.name.split('.')[-1]}"
                        with open(temp_file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # Extract CV data using LLM
                        extractor = LLMCVExtractor(api_key=api_key.strip(), model=selected_model)
                        cv_data = extractor.extract_from_file(temp_file_path)
                        suggestions = extractor.suggest_profile_fields(cv_data)
                        
                        # Clean up temp file
                        os.remove(temp_file_path)
                        
                        if cv_data.get('extraction_success', False):
                            # Auto-populate session state with extracted data
                            if cv_data.get('experience_entries'):
                                st.session_state.experience_entries = cv_data['experience_entries']
                            if cv_data.get('education_entries'):
                                st.session_state.education_entries = cv_data['education_entries']

                            # Store suggestions for form pre-population
                            st.session_state.cv_suggestions = {
                                'overall_field': suggestions.get('overall_field', ''),
                                'target_roles': suggestions.get('target_roles', []),
                                'total_experience': suggestions.get('total_experience', 'None'),
                                'skills': cv_data.get('skills', {}).get('all', []),
                                'job_title_keywords': cv_data.get('suggested_job_title_keywords', []),
                                'contact_info': {
                                    'name': cv_data.get('name', ''),
                                    'email': cv_data.get('email', ''),
                                    'phone': cv_data.get('phone', ''),
                                    'linkedin': cv_data.get('linkedin', ''),
                                },
                                'languages': cv_data.get('languages', []),
                                'personal_summary': cv_data.get('personal_summary', '')
                            }
                            
                            # Show extraction results without nested expanders
                            st.success("✅ AI has successfully analyzed your CV and filled in the fields!")
                            st.info("💡 The CV upload section will now close automatically. You can reopen it if needed.")
                            st.balloons()
                            st.rerun()
                        else:
                            error_msg = cv_data.get('extraction_error', 'Unknown error')
                            st.error(f"❌ AI could not analyze the CV: {error_msg}")
                            
                            # Show debug info in a simple container
                            st.markdown("**🔍 Debug Information:**")
                            st.write("Model used:", selected_model)
                            st.write("Error:", error_msg)
                            if cv_data.get('raw_text_preview'):
                                st.text_area("Extracted text (preview):", cv_data['raw_text_preview'], height=100)
                            
                    except Exception as e:
                        st.error(f"❌ Error during AI processing: {str(e)}")
                        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                        
                        # Show troubleshooting tips
                        st.markdown("**💡 Troubleshooting:**")
                        st.markdown("""
                        **Possible solutions:**
                        - Check that your Together AI API key is correct
                        - Try uploading the file again
                        - Try a different AI model
                        - Verify that the CV contains readable text
                        """)
            
            elif extract_button and not api_key.strip():
                st.warning("⚠️ Please enter your Together AI API key first")
            
            if clear_button:
                # Clear all session state
                st.session_state.education_entries = []
                st.session_state.experience_entries = []
                st.session_state.job_title_keywords = []
                if 'cv_suggestions' in st.session_state:
                    del st.session_state.cv_suggestions
                st.success("🗑️ All fields have been cleared!")
                st.rerun()
        
        # Show a small indicator if CV has been extracted
        if cv_extracted:
            st.success("✅ CV data has been extracted and auto-filled in the form below")
        
        st.markdown("---")
    else:
        st.warning(f"🤖 AI CV extraction not available: {CV_EXTRACTION_ERROR if 'CV_EXTRACTION_ERROR' in globals() else 'Unknown error'}")
        st.info("To enable AI CV extraction: `pip install together`")

    # --- Load ontologies ---
    default_roles = ["Software Engineer", "Data Scientist", "Project Manager", "UX Designer"]
    default_skills = ["Python", "Java", "SQL", "Data Analysis", "Machine Learning"]
    default_overall_fields = ["Data Science & AI", "Software Development", "Project Management", "UX/UI Design", "Marketing & Sales", "Finance & Economics", "Engineering", "Healthcare", "International Business"]
    
    roles_options = load_ontology_data(ROLES_INDUSTRIES_ONTOLOGY_FILE, "name", default_roles)
    skills_options = load_ontology_data(SKILL_ONTOLOGY_FILE, "canonical_skill", default_skills)

    # --- Sidebar for user ID ---
    st.sidebar.header("👤 User Identification (Simulation)")
    user_id_input_val = st.sidebar.text_input("Enter User ID (optional):", value=st.session_state.user_id, key="user_id_widget")
    if user_id_input_val != st.session_state.user_id:
        st.session_state.user_id = user_id_input_val
    user_session_id_for_run = st.session_state.user_id if st.session_state.user_id else st.session_state.session_id
    st.sidebar.info(f"ID: `{user_session_id_for_run}`")

    # --- FORM STARTS HERE ---
    with st.form(key="profile_form"):
        # Auto-populate with CV suggestions if available
        cv_suggestions = st.session_state.get('cv_suggestions', {})
        
        st.header("1. 📊 Overall Profile")
        cols_profil1 = st.columns(2)
        
        # Pre-select overall field from CV if available
        overall_field_default = cv_suggestions.get('overall_field', '')
        overall_field_index = 0
        if overall_field_default and overall_field_default in default_overall_fields:
            overall_field_index = default_overall_fields.index(overall_field_default)
        
        overall_field = cols_profil1[0].selectbox(
            "Primary Field/Industry:", 
            options=default_overall_fields, 
            index=overall_field_index, 
            help="Choose the field that best describes your general profile."
        )
        
        # Pre-populate languages if available from CV
        cv_languages = cv_suggestions.get('languages', [])
        job_languages_options = ["Danish", "English", "German", "Swedish", "Norwegian", "French", "Spanish", "Other"]
        
        # Improved language mapping
        default_job_languages = []
        for lang in cv_languages:
            lang_lower = lang.lower().strip()
            # Direct matches first
            for opt in job_languages_options:
                if lang_lower == opt.lower():
                    default_job_languages.append(opt)
                    break
            else:
                # Partial matches for common variations
                if any(x in lang_lower for x in ['english', 'eng']):
                    if 'English' not in default_job_languages:
                        default_job_languages.append('English')
                elif any(x in lang_lower for x in ['danish', 'dansk']):
                    if 'Danish' not in default_job_languages:
                        default_job_languages.append('Danish')
                elif any(x in lang_lower for x in ['german', 'deutsch', 'tysk']):
                    if 'German' not in default_job_languages:
                        default_job_languages.append('German')
                elif any(x in lang_lower for x in ['spanish', 'español']):
                    if 'Spanish' not in default_job_languages:
                        default_job_languages.append('Spanish')
                elif any(x in lang_lower for x in ['french', 'français']):
                    if 'French' not in default_job_languages:
                        default_job_languages.append('French')
        
        job_languages = cols_profil1[1].multiselect(
            "🌍 Preferred Job Languages:", 
            options=job_languages_options, 
            default=default_job_languages,
            help="Select one or more languages you are comfortable working in."
        )
        
        # Add personal description field
        st.header("2. ✍️ Personal Description")
        personal_description_default = cv_suggestions.get('personal_summary', '')
        personal_description = st.text_area(
            "Describe yourself professionally (2-4 sentences):",
            value=personal_description_default,
            height=120,
            help="Write a brief professional summary about yourself, your strengths, and what you're looking for in your career.",
            placeholder="e.g., Experienced software developer with 5+ years in Python and web development. Passionate about creating user-friendly applications and working in agile teams. Looking for challenging projects where I can contribute to innovative solutions..."
        )

        st.header("3. 🎯 Target Roles and Specific Industries")
        
        # Improved target roles selection from CV
        cv_target_roles = cv_suggestions.get('target_roles', [])
        
        # Find matches in the ontology
        matched_roles = []
        for cv_role in cv_target_roles:
            cv_role_lower = cv_role.lower()
            # Direct match first
            for option in roles_options:
                if cv_role_lower == option.lower():
                    matched_roles.append(option)
                    break
            else:
                # Partial match for similar roles
                for option in roles_options:
                    if any(word in option.lower() for word in cv_role_lower.split() if len(word) > 3):
                        matched_roles.append(option)
                        break
        
        target_roles_selected = st.multiselect(
            "Target Role(s) and/or Industry(ies) (from list):", 
            roles_options,
            default=matched_roles
        )
        
        # Pre-populate custom roles with unmatched CV roles
        unmatched_roles = [role for role in cv_target_roles if role not in matched_roles]
        default_custom_roles = ', '.join(unmatched_roles) if unmatched_roles else ''
        
        target_roles_custom = st.text_area(
            "Other Target Roles/Industries (custom, comma-separated):", 
            value=default_custom_roles,
            height=75
        )

        st.header("4. 🛠️ Current Skills")
        
        # Pre-select skills from CV if available
        cv_skills = cv_suggestions.get('skills', [])
        current_skills_selected = st.multiselect(
            "Your Skills (from list):", 
            skills_options,
            default=[skill for skill in cv_skills if skill in skills_options]
        )
        current_skills_custom = st.text_area("Other Skills (custom, comma-separated):", height=75)

        st.header("5. 🎓 Educational Background")
        
        # Add education button inside form
        edu_cols = st.columns([3, 1])
        with edu_cols[1]:
            add_education = st.form_submit_button("➕ Add Education", help="Add a new education entry")
        
        if not st.session_state.education_entries:
            st.info("No education entries added. Click '➕ Add Education' to get started.")

        for i, edu_entry in enumerate(st.session_state.education_entries):
            with st.container(border=True):
                st.markdown(f"**🎓 Education #{i+1}**")
                edu_cols = st.columns([2,2,2,1,1])
                
                edu_entry["degree"] = edu_cols[0].text_input(
                    "Degree",
                    value=edu_entry.get("degree", ""),
                    key=f"edu_degree_{edu_entry['id']}",
                    placeholder="e.g. Bachelor, Master"
                )
                
                edu_entry["field_of_study"] = edu_cols[1].text_input(
                    "Field of Study",
                    value=edu_entry.get("field_of_study", ""),
                    key=f"edu_field_{edu_entry['id']}",
                    placeholder="e.g. Computer Science, Economics"
                )
                
                edu_entry["institution"] = edu_cols[2].text_input(
                    "Institution",
                    value=edu_entry.get("institution", ""),
                    key=f"edu_institution_{edu_entry['id']}",
                    placeholder="e.g. Aalborg University"
                )
                
                edu_entry["graduation_year"] = edu_cols[3].text_input(
                    "Graduation Year",
                    value=edu_entry.get("graduation_year", ""),
                    key=f"edu_year_{edu_entry['id']}"
                )
                
                edu_entry["marked_for_removal"] = edu_cols[4].checkbox(
                    "🗑️ Remove",
                    key=f"edu_remove_cb_{edu_entry['id']}"
                )

        st.header("6. 💼 Work Experience")
        
        # Add work experience button inside form
        exp_cols = st.columns([3, 1])
        with exp_cols[1]:
            add_experience = st.form_submit_button("➕ Add Work Experience", help="Add a new work experience entry")

        # Pre-select total experience from CV if available
        cv_total_exp = cv_suggestions.get('total_experience', 'None')
        total_exp_options = ["None", "0-1 year", "1-3 years", "3-5 years", "5-10 years", "10-15 years", "15+ years"]
        total_exp_index = 0
        if cv_total_exp in total_exp_options:
            total_exp_index = total_exp_options.index(cv_total_exp)

        total_experience = st.selectbox(
            "Total Professional Experience:", 
            options=total_exp_options, 
            index=total_exp_index,
            key="total_exp_select"
        )

        if not st.session_state.experience_entries:
            st.info("No experience entries added. Click '➕ Add Work Experience' to get started.")
        
        for i, exp_entry in enumerate(st.session_state.experience_entries):
            with st.container(border=True):
                st.markdown(f"**💼 Work Experience #{i+1}**")
                exp_cols_1 = st.columns(2)
                exp_entry["job_title"] = exp_cols_1[0].text_input("Job Title", value=exp_entry.get("job_title", ""), key=f"exp_title_{exp_entry['id']}")
                exp_entry["company"] = exp_cols_1[1].text_input("Company", value=exp_entry.get("company", ""), key=f"exp_company_{exp_entry['id']}")
                exp_cols_2 = st.columns([1,3,1])
                
                # Handle years_in_role with better error handling for fractional years
                years_value = exp_entry.get("years_in_role", "0")
                try:
                    # Convert to float first, then to int to handle decimal values
                    years_int = int(float(str(years_value)))
                except (ValueError, TypeError):
                    years_int = 0
                
                exp_entry["years_in_role"] = str(exp_cols_2[0].number_input(
                    "Years in Role", 
                    min_value=0, 
                    max_value=50, 
                    step=1, 
                    value=years_int, 
                    key=f"exp_years_{exp_entry['id']}"
                ))
                
                exp_entry["skills_responsibilities"] = exp_cols_2[1].text_area("Key Skills/Responsibilities (comma-separated)", value=exp_entry.get("skills_responsibilities", ""), key=f"exp_skills_{exp_entry['id']}", height=75)
                exp_entry["marked_for_removal"] = exp_cols_2[2].checkbox("🗑️ Remove", key=f"exp_remove_cb_{exp_entry['id']}", help="Mark for removal")

        st.header("7. 🔍 Job Title Search Keywords")
        st.markdown("*These keywords will be used to search for relevant job postings*")
        
        # Get AI-suggested keywords
        ai_suggested_keywords = cv_suggestions.get('job_title_keywords', [])
        
        # Initialize session state for keywords if not exists or if we have new CV suggestions
        if 'job_title_keywords' not in st.session_state or (ai_suggested_keywords and not st.session_state.job_title_keywords):
            st.session_state.job_title_keywords = ai_suggested_keywords[:5]  # Max 5 keywords
        
        # Display current keywords and allow editing
        st.markdown("**Current Job Title Search Keywords:**")
        
        # Create columns for keyword management
        keyword_cols = st.columns([3, 1])
        
        with keyword_cols[0]:
            # Allow user to edit keywords as comma-separated text
            keywords_text = st.text_area(
                "Edit your job search keywords (comma-separated, max 5):",
                value=", ".join(st.session_state.job_title_keywords),
                height=100,
                help="Enter job titles that recruiters might use when posting relevant positions. Examples: 'software developer', 'python engineer', 'data analyst'",
                placeholder="software developer, python engineer, backend developer, web developer, full stack developer",
                key="keywords_textarea"
            )
            
            # Add update button to make it clear how to save changes
            update_keywords_btn = st.form_submit_button("🔄 Update Keywords", help="Click to save your keyword changes")
        
        with keyword_cols[1]:
            st.markdown("**AI Suggestions:**")
            if ai_suggested_keywords:
                st.markdown("*From your CV:*")
                # Display suggested keywords as text (no buttons in forms)
                for keyword in ai_suggested_keywords[:5]:
                    st.markdown(f"• `{keyword}`")
                st.info("💡 Copy keywords from above and paste them into the text area, then click 'Update Keywords'")
            else:
                if cv_suggestions:  # If we have CV suggestions but no keywords
                    st.info("No keywords extracted from CV")
                else:
                    st.info("Upload CV for AI suggestions")
        
        # Display current keywords as tags
        if st.session_state.job_title_keywords:
            st.markdown("**Selected Keywords:**")
            keyword_tags = " • ".join([f"`{kw}`" for kw in st.session_state.job_title_keywords])
            st.markdown(keyword_tags)
            
            if len(st.session_state.job_title_keywords) >= 5:
                st.warning("⚠️ Maximum 5 keywords allowed")
        else:
            st.warning("⚠️ Please add at least one job search keyword")

        st.header("8. 🌍 Location & Analysis Preferences")
        location_options_dk = [
            "Danmark", "Hovedstaden", "Midtjylland", "Nordjylland",
            "Sjælland", "Syddanmark",
            
            "Aabenraa kommune", "Aalborg kommune", "Aarhus kommune", "Albertslund kommune", "Allerød kommune",
            "Assens kommune", "Ballerup kommune", "Billund kommune", "Bornholm kommune", "Brøndby kommune",
            "Brønderslev kommune", "Dragør kommune", "Egedal kommune", "Esbjerg kommune", "Fanø kommune",
            "Favrskov kommune", "Faxe kommune", "Fredensborg kommune", "Fredericia kommune", "Frederiksberg kommune",
            "Frederikshavn kommune", "Frederikssund kommune", "Furesø kommune", "Faaborg-Midtfyn kommune", "Gentofte kommune",
            "Gladsaxe kommune", "Glostrup kommune", "Greve kommune", "Gribskov kommune", "Guldborgsund kommune",
            "Haderslev kommune", "Halsnæs kommune", "Hedensted kommune", "Helsingør kommune", "Herlev kommune",
            "Herning kommune", "Hillerød kommune", "Hjørring kommune", "Holbæk kommune", "Holstebro kommune",
            "Horsens kommune", "Hvidovre kommune", "Høje-Taastrup kommune", "Hørsholm kommune", "Ikast-Brande kommune",
            "Ishøj kommune", "Jammerbugt kommune", "Kalundborg kommune", "Kerteminde kommune", "Kolding kommune",
            "Københavns kommune", "København", "Køge kommune", "Langeland kommune", "Lejre kommune", "Lemvig kommune",
            "Lolland kommune", "Lyngby-Taarbæk kommune", "Mariagerfjord kommune", "Middelfart kommune", "Morsø kommune",
            "Næstved kommune", "Norddjurs kommune", "Nordfyns kommune", "Nyborg kommune", "Næstved kommune",
            "Odder kommune", "Odense kommune", "Odsherred kommune", "Randers kommune", "Rebild kommune",
            "Ringkøbing-Skjern kommune", "Ringsted kommune", "Roskilde kommune", "Rudersdal kommune", "Rødovre kommune",
            "Samsø kommune", "Silkeborg kommune", "Skanderborg kommune", "Skive kommune", "Slagelse kommune",
            "Solrød kommune", "Sorø kommune", "Stevns kommune", "Struer kommune", "Svendborg kommune",
            "Syddjurs kommune", "Sønderborg kommune", "Thisted kommune", "Tønder kommune", "Tårnby kommune",
            "Vallensbæk kommune", "Varde kommune", "Vejen kommune", "Vejle kommune", "Vesthimmerlands kommune",
            "Viborg kommune", "Vordingborg kommune", "Ærø kommune", "Aarhus kommune", "Ødsherred kommune"
        ]
        # Updated job type options to align with Indeed's supported types and user expectations
        job_type_options = [
            "Full-time", 
            "Part-time", 
            "Internship", 
            "Temporary", 
            "Permanent",  # Will map to fulltime
            "Student job",  # Will add "student" to search terms
            "New graduate",  # Will add "graduate" to search terms
            "Apprentice"  # Will map to internship with "apprentice" modifier
        ]
        
        job_types = st.multiselect(
            "💼 Desired Job Types:", 
            options=job_type_options, 
            help="Select job types. Note: 'Student job' will add 'student' to your search terms, 'New graduate' adds 'graduate', etc."
        )

        preferred_locations_dk = st.multiselect("🗺️ Preferred Job Locations in Denmark:", options=location_options_dk)
        remote_options = ["Don't care", "Primarily On-site", "Primarily Hybrid", "Primarily Remote"]
        remote_openness = st.selectbox("🏠 Openness to Remote Work:", options=remote_options, key="remote_select")
        # Set analysis preference to comprehensive by default without user selection
        analysis_preference = "Deep Analysis (comprehensive)"

        # Add AI extraction info display if available
        if cv_suggestions.get('contact_info'):
            # Show contact info if available
            st.subheader("📞 Contact Information")
            contact_info = cv_suggestions['contact_info']
            col1, col2 = st.columns(2)
            
            if contact_info.get('name'):
                col1.info(f"**Name:** {contact_info['name']}")
            if contact_info.get('email'):
                col1.info(f"**Email:** {contact_info['email']}")
            if contact_info.get('phone'):
                col2.info(f"**Phone:** {contact_info['phone']}")
            if contact_info.get('linkedin'):
                col2.info(f"**LinkedIn:** {contact_info['linkedin']}")

        st.markdown("&nbsp;")
        submitted = st.form_submit_button("🚀 Save Profile and Continue")

        # Handle form submissions - MOVED INSIDE THE FORM BLOCK
        if update_keywords_btn:
            # Handle keyword updates
            keywords_text = st.session_state.get("keywords_textarea", "")
            if keywords_text.strip():
                new_keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
                # Limit to 5 keywords
                new_keywords = new_keywords[:5]
                st.session_state.job_title_keywords = new_keywords
                st.success(f"✅ Keywords updated! ({len(new_keywords)} keywords saved)")
            else:
                st.session_state.job_title_keywords = []
                st.warning("⚠️ Keywords cleared")
            st.rerun()

        if add_education:
            # Add new education entry
            st.session_state.education_entries.append({
                "degree": "", "field_of_study": "", "institution": "", "graduation_year": "", 
                "id": str(uuid.uuid4()), "marked_for_removal": False
            })
            st.rerun()
        
        if add_experience:
            # Add new work experience entry
            st.session_state.experience_entries.append({
                "job_title": "", "company": "", "years_in_role": "0", "skills_responsibilities": "", 
                "id": str(uuid.uuid4()), "marked_for_removal": False
            })
            st.rerun()

        if submitted:
            # Step 1: Handle removals
            education_removed_flag = False
            if any(edu.get("marked_for_removal") for edu in st.session_state.education_entries):
                st.session_state.education_entries = [edu for edu in st.session_state.education_entries if not edu.get("marked_for_removal")]
                education_removed_flag = True
            
            experience_removed_flag = False
            if any(exp.get("marked_for_removal") for exp in st.session_state.experience_entries):
                st.session_state.experience_entries = [exp for exp in st.session_state.experience_entries if not exp.get("marked_for_removal")]
                experience_removed_flag = True

            if education_removed_flag or experience_removed_flag:
                st.toast("Marked item(s) have been removed. Review and submit the form again.", icon="♻️")
                st.rerun()

            # Step 2: Validation
            validation_passed = True
            if not target_roles_selected and not target_roles_custom.strip():
                st.error("Please specify at least one target role/industry."); validation_passed = False
            if not current_skills_selected and not current_skills_custom.strip():
                st.error("Please specify at least one current skill."); validation_passed = False
            if not overall_field:
                st.error("Please select a primary field."); validation_passed = False
            if not job_languages:
                st.error("Please select at least one preferred job language."); validation_passed = False
            if not job_types:
                st.error("Please select at least one desired job type."); validation_passed = False
            if not preferred_locations_dk:
                st.error("Please select at least one preferred job location in Denmark."); validation_passed = False
            if not personal_description.strip():
                st.error("Please write a personal description."); validation_passed = False
            if not st.session_state.job_title_keywords:
                st.error("Please add at least one job search keyword."); validation_passed = False

            for edu_entry in st.session_state.education_entries:
                if not edu_entry["degree"].strip() or not edu_entry["field_of_study"].strip() or not edu_entry["institution"].strip():
                    st.error("Fill in Degree, Field of Study and Institution for all education entries."); validation_passed = False; break
            
            for exp_entry in st.session_state.experience_entries:
                if not exp_entry["job_title"].strip() or not exp_entry["company"].strip():
                    st.error("Fill in Job Title and Company for all experience entries."); validation_passed = False; break
            
            if validation_passed:
                profile_data = {
                    "submission_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user_session_id": user_session_id_for_run,
                    "user_id_input": st.session_state.user_id,
                    "target_roles_industries_selected": target_roles_selected,
                    "target_roles_industries_custom": [r.strip() for r in target_roles_custom.split(',') if r.strip()],
                    "overall_field": overall_field,
                    "personal_description": personal_description.strip(),
                    "job_title_keywords": st.session_state.job_title_keywords,
                    "current_skills_selected": current_skills_selected,
                    "current_skills_custom": [s.strip() for s in current_skills_custom.split(',') if s.strip()],
                    "education_entries": [{k: v for k, v in edu.items() if k != 'marked_for_removal'} for edu in st.session_state.education_entries],
                    "total_experience": total_experience,
                    "work_experience_entries": [{k: v for k, v in exp.items() if k != 'marked_for_removal'} for exp in st.session_state.experience_entries],
                    "job_languages": job_languages,
                    "job_types": job_types,
                    "preferred_locations_dk": preferred_locations_dk,
                    "remote_openness": remote_openness,
                    "analysis_preference": analysis_preference
                }
                if log_user_profile(profile_data):
                    st.success("✅ Profile saved and logged successfully!")
                    st.balloons()
                    
                    # Store profile data in session state for job search
                    st.session_state.saved_profile_data = profile_data
                    st.session_state.profile_saved = True
                    
                    st.info(f"📋 Profile data saved to {USER_PROFILE_LOG_FILE}")
                else:
                    st.error("Error logging profile.")

    # Job Search Section - Outside the form but with session state management
    if st.session_state.get('profile_saved', False) and JOB_MATCHING_AVAILABLE:
        profile_data = st.session_state.get('saved_profile_data', {})
        
        # Always proceed with job search (comprehensive analysis is default)
        st.markdown("---")
        st.subheader("🔍 Finding Relevant Job Opportunities")
        st.markdown("*Search for jobs based on your profile data*")
        
        # Initialize job search state
        if 'job_search_started' not in st.session_state:
            st.session_state.job_search_started = False
        if 'job_search_completed' not in st.session_state:
            st.session_state.job_search_completed = False
        if 'job_search_results' not in st.session_state:
            st.session_state.job_search_results = None
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Show job search button
            if not st.session_state.job_search_started:
                start_search = st.button("🚀 Start Job Search Based on Your Profile", type="primary", key="start_job_search")
            elif st.session_state.job_search_started and not st.session_state.job_search_completed:
                st.info("🔍 Job search in progress... Please wait.")
                start_search = False
            else:
                st.success("✅ Job search completed!")
                start_search = False
        
        with col2:
            if st.session_state.job_search_completed:
                if st.button("🔄 Search Again", key="search_again"):
                    st.session_state.job_search_started = False
                    st.session_state.job_search_completed = False
                    st.session_state.job_search_results = None
                    st.rerun()

        # Handle job search execution
        if start_search:
            st.session_state.job_search_started = True
            st.rerun()
        
        # Execute search if started but not completed
        if st.session_state.job_search_started and not st.session_state.job_search_completed:
            with st.spinner("🔍 Searching for relevant jobs... This may take a few minutes."):
                try:
                    search_results = run_profile_job_search(profile_data)
                    st.session_state.job_search_results = search_results
                    
                    # Run data enrichment automatically after successful job search
                    if DATA_ENRICHMENT_AVAILABLE and search_results.get('source') == 'live_scraping':
                        with st.spinner("🔍 Enriching job data with company information..."):
                            try:
                                enrichment_result = run_data_enrichment_for_app(
                                    app_context="auto",
                                    batch_size=10,
                                    max_batches=3
                                )
                                
                                if enrichment_result["success"] and enrichment_result.get("stats"):
                                    improvements = enrichment_result["stats"]["improvements"]
                                    total_enriched = improvements.get("total", 0)
                                    if total_enriched > 0:
                                        st.success(f"✅ Enriched {total_enriched} job records with additional company information!")
                                
                            except Exception as e:
                                # Don't fail the whole search if enrichment fails
                                st.warning(f"⚠️ Job search successful, but data enrichment encountered an issue: {str(e)}")
                    
                    st.session_state.job_search_completed = True
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error during job search: {str(e)}")
                    st.session_state.job_search_started = False
                    
                    # Show detailed error info
                    with st.expander("🔍 Error Details"):
                        st.code(str(e))
                        st.markdown("**Possible solutions:**")
                        st.markdown("""
                        - Check your internet connection
                        - Verify that indeed_scraper.py and profile_job_matcher.py are working
                        - Try reducing the number of job search keywords
                        - Check if Indeed is accessible from your location
                        """)

        # Display results if completed
        if st.session_state.job_search_completed and st.session_state.job_search_results:
            search_results = st.session_state.job_search_results
            
            # Determine what source was used and get jobs accordingly
            source = search_results.get('source', 'unknown')
            fallback_used = search_results.get('fallback_used', False)
            total_jobs_found = search_results.get('total_jobs_found', 0)
            
            if source == 'live_scraping':
                # PRIMARY: Live scraping was successful
                if total_jobs_found > 0:
                    st.success(f"✅ Found {total_jobs_found} fresh jobs directly from Indeed!")
                    
                    # Get jobs from search results (they should be fresh from scraping)
                    matches = search_results.get('jobs', [])
                    if not matches:
                        # If jobs not in results, try to get them from database
                        matches = get_user_job_matches(user_session_id_for_run, limit=100)
                        if matches:
                            st.info(f"📊 Jobs have been saved to database. Displaying {len(matches)} matches.")
                    
                else:
                    st.warning("⚠️ Live scraping completed but found no new jobs matching your profile")
                    st.info("💡 Try adjusting your job search keywords or locations for broader results")
                    matches = []
            
            elif source == 'database_fallback':
                # FALLBACK: Database was used because scraping failed
                scraping_error = search_results.get('scraping_error', 'Unknown error')
                st.warning(f"⚠️ Live job scraping failed, using database fallback")
                st.info(f"📊 Found {total_jobs_found} jobs from local database")
                
                with st.expander("🔍 Why did live scraping fail?"):
                    st.write("**Scraping Error:**", scraping_error)
                    st.markdown("""
                    **Common reasons for scraping failure:**
                    - Network connectivity issues
                    - Indeed temporarily blocking requests
                    - Changes in Indeed's website structure
                    - Rate limiting or IP restrictions
                    
                    **What this means:**
                    - You're seeing jobs from our local database
                    - These may be slightly older but still relevant
                    - Try again later for fresh live results
                    """)
                
                matches = search_results.get('jobs', [])
            
            else:
                # FAILED: Both sources failed
                st.error("❌ Both live scraping and database search failed")
                error_msg = search_results.get('error', 'Unknown error')
                st.error(f"Error details: {error_msg}")
                
                st.markdown("""
                **What you can try:**
                1. Check your internet connection
                2. Try again in a few minutes
                3. Reduce the number of job search keywords
                4. Contact support if the problem persists
                """)
                matches = []

            # Display jobs if we have any
            total_existing_matches = len(matches) if matches else 0
            
            if total_existing_matches > 0:
                st.subheader("🎯 Your Job Matches")
                
                # Show source information with appropriate styling
                if source == 'live_scraping':
                    st.success(f"🔥 **Live Data Source**: {total_existing_matches} fresh jobs from Indeed")
                elif source == 'database_fallback':
                    st.info(f"📊 **Database Source**: {total_existing_matches} jobs from local storage (fallback)")
                
                try:
                    # Enhanced filter options
                    filter_col1, filter_col2 = st.columns(2)
                    
                    with filter_col1:
                        show_all = st.checkbox("Show all matches", value=False, help="Show all matches or limit to top 15")
                    
                    with filter_col2:
                        sort_by = st.selectbox(
                            "Sort by",
                            ["Date (newest first)", "Company name"],
                            help="Choose how to sort the job matches"
                        )
                    
                    # Apply sorting (no filtering by relevance score)
                    filtered_matches = matches  # Show all matches, no filtering
                    
                    # Apply sorting with null-safe handling
                    if sort_by == "Date (newest first)":
                        # Null-safe sorting: put None values at the end, handle empty strings
                        def safe_date_key(job):
                            timestamp = job.get('scraped_timestamp') or job.get('date_posted')
                            if timestamp is None or timestamp == '':
                                return '1900-01-01'  # Very old date to put at end when reverse=True
                            return str(timestamp)
                        
                        filtered_matches = sorted(filtered_matches, key=safe_date_key, reverse=True)
                    elif sort_by == "Company name":
                        # Null-safe sorting for company names
                        filtered_matches = sorted(filtered_matches, key=lambda x: (x.get('company') or '').lower())
                    
                    display_count = len(filtered_matches) if show_all else min(15, len(filtered_matches))
                    
                    # Show filtering results
                    st.write(f"Displaying {display_count} of {len(filtered_matches)} matches")
                    
                    if len(filtered_matches) > display_count:
                        st.info(f"💡 {len(filtered_matches) - display_count} more matches available. Check 'Show all matches' to see them.")
                    
                    # Add data freshness indicator
                    if source == 'live_scraping':
                        st.success("🕐 **Data Freshness**: These jobs were scraped within the last few minutes")
                    elif source == 'database_fallback':
                        st.info("🕐 **Data Freshness**: These jobs may be from previous scraping sessions")
                    
                    # Display job matches with enhanced information
                    for i, job in enumerate(filtered_matches[:display_count]):
                        with st.container(border=True):
                            # Header with job title and relevance
                            header_col1, header_col2 = st.columns([4, 1])
                            
                            with header_col1:
                                st.markdown(f"### **{job.get('title', 'Unknown Title')}**")
                                # Add freshness indicator
                                if source == 'live_scraping':
                                    st.markdown("🔥 **Fresh from Indeed**")
                            
                            with header_col2:
                                relevance_score = job.get('relevance_score', 1)
                                if relevance_score >= 70:
                                    st.success(f"🎯 {relevance_score}% Match")
                                elif relevance_score >= 50:
                                    st.warning(f"🟡 {relevance_score}% Match")
                                else:
                                    st.info(f"📊 {relevance_score}% Match")
                            
                            # Main job information - in two columns
                            info_col1, info_col2 = st.columns([2, 1])
                            
                            with info_col1:
                                # Company and location information
                                company_info = []
                                if job.get('company'):
                                    company_info.append(f"🏢 **{job['company']}**")
                                if job.get('location'):
                                    company_info.append(f"📍 {job['location']}")
                                if job.get('job_type'):
                                    company_info.append(f"💼 {job['job_type'].title()}")
                                if job.get('company_industry'):
                                    company_info.append(f"🏭 {job['company_industry']}")
                                
                                if company_info:
                                    st.markdown(" • ".join(company_info))
                                
                                # Quick overview of the job
                                description = job.get('description', '')
                                if description and len(description.strip()) > 10:
                                    # Show a brief preview
                                    preview = description[:150] + "..." if len(description) > 150 else description
                                    st.markdown(f"📝 **Quick overview:** {preview}")
                                    
                                    # Expandable full description
                                    with st.expander("📖 View Full Job Description", expanded=False):
                                        # Clean up the description for better display
                                        clean_description = description.replace('\n\n', '\n').strip()
                                        st.markdown(clean_description)
                                else:
                                    st.markdown("📝 **Description:** Not available")
                                
                                # Additional metadata in compact format
                                metadata_parts = []
                                if job.get('date_posted'):
                                    metadata_parts.append(f"📅 {job['date_posted']}")
                                if job.get('is_remote'):
                                    metadata_parts.append("🏠 Remote")
                                elif job.get('is_remote') is False:
                                    metadata_parts.append("🏢 On-site")
                                
                                if metadata_parts:
                                    st.caption(" • ".join(metadata_parts))
                            
                            with info_col2:
                                # Action buttons and scoring
                                if job.get('job_url'):
                                    st.link_button("🔗 View on Indeed", job['job_url'], use_container_width=True)
                                else:
                                    st.info("🔗 No direct link available")
                                
                                # Relevance score visualization
                                progress_value = min(1.0, max(0.0, relevance_score / 100))
                                st.progress(progress_value, text=f"Match: {relevance_score}%")
                    
                except Exception as e:
                    st.error(f"❌ Error displaying job matches: {str(e)}")
                    st.markdown("**Debug info:**")
                    st.write(f"Number of matches: {len(matches) if matches else 0}")
                    st.write(f"Search source: {source}")
                    st.write(f"Error details: {str(e)}")
                    
                    # Show fallback message
                    st.info("💡 Try refreshing the page or running a new job search")

            # CV-Job Evaluation Section - MOVED TO CORRECT POSITION (after job display, when we have matches)
            if CV_EVALUATION_AVAILABLE and total_existing_matches > 0:
                st.markdown("---")
                st.subheader("🤖 AI-Powered CV Analysis")
                st.markdown("*Get detailed analysis of how well your CV matches the available jobs*")
                
                # Show which jobs will be analyzed
                jobs_to_analyze = matches[:min(10, len(matches))]  # Limit to first 10 jobs
                st.info(f"🎯 Will analyze the top {len(jobs_to_analyze)} jobs from your matches above")
                
                # Initialize evaluation state
                if 'cv_evaluation_started' not in st.session_state:
                    st.session_state.cv_evaluation_started = False
                if 'cv_evaluation_completed' not in st.session_state:
                    st.session_state.cv_evaluation_completed = False
                if 'cv_evaluation_results' not in st.session_state:
                    st.session_state.cv_evaluation_results = None
                
                eval_col1, eval_col2 = st.columns([2, 1])
                
                with eval_col1:
                    if not st.session_state.cv_evaluation_started:
                        start_evaluation = st.button("🤖 Analyze My CV Against These Jobs", type="primary", key="start_cv_evaluation")
                    elif st.session_state.cv_evaluation_started and not st.session_state.cv_evaluation_completed:
                        st.info("🤖 AI is analyzing your CV... Please wait.")
                        start_evaluation = False
                    else:
                        st.success("✅ CV analysis completed!")
                        start_evaluation = False
                
                with eval_col2:
                    if st.session_state.cv_evaluation_completed:
                        if st.button("🔄 Re-analyze", key="restart_evaluation"):
                            st.session_state.cv_evaluation_started = False
                            st.session_state.cv_evaluation_completed = False
                            st.session_state.cv_evaluation_results = None
                            st.rerun()
                
                # Handle evaluation execution
                if start_evaluation:
                    st.session_state.cv_evaluation_started = True
                    st.rerun()
                
                # Execute evaluation if started but not completed
                if st.session_state.cv_evaluation_started and not st.session_state.cv_evaluation_completed:
                    with st.spinner("🤖 AI is analyzing your CV against job requirements... This may take several minutes."):
                        try:
                            # Pass the actual jobs from matches instead of fetching from database
                            # This ensures we analyze exactly the same jobs shown in the matches section
                            evaluator = CVJobEvaluator()
                            evaluation_results = evaluator.evaluate_cv_against_specific_jobs(
                                user_session_id_for_run, 
                                jobs_to_analyze,  # Use the exact same jobs
                                profile_data  # Pass profile data for context
                            )
                            st.session_state.cv_evaluation_results = evaluation_results
                            st.session_state.cv_evaluation_completed = True
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Error during CV evaluation: {str(e)}")
                            st.session_state.cv_evaluation_started = False
                            
                            # Show detailed error info
                            with st.expander("🔍 Error Details"):
                                st.code(str(e))
                                st.markdown("**Possible solutions:**")
                                st.markdown("""
                                - Check your Together AI API key configuration
                                - Verify that cv_job_evaluator.py is working correctly
                                - Try with fewer jobs (the analysis is compute-intensive)
                                - Check internet connection for AI service access
                                """)

                # DISPLAY CV EVALUATION RESULTS:
                if st.session_state.cv_evaluation_completed and st.session_state.cv_evaluation_results:
                    evaluation_results = st.session_state.cv_evaluation_results
                    
                    # Check if evaluation was successful
                    if "error" in evaluation_results:
                        st.error(f"❌ CV Evaluation Error: {evaluation_results['error']}")
                        
                        # Show fallback options
                        if evaluation_results.get('fallback_mode'):
                            st.info("📋 Using basic compatibility assessment based on profile matching")
                        else:
                            st.info("💡 Try running the evaluation again or check your profile data")
                    
                    else:
                        # Display successful evaluation results
                        st.markdown("### 📊 CV Analysis Results")
                        
                        # Show summary statistics
                        summary = evaluation_results.get('summary', {})
                        avg_score = summary.get('average_match_score', 0)
                        jobs_evaluated = evaluation_results.get('jobs_evaluated', 0)
                        
                        # Create summary cards
                        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
                        
                        with summary_col1:
                            st.metric(
                                label="📈 Average Match Score",
                                value=f"{avg_score}%",
                                delta=f"vs {sum(job.get('relevance_score', 0) for job in matches[:jobs_evaluated])//max(jobs_evaluated,1)}% profile score" if matches else None
                            )
                        
                        with summary_col2:
                            st.metric(
                                label="🎯 Jobs Analyzed", 
                                value=jobs_evaluated
                            )
                        
                        with summary_col3:
                            score_dist = summary.get('score_distribution', {})
                            high_matches = score_dist.get('high (70-100)', 0)
                            st.metric(
                                label="⭐ High Matches", 
                                value=high_matches,
                                delta=f"{round(high_matches/max(jobs_evaluated,1)*100,1)}%" if jobs_evaluated > 0 else "0%"
                            )
                        
                        with summary_col4:
                            model_used = evaluation_results.get('evaluation_model', 'AI Analysis')
                            if 'fallback' in model_used.lower():
                                st.metric(label="🤖 Analysis Type", value="Basic")
                            else:
                                st.metric(label="🤖 Analysis Type", value="AI-Powered")
                        
                        # Display individual job evaluations
                        st.markdown("---")
                        st.markdown("### 🔍 Detailed Job Analysis")
                        
                        evaluations = evaluation_results.get('evaluations', [])
                        if evaluations:
                            # Sort evaluations by match score
                            sorted_evaluations = sorted(evaluations, 
                                                      key=lambda x: x.get('match_score', 0), 
                                                      reverse=True)
                            
                            for i, evaluation in enumerate(sorted_evaluations):
                                with st.container(border=True):
                                    # Job header
                                    job_col1, job_col2 = st.columns([3, 1])
                                    
                                    with job_col1:
                                        job_title = evaluation.get('job_title', 'Unknown Position')
                                        company = evaluation.get('company', 'Unknown Company')
                                        st.markdown(f"#### 💼 {job_title}")
                                        st.markdown(f"**🏢 {company}** • {evaluation.get('location', 'Unknown Location')}")
                                    
                                    with job_col2:
                                        match_score = evaluation.get('match_score', 0)
                                        if match_score >= 80:
                                            st.success(f"🌟 {match_score}% Match")
                                        elif match_score >= 60:
                                            st.warning(f"⚡ {match_score}% Match")
                                        else:
                                            st.info(f"📊 {match_score}% Match")
                                    
                                    # Main evaluation content
                                    eval_col1, eval_col2 = st.columns([2, 1])
                                    
                                    with eval_col1:
                                        # Core assessment
                                        overall_fit = evaluation.get('overall_fit', 'Not assessed')
                                        reality_check = evaluation.get('reality_check', 'No assessment available')
                                        
                                        st.markdown("**🎯 Overall Assessment:**")
                                        st.markdown(f"*{overall_fit}* - {reality_check}")
                                        
                                        # Strengths and gaps
                                        strengths = evaluation.get('strengths', 'No strengths identified')
                                        critical_gaps = evaluation.get('critical_gaps', 'No critical gaps identified')
                                        
                                        st.markdown("**✅ Your Strengths for this Role:**")
                                        st.markdown(f"{strengths}")
                                        
                                        if critical_gaps and critical_gaps != 'No critical gaps identified':
                                            st.markdown("**🔍 Areas to Address:**")
                                            st.markdown(f"{critical_gaps}")
                                        
                                        # Recommendations
                                        recommendations = evaluation.get('recommendations', 'No specific recommendations')
                                        if recommendations and recommendations != 'No specific recommendations':
                                            st.markdown("**💡 Action Items:**")
                                            st.markdown(f"{recommendations}")
                                    
                                    with eval_col2:
                                        # Quick facts sidebar
                                        st.markdown("**📋 Quick Facts:**")
                                        
                                        seniority_match = evaluation.get('seniority_match', 'Not assessed')
                                        if seniority_match != 'Not assessed':
                                            st.markdown(f"**Experience Level:** {seniority_match}")
                                        
                                        likelihood = evaluation.get('likelihood', 'Unknown')
                                        if likelihood == 'High':
                                            st.success(f"🎯 Interview Chance: {likelihood}")
                                        elif likelihood == 'Medium':
                                            st.warning(f"⚡ Interview Chance: {likelihood}")
                                        else:
                                            st.info(f"📊 Interview Chance: {likelihood}")
                                        
                                        # Experience gap info
                                        exp_gap = evaluation.get('experience_gap', '')
                                        if exp_gap and len(exp_gap) > 10 and 'not available' not in exp_gap.lower():
                                            st.markdown(f"**Experience Gap:** {exp_gap[:100]}{'...' if len(exp_gap) > 100 else ''}")
                                        
                                        # Show job URL if available
                                        job_url = evaluation.get('job_url', '')
                                        if job_url:
                                            st.link_button("🔗 View Job", job_url, use_container_width=True)
                                        
                                        # Progress bar for match score
                                        progress_value = min(1.0, max(0.0, match_score / 100))
                                        st.progress(progress_value, text=f"AI Match: {match_score}%")
                                    
                                    # Show if this was fallback analysis
                                    if evaluation.get('fallback_mode') or evaluation.get('parsing_fallback'):
                                        st.caption("⚠️ Basic analysis (AI parsing limited)")
                        
                        else:
                            st.warning("No individual job evaluations available")
                            st.info("This might be due to parsing issues with the AI response")
                        
                        # Add action buttons section
                        st.markdown("---")
                        action_col1, action_col2 = st.columns(2)
                        
                        with action_col1:
                            if st.button("📊 Export Results", key="export_results"):
                                # Create downloadable results
                                results_text = f"""CV Analysis Results
Generated: {evaluation_results.get('evaluation_timestamp', 'Unknown')}
Average Match Score: {avg_score}%
Jobs Analyzed: {jobs_evaluated}

DETAILED RESULTS:
"""
                                for eval in evaluations:
                                    results_text += f"""
{eval.get('job_title', 'Unknown')} at {eval.get('company', 'Unknown')}
Match Score: {eval.get('match_score', 0)}%
Overall Fit: {eval.get('overall_fit', 'Not assessed')}
Strengths: {eval.get('strengths', 'Not listed')}
Recommendations: {eval.get('recommendations', 'None provided')}
---
"""
                                
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                                filename = f"cv_analysis_{timestamp}.txt"
                                
                                st.download_button(
                                    label="📥 Download Analysis",
                                    data=results_text.encode('utf-8'),
                                    file_name=filename,
                                    mime="text/plain",
                                    key="download_analysis_btn"
                                )
                        
                        with action_col2:
                            # Show improvement plan button
                            if st.button("📈 Get Improvement Plan", type="primary", key="get_improvement_plan"):
                                st.session_state.show_improvement_plan = True

                # Handle improvement plan execution
                if st.session_state.get('show_improvement_plan', False) and st.session_state.get('cv_evaluation_completed', False):
                    with st.spinner("🤖 AI is generating your personalized improvement plan..."):
                        try:
                            improvement_plan = generate_user_improvement_plan(user_session_id_for_run)
                            
                            if "error" not in improvement_plan:
                                st.session_state.improvement_plan_results = improvement_plan
                                st.session_state.show_improvement_plan = False  # Reset trigger
                                st.success("✅ Improvement plan generated!")
                                st.rerun()
                            else:
                                st.error(f"❌ Could not generate improvement plan: {improvement_plan['error']}")
                                st.session_state.show_improvement_plan = False
                        
                        except Exception as e:
                            error_str = str(e)
                            st.error(f"❌ Error generating improvement plan: {error_str}")
                            st.session_state.show_improvement_plan = False

                # Display improvement plan if available
                if st.session_state.get('improvement_plan_results'):
                    improvement_plan = st.session_state.improvement_plan_results
                    
                    st.markdown("---")
                    st.subheader("📈 Personalized Career Improvement Plan")
                    
                    # Show if this is fallback mode
                    if improvement_plan.get('fallback_mode'):
                        st.info("📋 **Basic Plan** - AI service was unavailable, showing fundamental recommendations")
                    
                    # Display the improvement plan using Streamlit's markdown
                    plan_text = improvement_plan.get('improvement_plan', 'No plan available')
                    st.markdown(plan_text)
                    
                    # Simplified action buttons
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Create downloadable markdown file
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                        user_field = profile_data.get('overall_field', 'Unknown')
                        user_field_clean = re.sub(r'[^\w\-_]', '_', user_field)
                        filename = f"career_plan_{user_field_clean}_{timestamp}.md"
                        
                        # Create markdown content with header
                        markdown_content = f"""# Career Improvement Plan

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  
**Field:** {profile_data.get('overall_field', 'Unknown')}  
**Experience:** {profile_data.get('total_experience', 'Unknown')}  

---

{plan_text}

---
*Generated by SkillScope Career Assistant*
"""
                        
                        st.download_button(
                            label="📄 Download as Markdown",
                            data=markdown_content.encode('utf-8'),
                            file_name=filename,
                            mime="text/markdown",
                            key="markdown_download_btn"
                        )
                    
                    with col2:
                        # Text file alternative
                        txt_filename = f"career_plan_{user_field_clean}_{timestamp}.txt"
                        
                        # Clean markdown for text file
                        clean_text = re.sub(r'#{1,4}\s*', '', plan_text)  # Remove headers
                        clean_text = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_text)  # Remove bold
                        clean_text = re.sub(r'\*(.*?)\*', r'\1', clean_text)  # Remove italics
                        
                        txt_content = f"""Career Improvement Plan
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Field: {profile_data.get('overall_field', 'Unknown')}
Experience: {profile_data.get('total_experience', 'Unknown')}

{clean_text}

Generated by SkillScope Career Assistant
"""
                        
                        st.download_button(
                            label="📄 Download as Text",
                            data=txt_content.encode('utf-8'),
                            file_name=txt_filename,
                            mime="text/plain",
                            key="txt_download_btn"
                        )
                    
                    with col3:
                        if st.button("🔄 Generate New Plan", key="new_plan_btn"):
                            # Clear the current plan and trigger regeneration
                            if 'improvement_plan_results' in st.session_state:
                                del st.session_state.improvement_plan_results
                            st.session_state.show_improvement_plan = True
                            st.rerun()

# make file runable
if __name__ == "__main__":
    run_app()

# Ensure the run_app() function is exported
__all__ = ['run_app']

# Complete the missing parts in cv_job_evaluator.py functions
def format_jobs_for_evaluation(jobs: List[Dict]) -> str:
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