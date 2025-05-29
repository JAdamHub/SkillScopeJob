import streamlit as st
import uuid
import csv
from datetime import datetime
import os
import json

# --- Konstanter for filnavne ---
ROLES_INDUSTRIES_ONTOLOGY_FILE = "roles_industries_ontology.csv"
SKILL_ONTOLOGY_FILE = "skill_ontology.csv"
EDUCATION_ONTOLOGY_FILE = "education_ontology.csv" # Ny ontologifil
USER_PROFILE_LOG_FILE = "advanced_user_profile_log.csv"

# --- Hjælpefunktioner til at indlæse ontologier (med dummy oprettelse) ---
def load_ontology_data(file_path: str, column_name: str, default_items: list, is_education_ontology: bool = False) -> list | dict:
    """Indlæser data fra en CSV-ontologifil. Opretter en dummyfil hvis den ikke findes.
       For uddannelsesontologi, returner en dict med lister for hver kolonne.
    """
    if not os.path.exists(file_path):
        print(f"INFO: Ontologifil ikke fundet: {file_path}. Opretter en dummy-fil.")
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if is_education_ontology:
                    # Specifikke headers for uddannelsesontologi
                    writer.writerow(["degree_name", "field_of_study_name", "institution_name"])
                    for deg, fos, inst in default_items: # Forventer tupler/lister for default uddannelse
                        writer.writerow([deg, fos, inst])
                else:
                    writer.writerow([column_name]) # Header
                    for item in default_items:
                        writer.writerow([item])
        except Exception as e:
            print(f"ERROR: Kunne ikke oprette dummy ontologifil {file_path}: {e}")
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
                    print(f"ERROR: En eller flere påkrævede kolonner {expected_cols} mangler i {file_path}")
                    return {col: [] for col in expected_cols} # Returner tomme lister
                for row in reader:
                    if row.get("degree_name"): education_data["degree_name"].add(row["degree_name"])
                    if row.get("field_of_study_name"): education_data["field_of_study_name"].add(row["field_of_study_name"])
                    if row.get("institution_name"): education_data["institution_name"].add(row["institution_name"])
                return {k: sorted(list(v)) for k, v in education_data.items()}
            else:
                if column_name not in reader.fieldnames:
                    print(f"ERROR: Kolonne '{column_name}' mangler i {file_path}")
                    return default_items 
                items = [row[column_name] for row in reader if row.get(column_name)]
                return sorted(list(set(items)))
    except Exception as e:
        print(f"ERROR: Fejl under indlæsning af ontologifil {file_path}: {e}")
        if is_education_ontology:
            return { "degree_name": [], "field_of_study_name": [], "institution_name": [] }
        return default_items

# --- Initialisering af Session State for dynamiske lister ---
def initialize_session_state():
    if 'education_entries' not in st.session_state:
        st.session_state.education_entries = []
    if 'experience_entries' not in st.session_state:
        st.session_state.experience_entries = []
    if 'user_id' not in st.session_state:
        st.session_state.user_id = ""
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

# --- Funktioner til at håndtere dynamiske inputfelter (uddannelse, erfaring) ---
def add_education_entry_callback():
    st.session_state.education_entries.append({
        "degree": "", "field_of_study": "", "institution": "", "graduation_year": "", "id": str(uuid.uuid4()), "marked_for_removal": False
    })

def add_experience_entry_callback():
    st.session_state.experience_entries.append({
        "job_title": "", "company": "", "years_in_role": "0", "skills_responsibilities": "", "id": str(uuid.uuid4()), "marked_for_removal": False
    })

