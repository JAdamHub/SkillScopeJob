import os
import uuid
import csv
import json
import logging
import streamlit as st
import streamlit.components.v1 as components
import sqlite3
from datetime import datetime

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
    from cv_extraction import LLMCVExtractor
    CV_EXTRACTION_AVAILABLE = True
except ImportError as e:
    CV_EXTRACTION_AVAILABLE = False
    CV_EXTRACTION_ERROR = str(e)

# Import job matching functionality
try:
    from profile_job_matcher import run_profile_job_search, get_user_job_matches
    JOB_MATCHING_AVAILABLE = True
except ImportError as e:
    JOB_MATCHING_AVAILABLE = False
    JOB_MATCHING_ERROR = str(e)

# Import CV-job evaluation functionality
try:
    from cv_job_evaluator import evaluate_user_cv_matches, get_user_latest_evaluation, generate_user_improvement_plan
    CV_EVALUATION_AVAILABLE = True
except ImportError as e:
    CV_EVALUATION_AVAILABLE = False
    CV_EVALUATION_ERROR = str(e)

# --- Constants for file names ---
ROLES_INDUSTRIES_ONTOLOGY_FILE = "roles_industries_ontology.csv"
SKILL_ONTOLOGY_FILE = "skill_ontology.csv"
EDUCATION_ONTOLOGY_FILE = "education_ontology.csv"
USER_PROFILE_LOG_FILE = "advanced_user_profile_log.csv"

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
            st.markdown("### 🔑 AI Configuration")
            api_key = st.text_input(
                "Together AI API Key", 
                type="password",
                value=os.getenv("TOGETHER_API_KEY", ""),
                help="Enter your Together AI API key or set TOGETHER_API_KEY environment variable"
            )
            
            # Model selection
            model_options = [
                "meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo",
                "meta-llama/Llama-3.1-70B-Instruct-Turbo",
                "meta-llama/Llama-3.1-8B-Instruct-Turbo",
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
                            if cv_data.get('education_entries'):
                                st.session_state.education_entries = cv_data['education_entries']
                            if cv_data.get('experience_entries'):
                                st.session_state.experience_entries = cv_data['experience_entries']
                            
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
    default_education = [
        ("B.Sc.", "Computer Science", "University of Copenhagen"),
        ("M.Sc.", "Software Engineering", "Aalborg University"),
        ("Cand.merc.", "International Business", "Copenhagen Business School"),
        ("PhD", "Artificial Intelligence", "Technical University of Denmark"),
        ("Computer Science Diploma", "", "Business Academy Aarhus"),
        ("HA", "", "University of Southern Denmark"),
        ("Cand.polit", "", "University of Copenhagen"),
        ("Master", "Computer Science", "University of Southern Denmark"),
        ("Bachelor", "Economics", "Aarhus University")
    ]
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
        analysis_options = ["Quick scan (guidance)", "Deep Analysis (comprehensive)"]
        analysis_preference = st.selectbox("📊 Analysis Preference:", options=analysis_options, index=1, key="analysis_select")

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
        analysis_preference = profile_data.get('analysis_preference', '')
        
        if analysis_preference == "Deep Analysis (comprehensive)":
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
            
            col1, col2, col3 = st.columns([2, 1, 1])
            
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
            
            with col3:
                if st.session_state.get('job_search_results'):
                    if st.button("📊 View All Jobs", key="view_dashboard"):
                        st.info("💡 Run the streamlit_app.py dashboard to view all scraped jobs")

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
                
                # ALWAYS fetch existing matches from database - this is the primary source
                try:
                    matches = get_user_job_matches(user_session_id_for_run, limit=100)
                    total_existing_matches = len(matches) if matches else 0
                    
                    # Log database fetch for debugging
                    import logging
                    logging.info(f"Fetched {total_existing_matches} job matches from database for user {user_session_id_for_run}")
                    
                except Exception as e:
                    matches = []
                    total_existing_matches = 0
                    st.error(f"❌ Error fetching jobs from database: {str(e)}")
                    st.info("💡 Check that the database exists and contains job data")
                
                # Show results - focus on database matches, not scraping results
                if total_existing_matches > 0:
                    # Success message based on whether new jobs were scraped
                    if search_results['total_jobs_found'] > 0:
                        st.success(f"✅ Found {search_results['total_jobs_found']} new jobs and loaded {total_existing_matches} total relevant positions from database.")
                    else:
                        st.success(f"✅ Search completed! Loaded {total_existing_matches} relevant positions from database.")
                        st.info("ℹ️ No new jobs were scraped (they may already exist in database)")
                    
                    st.subheader("🎯 Your Job Matches (from Database)")
                    
                    # Show database source information
                    st.info(f"📊 Showing jobs from local database. Total matches found: {total_existing_matches}")
                    
                    try:
                        # Add enhanced filter options
                        filter_col1, filter_col2, filter_col3 = st.columns(3)
                        
                        with filter_col1:
                            show_all = st.checkbox("Show all matches", value=False, help="Show all matches or limit to top 10")
                        
                        with filter_col2:
                            min_relevance = st.selectbox(
                                "Minimum relevance score", 
                                [1, 2, 3], 
                                index=0,
                                help="Filter by relevance: 3=Excellent, 2=Good, 1=Fair"
                            )
                        
                        with filter_col3:
                            sort_by = st.selectbox(
                                "Sort by",
                                ["Relevance (highest first)", "Date (newest first)", "Company name"],
                                help="Choose how to sort the job matches"
                            )
                        
                        # Apply filters and sorting
                        filtered_matches = [job for job in matches if job.get('relevance_score', 1) >= min_relevance]
                        
                        # Apply sorting
                        if sort_by == "Date (newest first)":
                            filtered_matches = sorted(filtered_matches, key=lambda x: x.get('scraped_timestamp', ''), reverse=True)
                        elif sort_by == "Company name":
                            filtered_matches = sorted(filtered_matches, key=lambda x: x.get('company', '').lower())
                        else:  # Default: Relevance
                            filtered_matches = sorted(filtered_matches, key=lambda x: x.get('relevance_score', 1), reverse=True)
                        
                        display_count = len(filtered_matches) if show_all else min(15, len(filtered_matches))
                        
                        # Show filtering results
                        st.write(f"Displaying {display_count} of {len(filtered_matches)} matches (filtered from {total_existing_matches} total)")
                        
                        if len(filtered_matches) > display_count:
                            st.info(f"💡 {len(filtered_matches) - display_count} more matches available. Check 'Show all matches' to see them.")
                        
                        # Display job matches with enhanced information
                        for i, job in enumerate(filtered_matches[:display_count]):
                            with st.container(border=True):
                                # Header with job title and relevance
                                header_col1, header_col2 = st.columns([4, 1])
                                
                                with header_col1:
                                    st.markdown(f"### **{job.get('title', 'Unknown Title')}**")
                                
                                with header_col2:
                                    relevance_score = job.get('relevance_score', 1)
                                    if relevance_score >= 8:
                                        st.markdown("🎯 **Excellent**")
                                    elif relevance_score >= 5:
                                        st.markdown("🟡 **Good**")
                                    else:
                                        st.markdown("🔴 **Fair**")
                                
                                # Main job information
                                info_col1, info_col2 = st.columns([3, 1])
                                
                                with info_col1:
                                    # Company and location
                                    company_info = []
                                    if job.get('company'):
                                        company_info.append(f"🏢 **{job['company']}**")
                                    if job.get('location'):
                                        company_info.append(f"📍 {job['location']}")
                                    if job.get('job_type'):
                                        company_info.append(f"💼 {job['job_type']}")
                                    
                                    if company_info:
                                        st.markdown(" | ".join(company_info))
                                    
                                    # Enhanced company information if available
                                    if job.get('company_industry'):
                                        st.markdown(f"🏭 **Industry:** {job['company_industry']}")
                                    
                                    # Job description preview
                                    description = job.get('description', '')
                                    if description and len(description) > 10:
                                        # Clean up description and show preview
                                        clean_desc = description.replace('\n', ' ').replace('\r', ' ')
                                        preview_length = 200
                                        if len(clean_desc) > preview_length:
                                            clean_desc = clean_desc[:preview_length] + "..."
                                        st.markdown(f"📝 {clean_desc}")
                                    else:
                                        st.markdown("📝 *No description available*")
                                    
                                    # Additional metadata
                                    metadata_parts = []
                                    if job.get('date_posted'):
                                        metadata_parts.append(f"📅 Posted: {job['date_posted']}")
                                    if job.get('scraped_timestamp'):
                                        # Show just the date part
                                        scraped_date = job['scraped_timestamp'].split(' ')[0] if ' ' in job['scraped_timestamp'] else job['scraped_timestamp']
                                        metadata_parts.append(f"🔍 Found: {scraped_date}")
                                    
                                    if metadata_parts:
                                        st.caption(" • ".join(metadata_parts))
                                
                                with info_col2:
                                    # Action buttons and score
                                    if job.get('job_url'):
                                        st.link_button("🔗 View Job", job['job_url'], use_container_width=True)
                                    
                                    # Relevance score visualization - FIX THE PROGRESS BAR ERROR
                                    score_percentage = min(100, max(0, (relevance_score / 10) * 100))  # Normalize to 0-100
                                    progress_value = score_percentage / 100  # Convert to 0.0-1.0 for progress bar
                                    st.progress(progress_value)
                                    st.caption(f"Match: {score_percentage:.0f}%")
                                    
                                    # Database source indicator
                                    st.caption("💾 From Database")
                        
                        # Additional database statistics
                        if total_existing_matches > 0:
                            st.markdown("---")
                            
                            stats_col1, stats_col2, stats_col3 = st.columns(3)
                            
                            with stats_col1:
                                excellent_matches = len([job for job in matches if job.get('relevance_score', 1) >= 8])
                                st.metric("🎯 Excellent Matches", excellent_matches)
                            
                            with stats_col2:
                                good_matches = len([job for job in matches if job.get('relevance_score', 1) >= 5 and job.get('relevance_score', 1) < 8])
                                st.metric("🟡 Good Matches", good_matches)
                            
                            with stats_col3:
                                companies = len(set([job.get('company', '').lower() for job in matches if job.get('company')]))
                                st.metric("🏢 Unique Companies", companies)

                    except Exception as e:
                        st.error(f"❌ Error displaying job matches: {str(e)}")
                        st.info("💡 Jobs were found in database but couldn't be displayed properly")
                        
                        # Show raw count as fallback
                        st.info(f"Found {total_existing_matches} job matches in database")
                
                else:
                    # No matches found in database at all
                    if search_results['total_jobs_found'] > 0:
                        st.warning(f"⚠️ Scraped {search_results['total_jobs_found']} new jobs, but no matches found in database for your profile")
                        st.info("💡 The scraped jobs may not match your keywords/criteria, or there may be a database issue")
                    else:
                        st.warning("❌ No relevant jobs found in database and no new jobs were scraped")
                        
                        st.markdown("**This might be because:**")
                        st.markdown("""
                        - 🔍 Your search keywords are too specific
                        - 📍 No jobs match your location preferences  
                        - 💾 The database is empty - try running the general scraper first
                        - 🌐 Indeed has limited results for your search terms
                        - ⚙️ Database connection issues
                        """)
                        
                        st.info("💡 **Recommended actions:**")
                        st.markdown("""
                        1. Try broader job search keywords
                        2. Run `python indeed_scraper.py` to populate the database
                        3. Check that the database file `indeed_jobs.db` exists
                        4. Try the general job dashboard to see all available jobs
                        """)
                    
                    # Show search details for debugging
                    with st.expander("🔍 Search Details & Debugging"):
                        st.json({
                            "search_results": search_results,
                            "user_id": user_session_id_for_run,
                            "total_database_matches": total_existing_matches,
                            "search_keywords": profile_data.get('job_title_keywords', []),
                            "locations": profile_data.get('preferred_locations_dk', [])
                        })
                        
                        # Database connection test
                        try:
                            db_path = "indeed_jobs.db"
                            if os.path.exists(db_path):
                                conn = sqlite3.connect(db_path)
                                cursor = conn.cursor()
                                cursor.execute("SELECT COUNT(*) FROM job_postings")
                                total_jobs = cursor.fetchone()[0]
                                conn.close()
                                st.info(f"✅ Database connection OK. Total jobs in database: {total_jobs}")
                            else:
                                st.error(f"❌ Database file '{db_path}' not found")
                        except Exception as db_e:
                            st.error(f"❌ Database connection failed: {str(db_e)}")
    
    # Add CV-Job Evaluation Section
    if (CV_EVALUATION_AVAILABLE and 
        st.session_state.get('job_search_completed', False) and 
        st.session_state.get('job_search_results')):
        
        search_results = st.session_state.job_search_results
        
        if search_results.get('total_jobs_found', 0) > 0:
            st.markdown("---")
            st.subheader("🎯 AI-Powered CV-Job Match Analysis")
            st.markdown("*Get detailed feedback on how well your profile matches available positions*")
            
            # Initialize evaluation state
            if 'cv_evaluation_started' not in st.session_state:
                st.session_state.cv_evaluation_started = False
            if 'cv_evaluation_completed' not in st.session_state:
                st.session_state.cv_evaluation_completed = False
            if 'cv_evaluation_results' not in st.session_state:
                st.session_state.cv_evaluation_results = None

            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                if not st.session_state.cv_evaluation_started:
                    start_evaluation = st.button("🤖 Analyze CV vs Jobs with AI", type="primary", key="start_cv_eval")
                elif st.session_state.cv_evaluation_started and not st.session_state.cv_evaluation_completed:
                    st.info("🤖 AI is analyzing your CV against job postings... Please wait.")
                    start_evaluation = False
                else:
                    st.success("✅ CV-Job analysis completed!")
                    start_evaluation = False
            
            with col2:
                if st.session_state.cv_evaluation_completed:
                    if st.button("🔄 Re-analyze", key="reanalyze_cv"):
                        st.session_state.cv_evaluation_started = False
                        st.session_state.cv_evaluation_completed = False
                        st.session_state.cv_evaluation_results = None
                        st.rerun()
            
            with col3:
                if st.session_state.cv_evaluation_completed and st.session_state.cv_evaluation_results:
                    show_improvement_plan = st.button("📈 Get Improvement Plan", key="show_improvement_plan")
            
            # Handle evaluation execution
            if start_evaluation:
                st.session_state.cv_evaluation_started = True
                st.rerun()
            
            # Execute evaluation if started but not completed
            if st.session_state.cv_evaluation_started and not st.session_state.cv_evaluation_completed:
                with st.spinner("🤖 AI is analyzing your CV against job postings... This may take a moment."):
                    try:
                        evaluation_results = evaluate_user_cv_matches(user_session_id_for_run, max_jobs=10)
                        
                        # Debug: Show what we got back
                        st.info(f"🔍 Debug: Received evaluation with {len(evaluation_results.get('evaluations', []))} evaluations")
                        
                        if "error" in evaluation_results:
                            st.error(f"❌ Evaluation failed: {evaluation_results['error']}")
                            st.session_state.cv_evaluation_started = False
                        else:
                            st.session_state.cv_evaluation_results = evaluation_results
                            st.session_state.cv_evaluation_completed = True
                            st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error during evaluation: {str(e)}")
                        st.session_state.cv_evaluation_started = False
                        
                        # Show detailed error info
                        with st.expander("🔍 Error Details"):
                            st.code(str(e))
                            st.info("💡 This might be due to API limitations or network issues. Try again in a moment.")

            # Display evaluation results
            if st.session_state.cv_evaluation_completed and st.session_state.cv_evaluation_results:
                evaluation_results = st.session_state.cv_evaluation_results
                
                # Debug information
                with st.expander("🔍 Debug Information"):
                    st.write("Evaluation Results Structure:")
                    st.json({
                        "evaluations_count": len(evaluation_results.get('evaluations', [])),
                        "summary_keys": list(evaluation_results.get('summary', {}).keys()),
                        "has_error": "error" in evaluation_results,
                        "evaluation_status": evaluation_results.get('evaluation_status', 'normal')
                    })
                
                if "error" in evaluation_results:
                    st.error(f"❌ Evaluation failed: {evaluation_results['error']}")
                else:
                    # Check if we have valid evaluations
                    evaluations = evaluation_results.get('evaluations', [])
                    if not evaluations:
                        st.warning("⚠️ No evaluations found in results")
                        st.info("This might be due to parsing issues. Check the debug information above.")
                    else:
                        st.success("✅ CV analysis completed!")
                        
                        # Summary metrics with fallback handling
                        summary = evaluation_results.get('summary', {})
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            avg_score = summary.get('average_match_score', 0)
                            st.metric("Average Match Score", f"{avg_score}%")
                        
                        with col2:
                            jobs_count = evaluation_results.get('jobs_evaluated', len(evaluations))
                            st.metric("Jobs Analyzed", jobs_count)
                        
                        with col3:
                            best_score = 0
                            if evaluations:
                                best_score = max([e.get('match_score', 0) for e in evaluations])
                            st.metric("Best Match", f"{best_score}%")
                        
                        with col4:
                            high_likelihood = summary.get('high_interview_likelihood', 0)
                            st.metric("High Interview Likelihood", high_likelihood)
                        
                        # Detailed job evaluations with enhanced display
                        st.subheader("📊 Detailed Job Evaluations")
                        
                        if evaluations:
                            # Sort evaluations by match score
                            sorted_evaluations = sorted(evaluations, 
                                                      key=lambda x: x.get('match_score', 0), 
                                                      reverse=True)
                            
                            for i, evaluation in enumerate(sorted_evaluations):
                                with st.expander(f"🎯 {evaluation.get('job_title', 'Unknown Position')} at {evaluation.get('company', 'Unknown Company')} - {evaluation.get('match_score', 0)}% Match"):
                                    
                                    # Basic job info
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.write(f"**Company:** {evaluation.get('company', 'N/A')}")
                                        st.write(f"**Location:** {evaluation.get('location', 'N/A')}")
                                        st.write(f"**Industry:** {evaluation.get('company_industry', 'N/A')}")
                                    
                                    with col2:
                                        st.write(f"**Match Score:** {evaluation.get('match_score', 0)}%")
                                        st.write(f"**Overall Fit:** {evaluation.get('overall_fit', 'N/A')}")
                                        st.write(f"**Interview Likelihood:** {evaluation.get('likelihood', 'N/A')}")
                                    
                                    # Detailed analysis
                                    if evaluation.get('reality_check'):
                                        st.write("**💭 Reality Check:**")
                                        st.write(evaluation['reality_check'])
                                    
                                    if evaluation.get('strengths'):
                                        st.write("**✅ Your Strengths:**")
                                        st.success(evaluation['strengths'])
                                    
                                    if evaluation.get('critical_gaps'):
                                        st.write("**❗ Critical Gaps:**")
                                        st.warning(evaluation['critical_gaps'])
                                    
                                    if evaluation.get('recommendations'):
                                        st.write("**💡 Recommendations:**")
                                        st.info(evaluation['recommendations'])
                                    
                                    # Link to job if available
                                    if evaluation.get('job_url'):
                                        st.markdown(f"[🔗 View Job Posting]({evaluation['job_url']})")
                                    
                                    # Show any parsing issues
                                    if evaluation.get('parsing_status'):
                                        st.caption(f"ℹ️ {evaluation['parsing_status']}")
                        else:
                            st.warning("⚠️ No detailed evaluations available")
                            
                            # Show raw summary if available
                            if summary:
                                st.write("**Available Summary Data:**")
                                st.json(summary)

# ...existing code...