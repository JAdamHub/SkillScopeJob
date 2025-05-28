import sqlite3
import pandas as pd
import spacy
from spacy.matcher import PhraseMatcher
from collections import Counter
import json
from pathlib import Path
from loguru import logger
import csv
import itertools
import sys

# --- Konstanter ---
DB_PATH = Path("job_postings.db")
TAXONOMY_PATH = Path("skill_taxonomy.csv")
SPACY_MODEL_NAME = "en_core_web_lg" # Specificerer spaCy modellen
POTENTIAL_SKILLS_LOG_PATH = Path("potential_new_skills_log.csv")
RUN_LOG_PATH = Path("run_log.txt")
TREND_REPORT_PATH = Path("skill_trend_report.json")
TOP_N_SKILLS = 20 # Antal top-færdigheder at inkludere i rapporten

# --- Opsætning af Logging ---
def setup_logging():
    """Konfigurerer Loguru logger til både konsol og fil.
"""
    logger.remove()  # Fjern standardhandler
    logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
    logger.add(RUN_LOG_PATH, level="INFO", rotation="1 MB", # Roter logfilen når den når 1MB
               format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module}:{function}:{line} - {message}")
    logger.info("Logging initialiseret.")
    logger.info(f"Gemmer detaljeret log til: {RUN_LOG_PATH.resolve()}")

# --- Trin 3 Funktioner: Pålidelig Færdighedsidentifikation ---