# --- Funktion til at logge brugerprofil ---
def log_user_profile(data: dict):
    log_file_exists = os.path.isfile(USER_PROFILE_LOG_FILE)
    # Opdaterede LOG_HEADERS
    log_headers = [
        "submission_timestamp", "user_session_id", "user_id_input",
        "target_roles_industries_selected", "target_roles_industries_custom",
        "overall_field", # Ny
        "current_skills_selected", "current_skills_custom",
        "education_entries", "total_experience", "work_experience_entries", 
        "job_languages", "job_types", "preferred_locations_dk", # Nye
        "remote_openness", "analysis_preference"
        # "career_goals" er fjernet
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
        st.error(f"Fejl under logning af profil: {e}")
        print(f"ERROR logging profile: {e}")
        return False

# --- Streamlit App UI ---
def run_app():
    st.set_page_config(page_title="Udvidet Karriereprofil", layout="wide")
    st.title("🎯 Udvidet Karriereprofil & Målsætning")
    st.markdown("Definer din detaljerede profil for præcise karriereindsigter.")

    initialize_session_state()

    # --- Indlæs ontologier ---
    default_roles = ["Software Engineer", "Data Scientist", "Project Manager", "UX Designer"]
    default_skills = ["Python", "Java", "SQL", "Data Analysis", "Machine Learning"]
    default_education = [
        ("B.Sc.", "Datalogi", "Københavns Universitet"),
        ("M.Sc.", "Software Engineering", "Aalborg Universitet"),
        ("Cand.merc.", "International Business", "Copenhagen Business School"),
        ("PhD", "Kunstig Intelligens", "Danmarks Tekniske Universitet"),
        ("Datamatiker", "", "Erhvervsakademi Aarhus"),
        ("HA", "", "Syddansk Universitet"),
        ("Cand.polit", "", "Københavns Universitet"),
        ("Master", "Computer Science", "University of Southern Denmark"),
        ("Bachelor", "Economics", "Aarhus University")
    ]
    default_overall_fields = ["Data Science & AI", "Softwareudvikling", "Projektledelse", "UX/UI Design", "Marketing & Salg", "Finans & Økonomi", "Ingeniørvidenskab", "Sundhedssektoren", "International Business"]
    
    roles_options = load_ontology_data(ROLES_INDUSTRIES_ONTOLOGY_FILE, "name", default_roles)
    skills_options = load_ontology_data(SKILL_ONTOLOGY_FILE, "canonical_skill", default_skills)
    education_options = load_ontology_data(EDUCATION_ONTOLOGY_FILE, None, default_education, is_education_ontology=True)
    # For overall_field, kan vi have en simpel liste eller en ontologi hvis det bliver komplekst
    # Vi kan hardcode den for nu eller lave en simpel CSV for den også hvis den skal være dynamisk.

    # --- Sidebar for bruger ID ---
    st.sidebar.header("Brugeridentifikation (Simulering)")
    user_id_input_val = st.sidebar.text_input("Indtast Bruger ID (valgfri):", value=st.session_state.user_id, key="user_id_widget")
    if user_id_input_val != st.session_state.user_id:
        st.session_state.user_id = user_id_input_val
    user_session_id_for_run = st.session_state.user_id if st.session_state.user_id else st.session_state.session_id
    st.sidebar.info(f"ID: `{user_session_id_for_run}`")

    # --- Knapper til at tilføje entries (UDENFOR FORM) ---
    col_add1, col_add2 = st.columns(2)
    with col_add1:
        st.subheader("Uddannelsesafsnit")
        st.button("➕ Tilføj Uddannelse", on_click=add_education_entry_callback, key="add_education_main_btn", use_container_width=True)
    with col_add2:
        st.subheader("Erhvervserfaringsafsnit")
        st.button("➕ Tilføj Arbejdserfaring", on_click=add_experience_entry_callback, key="add_experience_main_btn", use_container_width=True)
    st.markdown("---")

    # --- FORM STARTER HER ---
    with st.form(key="profile_form"):
        st.header("1. Overordnet Profil")
        cols_profil1 = st.columns(2)
        overall_field = cols_profil1[0].selectbox("Primært Fagområde/Industri:", options=default_overall_fields, index=0, help="Vælg det felt der bedst beskriver din generelle profil.")
        
        job_languages_options = ["Dansk", "Engelsk", "Tysk", "Svensk", "Norsk", "Fransk", "Spansk", "Andet"]
        job_languages = cols_profil1[1].multiselect("Foretrukne Jobsprog:", options=job_languages_options, help="Vælg et eller flere sprog du er komfortabel med at arbejde på.")
        
        job_type_options = ["Fuldtid", "Deltid", "Permanent", "Studiejob", "Frivilligt arbejde", "Praktik", "Nyuddannet", "Elev / Lærling", "Tidsbegrænset"]
        job_types = st.multiselect("Ønskede Jobtyper:", options=job_type_options, help="Vælg en eller flere relevante jobtyper.")

        st.header("2. Målroller og Specifikke Industrier")
        target_roles_selected = st.multiselect("Målrolle(r) og/eller Industri(er) (fra liste):", roles_options)
        target_roles_custom = st.text_area("Andre Målroller/Industrier (brugerdefineret, kommasepareret):", height=75)

        st.header("3. Nuværende Færdigheder")
        current_skills_selected = st.multiselect("Dine Færdigheder (fra liste):", skills_options)
        current_skills_custom = st.text_area("Andre Færdigheder (brugerdefineret, kommasepareret):", height=75)

        st.header("4. Uddannelsesbaggrund")
        if not st.session_state.education_entries:
            st.caption("Ingen uddannelser tilføjet. Klik på '➕ Tilføj Uddannelse' ovenfor formularen.")
        for i, edu_entry in enumerate(st.session_state.education_entries):
            with st.container(border=True):
                st.markdown(f"**Uddannelse #{i+1}**")
                edu_cols = st.columns([2,2,2,1,1])
                edu_entry["degree"] = edu_cols[0].selectbox("Grad", options=[""] + education_options.get("degree_name", []), index=0, key=f"edu_degree_{edu_entry['id']}")
                edu_entry["field_of_study"] = edu_cols[1].selectbox("Studieretning", options=[""] + education_options.get("field_of_study_name", []), index=0, key=f"edu_field_{edu_entry['id']}")
                edu_entry["institution"] = edu_cols[2].text_input("Institution", value=edu_entry.get("institution", ""), key=f"edu_institution_{edu_entry['id']}", placeholder="f.eks. Aalborg Universitet") # Kan også være selectbox hvis ontology har institutioner
                edu_entry["graduation_year"] = edu_cols[3].text_input("Dimissionsår", value=edu_entry.get("graduation_year", ""), key=f"edu_year_{edu_entry['id']}")
                edu_entry["marked_for_removal"] = edu_cols[4].checkbox("Fjern", key=f"edu_remove_cb_{edu_entry['id']}")

        st.header("5. Erhvervserfaring")
        total_experience = st.selectbox("Samlet Professionel Erfaring:", options=["Ingen", "0-1 år", "1-3 år", "3-5 år", "5-10 år", "10-15 år", "15+ år"], key="total_exp_select")
        if not st.session_state.experience_entries:
            st.caption("Ingen erfaringer tilføjet. Klik på '➕ Tilføj Arbejdserfaring' ovenfor formularen.")
        for i, exp_entry in enumerate(st.session_state.experience_entries):
            with st.container(border=True):
                st.markdown(f"**Erhvervserfaring #{i+1}**")
                exp_cols_1 = st.columns(2)
                exp_entry["job_title"] = exp_cols_1[0].text_input("Jobtitel", value=exp_entry.get("job_title", ""), key=f"exp_title_{exp_entry['id']}")
                exp_entry["company"] = exp_cols_1[1].text_input("Virksomhed", value=exp_entry.get("company", ""), key=f"exp_company_{exp_entry['id']}")
                exp_cols_2 = st.columns([1,3,1])
                exp_entry["years_in_role"] = exp_cols_2[0].number_input("År i rollen", min_value=0, max_value=50, step=1, value=int(exp_entry.get("years_in_role", 0)), key=f"exp_years_{exp_entry['id']}")
                exp_entry["skills_responsibilities"] = exp_cols_2[1].text_area("Nøglefærdigheder/Ansvarsområder (kommasepareret)", value=exp_entry.get("skills_responsibilities", ""), key=f"exp_skills_{exp_entry['id']}", height=75)
                exp_entry["marked_for_removal"] = exp_cols_2[2].checkbox("Fjern", key=f"exp_remove_cb_{exp_entry['id']}", help="Markér for fjernelse")

        st.header("6. Lokations- og Analysepræferencer")
        location_options_dk = [
            "Hele Danmark", "Storkøbenhavn", "Aarhus Området", "Odense Området", "Aalborg Området", 
            "Trekantområdet (Vejle, Kolding, Fredericia)", "Sjælland (udenfor Storkøbenhavn)", 
            "Fyn (udenfor Odense)", "Nordjylland (udenfor Aalborg)", "Midtjylland (udenfor Aarhus)", 
            "Sønderjylland", "Vestjylland", "Bornholm"
        ]
        preferred_locations_dk = st.multiselect("Foretrukne Joblokationer i Danmark:", options=location_options_dk)
        remote_options = ["Ligeglad", "Primært På Stedet", "Primært Hybrid", "Primært Remote"]
        remote_openness = st.selectbox("Åbenhed for Remote Arbejde:", options=remote_options, key="remote_select")
        analysis_options = ["Hurtig scanning (vejledende)", "Dybdegående Analyse (omfattende)"]
        analysis_preference = st.selectbox("Analysepræference:", options=analysis_options, index=1, key="analysis_select")

        st.markdown("&nbsp;")
        submitted = st.form_submit_button("🚀 Gem Profil og Fortsæt")

    # --- Håndtering af formularindsendelse ---
    if submitted:
        # Trin 1: Behandl fjernelser
        education_removed_flag = False
        if any(edu.get("marked_for_removal") for edu in st.session_state.education_entries):
            st.session_state.education_entries = [edu for edu in st.session_state.education_entries if not edu.get("marked_for_removal")]
            education_removed_flag = True
        
        experience_removed_flag = False
        if any(exp.get("marked_for_removal") for exp in st.session_state.experience_entries):
            st.session_state.experience_entries = [exp for exp in st.session_state.experience_entries if not exp.get("marked_for_removal")]
            experience_removed_flag = True

        if education_removed_flag or experience_removed_flag:
            st.toast("Markeret(e) post(er) er fjernet. Gennemse og indsend formularen igen.", icon="♻️")
            st.rerun()

        # Trin 2: Validering
        validation_passed = True
        if not target_roles_selected and not target_roles_custom.strip():
            st.error("Angiv mindst én målrolle/industri."); validation_passed = False
        if not current_skills_selected and not current_skills_custom.strip():
            st.error("Angiv mindst én nuværende færdighed."); validation_passed = False
        if not overall_field:
            st.error("Vælg venligst et primært fagområde."); validation_passed = False
        if not job_languages:
            st.error("Vælg venligst mindst ét foretrukket jobsprog."); validation_passed = False
        if not job_types:
            st.error("Vælg venligst mindst én ønsket jobtype."); validation_passed = False
        if not preferred_locations_dk:
            st.error("Vælg venligst mindst én foretrukken joblokation i Danmark."); validation_passed = False

        for edu_entry in st.session_state.education_entries:
            if not edu_entry["degree"].strip() or not edu_entry["field_of_study"].strip() or not edu_entry["institution"].strip():
                st.error("Udfyld Grad, Studieretning og Institution for alle uddannelser."); validation_passed = False; break
        
        for exp_entry in st.session_state.experience_entries:
            if not exp_entry["job_title"].strip() or not exp_entry["company"].strip():
                st.error("Udfyld Jobtitel og Virksomhed for alle erfaringer."); validation_passed = False; break
        
        if validation_passed:
            profile_data = {
                "submission_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user_session_id": user_session_id_for_run,
                "user_id_input": st.session_state.user_id,
                "target_roles_industries_selected": target_roles_selected,
                "target_roles_industries_custom": [r.strip() for r in target_roles_custom.split(',') if r.strip()],
                "overall_field": overall_field,
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
                st.success("✅ Profil er gemt og logget succesfuldt!")
                st.balloons()
                st.subheader("Indsamlede Profildata:")
                st.json(profile_data)
                st.caption(f"Data er blevet tilføjet til `{USER_PROFILE_LOG_FILE}`.")
            else:
                st.error("Fejl under logning af profil.")
        else:
            st.warning("Gennemgå venligst formularen for fejl.")

if __name__ == "__main__":
    run_app() 