def load_job_postings(db_path: Path) -> pd.DataFrame:
    """Indlæser jobopslag (ID og beskrivelse) fra SQLite databasen.
"""
    logger.info(f"Indlæser jobopslag fra databasen: {db_path}")
    if not db_path.exists():
        logger.error(f"Databasefil ikke fundet: {db_path}")
        raise FileNotFoundError(f"Databasefil ikke fundet: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        # Indlæs kun id og description for effektivitet (ændret fra ID til id)
        query = "SELECT id, description FROM job_postings WHERE description IS NOT NULL AND description != ''"
        df = pd.read_sql_query(query, conn)
        conn.close()
        logger.success(f"Indlæst {len(df)} jobopslag fra '{db_path}'. Kolonner: {df.columns.tolist()}")
        if 'id' not in df.columns or 'description' not in df.columns:
            logger.error("Database tabel mangler påkrævede kolonner 'id' eller 'description'.")
            raise ValueError("Database tabel mangler påkrævede kolonner 'id' eller 'description'.")
        return df
    except sqlite3.Error as e:
        logger.error(f"Databasefejl under indlæsning af jobopslag: {e}")
        raise
    except Exception as e:
        logger.error(f"Uventet fejl under indlæsning af jobopslag: {e}")
        raise

def load_skill_taxonomy(taxonomy_path: Path) -> dict[str, str]:
    """Indlæser færdighedstaksonomien fra en CSV-fil.
    Returnerer en dictionary: {lowercase_variation: canonical_skill}.
    """
    logger.info(f"Indlæser færdighedstaksonomi fra: {taxonomy_path}")
    if not taxonomy_path.exists():
        logger.error(f"Taksonomifil ikke fundet: {taxonomy_path}")
        raise FileNotFoundError(f"Taksonomifil ikke fundet: {taxonomy_path}")
    try:
        df_taxonomy = pd.read_csv(taxonomy_path)
        if "variation" not in df_taxonomy.columns or "canonical_skill" not in df_taxonomy.columns:
            logger.error("Taksonomifil mangler påkrævede kolonner 'variation' eller 'canonical_skill'.")
            raise ValueError("Taksonomifil mangler påkrævede kolonner 'variation' eller 'canonical_skill'.")

        taxonomy_map = {}
        for _, row in df_taxonomy.iterrows():
            variation = str(row["variation"]).lower().strip()
            canonical = str(row["canonical_skill"]).strip()
            if variation and canonical: # Spring over tomme rækker
                 taxonomy_map[variation] = canonical
        logger.success(f"Indlæst {len(taxonomy_map)} unikke færdighedsvariationer fra taksonomien.")
        return taxonomy_map
    except Exception as e:
        logger.error(f"Fejl under indlæsning af færdighedstaksonomi: {e}")
        raise

def initialize_nlp_model(model_name: str = SPACY_MODEL_NAME):
    """Initialiserer og returnerer en spaCy NLP-model.
"""
    logger.info(f"Initialiserer spaCy NLP-model: {model_name}")
    try:
        nlp = spacy.load(model_name)
        model_version = spacy.__version__ + " (model: " + nlp.meta['name'] + " v" + nlp.meta['version'] + ")"
        logger.success(f"spaCy model '{model_name}' version '{model_version}' indlæst succesfuldt.")
        # Log MLOps information
        logger.info(f"MLOps: Anvender spaCy model: {model_name}, Version: {model_version}")
        return nlp
    except OSError:
        logger.error(f"spaCy model '{model_name}' ikke fundet. Har du downloadet den? "
                     f"Kør: python -m spacy download {model_name}")
        raise
    except Exception as e:
        logger.error(f"Fejl under initialisering af spaCy model: {e}")
        raise

def build_phrase_matcher(nlp, taxonomy_map: dict[str, str]) -> PhraseMatcher:
    """Bygger en spaCy PhraseMatcher baseret på færdighedstaksonomien."""
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    for variation_lower, canonical_skill in taxonomy_map.items():
        # Vi bruger canonical_skill som ID for reglen, så vi kan hente den direkte.
        # spaCy kræver at ID'et (match_id) er et hash (int). Vi gemmer canonical skill direkte.
        matcher.add(canonical_skill, [nlp(variation_lower)])
    logger.info(f"PhraseMatcher bygget med {len(taxonomy_map)} mønstre.")
    return matcher

def extract_skills_for_job(
    job_id: int,
    description_text: str,
    phrase_matcher: PhraseMatcher,
    taxonomy_map_lower_to_canonical: dict[str, str], # Bruges til NER check
    nlp_model, # spaCy nlp object
    log_potential_skill_func # funktion til at logge potentielle færdigheder
) -> list[str]:
    """Ekstraherer færdigheder fra en enkelt jobbeskrivelse.
"""
    if not isinstance(description_text, str) or not description_text.strip():
        return [] # Returner tom liste for tomme beskrivelser

    doc = nlp_model(description_text)
    extracted_canonical_skills = set()

    # 1. Primær færdighedsekstraktion (via PhraseMatcher)
    matches = phrase_matcher(doc)
    for match_id_hash, start, end in matches:
        # match_id_hash er hashen af det `canonical_skill` navn vi brugte da vi tilføjede reglen
        canonical_skill_name = nlp_model.vocab.strings[match_id_hash]
        extracted_canonical_skills.add(canonical_skill_name)

    # 2. Sekundær færdighedsopdagelse (via NER)
    # Entiteter der KUNNE være færdigheder: ORG, PRODUCT, WORK_OF_ART, MISC.
    # NORP (nationalities, political groups) og LOC (locations) kan også være relevante for visse færdigheder.
    relevant_ner_labels = {"ORG", "PRODUCT", "WORK_OF_ART", "MISC", "NORP", "LOC", "LANGUAGE"}

    for ent in doc.ents:
        entity_text_lower = ent.text.lower().strip()
        # Overvej kun relevante entitetstyper OG hvis teksten ikke er triviel
        if ent.label_ in relevant_ner_labels and len(entity_text_lower) > 1:
            # Tjek om entiteten allerede er dækket af taksonomien
            # Dvs. er entitetens tekst en kendt variation?
            if entity_text_lower not in taxonomy_map_lower_to_canonical:
                # Yderligere tjek: er entiteten (eller dens kanoniske form, hvis den havde en) allerede fundet?
                # For MVP er det nok at logge, hvis den ikke er direkte i taksonomien.
                # Vi vil undgå at logge dele af allerede matchede, længere færdigheder,
                # men PhraseMatcher håndterer typisk det længste match.
                log_potential_skill_func(job_id, ent.text, ent.sent.text)

    return sorted(list(extracted_canonical_skills))

def process_all_jobs_for_skills(
    job_data: pd.DataFrame, # Indeholder 'ID' og 'description'
    taxonomy_map_lower_to_canonical: dict[str, str],
    nlp_model
) -> list[dict]:
    """Behandler alle jobopslag for at ekstrahere færdigheder.
    Returnerer en liste af dicts: [{'ID': job_id, 'canonical_skills': [...]}]
    """
    logger.info(f"Starter færdighedsekstraktion for {len(job_data)} jobbeskrivelser...")

    # Byg PhraseMatcher én gang
    phrase_matcher = build_phrase_matcher(nlp_model, taxonomy_map_lower_to_canonical)

    jobs_with_extracted_skills = []
    
    # Opsætning af CSV-logger for potentielle nye færdigheder
    log_fieldnames = ["job_id", "potential_skill_entity", "context_sentence"]
    # Tjek om filen er tom for at skrive headers kun én gang
    file_exists_and_not_empty = POTENTIAL_SKILLS_LOG_PATH.exists() and POTENTIAL_SKILLS_LOG_PATH.stat().st_size > 0
    
    try:
        with open(POTENTIAL_SKILLS_LOG_PATH, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=log_fieldnames)
            if not file_exists_and_not_empty:
                writer.writeheader()
                logger.info(f"Oprettet logfil for potentielle nye færdigheder: {POTENTIAL_SKILLS_LOG_PATH}")

            def _log_potential_skill_to_csv(current_job_id, entity_text, context_sentence):
                writer.writerow({
                    "job_id": current_job_id,
                    "potential_skill_entity": entity_text,
                    "context_sentence": context_sentence.replace('\n', ' ').strip() # Rens kontekst lidt
                })

            for index, row in job_data.iterrows():
                job_id = row['id']
                description = row['description']
                
                if pd.isna(description) or not str(description).strip():
                    extracted_skills = []
                else:
                    extracted_skills = extract_skills_for_job(
                        job_id,
                        str(description),
                        phrase_matcher,
                        taxonomy_map_lower_to_canonical,
                        nlp_model,
                        _log_potential_skill_to_csv
                    )
                
                jobs_with_extracted_skills.append({
                    'ID': job_id,
                    'canonical_skills': extracted_skills
                })
                if (index + 1) % 100 == 0: # Log fremgang
                    logger.info(f"Behandlet {index + 1}/{len(job_data)} jobopslag...")
        
        logger.success(f"Færdighedsekstraktion fuldført for {len(job_data)} jobopslag.")
        logger.info(f"Potentielle nye færdigheder logget til: {POTENTIAL_SKILLS_LOG_PATH.resolve()}")
        return jobs_with_extracted_skills

    except Exception as e:
        logger.error(f"Fejl under behandling af job for færdigheder: {e}")
        # Prøv at lukke filen hvis den er åben, selvom det er usandsynligt her pga. 'with'
        raise


# --- Trin 4 Funktioner: Analyse af Færdighedstendenser ---

def analyze_skill_trends(
    jobs_with_skills_list: list[dict], # [{'ID': job_id, 'canonical_skills': [...]}]
    top_n: int = TOP_N_SKILLS
) -> dict:
    """Analyserer færdighedsfrekvenser og co-occurrence.
"""
    logger.info("Starter analyse af færdighedstendenser...")
    total_jobs_processed = len(jobs_with_skills_list)
    if total_jobs_processed == 0:
        logger.warning("Ingen jobdata med færdigheder at analysere.")
        return {
            "metadata": {"total_job_postings_processed": 0, "total_unique_canonical_skills": 0},
            "all_skill_frequencies": [], "top_n_skills": [], "skill_cooccurrence_counts": []
        }

    all_skills_flat_list = []
    for job_entry in jobs_with_skills_list:
        all_skills_flat_list.extend(job_entry['canonical_skills'])
    
    skill_frequencies = Counter(all_skills_flat_list)
    total_unique_skills = len(skill_frequencies)
    logger.info(f"MLOps: Total antal jobbeskrivelser behandlet: {total_jobs_processed}")
    logger.info(f"MLOps: Total antal unikke kanoniske færdigheder identificeret: {total_unique_skills}")

    # Formater 'all_skill_frequencies' som liste af dicts
    formatted_skill_frequencies = [{"skill": skill, "frequency": freq} for skill, freq in skill_frequencies.most_common()]

    # Top N færdigheder
    top_n_skills_list = []
    for skill, freq in skill_frequencies.most_common(top_n):
        percentage = (freq / total_jobs_processed) * 100 if total_jobs_processed > 0 else 0
        top_n_skills_list.append({"skill": skill, "frequency": freq, "percentage": round(percentage, 2)})

    logger.info(f"MLOps: Top 5 mest efterspurgte færdigheder:")
    for i, item in enumerate(top_n_skills_list[:5]):
        logger.info(f"  {i+1}. {item['skill']}: {item['frequency']} jobs ({item['percentage']}%)")

    # Færdigheds co-occurrence
    co_occurrence_counter = Counter()
    for job_entry in jobs_with_skills_list:
        skills_in_job = sorted(list(set(job_entry['canonical_skills']))) # Unikke, sorterede færdigheder pr. job
        if len(skills_in_job) >= 2:
            for pair in itertools.combinations(skills_in_job, 2):
                co_occurrence_counter[pair] += 1
    
    formatted_cooccurrence = [{"pair": list(pair), "count": count} for pair, count in co_occurrence_counter.most_common()]

    trend_data = {
        "metadata": {
            "total_job_postings_processed": total_jobs_processed,
            "total_unique_canonical_skills": total_unique_skills,
            "top_n_count": top_n
        },
        "all_skill_frequencies": formatted_skill_frequencies,
        "top_n_skills": top_n_skills_list,
        "skill_cooccurrence_counts": formatted_cooccurrence
    }
    logger.success("Analyse af færdighedstendenser fuldført.")
    return trend_data

def save_trend_report(trend_data: dict, report_path: Path):
    """Gemmer trendrapporten som en JSON-fil.
"""
    logger.info(f"Gemmer færdighedstrendrapport til: {report_path}")
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(trend_data, f, indent=4, ensure_ascii=False)
        logger.success(f"Trendrapport gemt succesfuldt: {report_path.resolve()}")
    except Exception as e:
        logger.error(f"Fejl under gemning af trendrapport: {e}")
        raise

# --- Main Orchestration ---
def main():
    """Hovedfunktion til at orkestrere hele pipeline.
"""
    setup_logging()
    logger.info("Starter Job Market Skill Demand Analysis pipeline...")

    try:
        # Trin 3a: Indlæs jobopslag
        job_postings_df = load_job_postings(DB_PATH)
        if job_postings_df.empty:
            logger.warning("Ingen jobopslag indlæst. Afslutter pipeline.")
            return

        # Trin 3b: Indlæs færdighedstaksonomi
        # Log MLOps information om taksonomifilen
        logger.info(f"MLOps: Anvender færdighedstaksonomi fra: {TAXONOMY_PATH.resolve()}")
        skill_taxonomy_map = load_skill_taxonomy(TAXONOMY_PATH)
        if not skill_taxonomy_map:
            logger.warning("Færdighedstaksonomi er tom. Resultater kan være begrænsede.")
            # Fortsæt evt. kun med NER-baseret, men for nu afslutter vi hvis den er kritisk
            # For MVP antager vi, at taksonomien er central.
            # return # Eller fortsæt, hvis det er meningsfuldt

        # Trin 3c: Initialiser NLP-model (MLOps logging sker inde i funktionen)
        nlp = initialize_nlp_model(SPACY_MODEL_NAME)

        # Trin 3d & 3e: Behandl alle job for færdigheder
        # (MLOps logning af potentielle nye færdigheder sker inde i process_all_jobs_for_skills)
        jobs_with_skills = process_all_jobs_for_skills(job_postings_df, skill_taxonomy_map, nlp)

        if not jobs_with_skills:
            logger.warning("Ingen færdigheder blev ekstraheret fra jobopslagene. Tjek data og taksonomi.")
            # Overvej om rapport stadig skal genereres (den vil være tom)
        
        # Trin 4: Analyser færdighedstendenser
        # (MLOps logning af aggregerede statistikker sker inde i analyze_skill_trends)
        trend_analysis_data = analyze_skill_trends(jobs_with_skills, top_n=TOP_N_SKILLS)

        # Trin 4d: Gem trendrapport
        save_trend_report(trend_analysis_data, TREND_REPORT_PATH)

        logger.success("Job Market Skill Demand Analysis pipeline fuldført succesfuldt!")

    except FileNotFoundError as e:
        logger.critical(f"Kritisk fil ikke fundet: {e}. Afslutter.")
    except ValueError as e:
        logger.critical(f"Dataproblem: {e}. Afslutter.")
    except Exception as e:
        logger.critical(f"En uventet kritisk fejl opstod i main pipeline: {e}", exc_info=True)
    finally:
        logger.info("Pipeline afslutning.")


if __name__ == "__main__":
    # Opret dummy filer hvis de ikke eksisterer, for at scriptet kan køre uden fejl ved første kørsel
    # Dette er kun til test/demo formål. I en produktionssetting skal filerne være korrekte.
    if not DB_PATH.exists():
        logger.warning(f"Database {DB_PATH} ikke fundet. Opretter en tom dummy-database for test.")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_postings (
                ID INTEGER PRIMARY KEY,
                job_title TEXT,
                company TEXT,
                location TEXT,
                date_posted TEXT,
                employment_type TEXT,
                description TEXT,
                source_url TEXT,
                scraped_timestamp TEXT
            )
        ''')
        # Tilføj et par dummy jobopslag
        dummy_jobs = [
            (1, "Python Developer", "Tech Inc.", "Copenhagen", "2023-01-01", "Full-time", "We need a Python expert with experience in Django and SQL. Knowledge of JavaScript is a plus.", "url1", "ts1"),
            (2, "Data Scientist", "Data Corp.", "Aarhus", "2023-01-02", "Full-time", "Seeking a Data Scientist skilled in machine learning, Python, and R. Experience with big data technologies like Spark required.", "url2", "ts2"),
            (3, "Project Manager", "Biz Solutions", "Odense", "2023-01-03", "Contract", "Experienced Project Manager needed for IT projects. Must know agile methodologies and project mgmt software.", "url3", "ts3"),
            (4, "Frontend Developer", "Web Works", "Copenhagen", "2023-01-04", "Full-time", "JavaScript and React expert wanted. HTML, CSS, and git are essential. Angular is a big plus.", "url4", "ts4"),
            (5, "Java Developer", "Enterprise Ltd.", "Aalborg", "2023-01-05", "Full-time", "Backend Java developer with Spring Boot experience. We also use SQL and microservices.", "url5", "ts5")
        ]
        cursor.executemany("INSERT INTO job_postings VALUES (?,?,?,?,?,?,?,?,?)", dummy_jobs)
        conn.commit()
        conn.close()
        logger.info(f"Dummy database {DB_PATH} oprettet med eksempeldata.")

    if not TAXONOMY_PATH.exists():
        logger.warning(f"Taksonomifil {TAXONOMY_PATH} ikke fundet. Opretter en dummy-fil for test.")
        dummy_taxonomy_data = {
            'variation': ['python', 'python programming', 'sql', 'structured query language', 'javascript', 'js', 
                          'project mgmt', 'project management', 'machine learning', 'ml', 'java', 'spring boot',
                          'react', 'angular', 'django', 'agile methodologies', 'git', 'css', 'html', 'big data', 'spark', 'r'],
            'canonical_skill': ['Python', 'Python', 'SQL', 'SQL', 'JavaScript', 'JavaScript', 
                                'Project Management', 'Project Management', 'Machine Learning', 'Machine Learning', 'Java', 'Spring Boot',
                                'React', 'Angular', 'Django', 'Agile Methodologies', 'Git', 'CSS', 'HTML', 'Big Data', 'Spark', 'R'],
            'category': ['Programming Language', 'Programming Language', 'Database', 'Database', 'Programming Language', 'Programming Language',
                         'Methodology', 'Methodology', 'AI/ML', 'AI/ML', 'Programming Language', 'Framework',
                         'Framework', 'Framework', 'Framework', 'Methodology', 'Tool', 'Web Technology', 'Web Technology', 'Technology', 'Tool', 'Programming Language']
        }
        pd.DataFrame(dummy_taxonomy_data).to_csv(TAXONOMY_PATH, index=False)
        logger.info(f"Dummy taksonomifil {TAXONOMY_PATH} oprettet med eksempeldata.")
        
    main() 