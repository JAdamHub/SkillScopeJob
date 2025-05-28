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
        logger.warning(f"Taksonomifil {TAXONOMY_PATH} ikke fundet. Opretter en udvidet dummy-fil for test.")
        # Udvidet dummy taksonomi data
        dummy_taxonomy_data = {
            'variation': [
                # Programmeringssprog
                'python', 'python programming', 'py', 'java', 'javascript', 'js', 'typescript', 'ts',
                'c#', 'c sharp', 'c++', 'cpp', 'php', 'ruby', 'ruby on rails', 'rails', 'golang', 'go language', 'swift', 'kotlin',
                'scala', 'r language', 'r programming', 'matlab', 'perl', 'powershell', 'bash', 'shell scripting', 'sql', 'structured query language',
                'pl/sql', 'tsql', 't-sql',
                # Web Teknologier & Frameworks (Frontend)
                'html', 'html5', 'css', 'css3', 'sass', 'scss', 'less',
                'react', 'react.js', 'reactjs', 'angular', 'angular.js', 'angularjs', 'vue', 'vue.js', 'vuejs',
                'jquery', 'bootstrap', 'tailwind css', 'redux', 'mobx', 'next.js', 'nuxtjs', 'gatsby',
                # Web Teknologier & Frameworks (Backend)
                'node.js', 'nodejs', 'express.js', 'django', 'flask', 'spring', 'spring boot', 'asp.net', 'asp.net core',
                '.net core', 'laravel', 'symfony', 'fastapi',
                # Databaser & Databehandling
                'mysql', 'postgresql', 'postgres', 'microsoft sql server', 'ms sql', 'oracle db', 'mongodb', 'nosql',
                'redis', 'elasticsearch', 'cassandra', 'sqlite', 'big data', 'hadoop', 'spark', 'apache spark', 'kafka', 'apache kafka',
                'data warehousing', 'etl', 'data pipelines', 'data modeling', 'pandas', 'numpy', 'scipy', 'data analysis',
                # Cloud & DevOps
                'aws', 'amazon web services', 'azure', 'microsoft azure', 'gcp', 'google cloud platform', 'docker', 'kubernetes', 'k8s',
                'terraform', 'ansible', 'jenkins', 'git', 'github', 'gitlab', 'ci/cd', 'continuous integration', 'continuous deployment',
                'serverless', 'aws lambda', 'azure functions', 'google cloud functions', 'microservices', 'infrastructure as code', 'iac',
                # AI & Machine Learning
                'machine learning', 'ml', 'deep learning', 'dl', 'artificial intelligence', 'ai', 'natural language processing', 'nlp',
                'computer vision', 'tensorflow', 'keras', 'pytorch', 'scikit-learn', 'reinforcement learning', 'neural networks',
                'data science', 'statistical analysis', 'data visualization', 'tableau', 'power bi',
                # Mobiludvikling
                'ios development', 'android development', 'swiftui', 'objective-c', 'react native', 'flutter', 'xamarin',
                # Test & QA
                'software testing', 'qa', 'quality assurance', 'selenium', 'junit', 'pytest', 'jest', 'cypress', 'test automation',
                # Projektledelse & Metoder
                'project management', 'project mgmt', 'agile', 'agile methodologies', 'scrum', 'kanban', 'lean',
                'product management', 'stakeholder management', 'risk management', 'jira', 'confluence',
                # Forretningsanalyse & Design
                'business analysis', 'requirements gathering', 'use cases', 'user stories', 'uml', 'system design',
                'ui design', 'user interface design', 'ux design', 'user experience design', 'figma', 'adobe xd', 'sketch',
                # Operativsystemer & Netværk
                'linux', 'unix', 'windows server', 'macos', 'networking', 'tcp/ip', 'dns', 'http', 'rest apis', 'graphql',
                # Cybersikkerhed
                'cybersecurity', 'information security', 'network security', 'penetration testing', 'siem', 'encryption',
                # Bløde færdigheder (eksempler)
                'communication', 'teamwork', 'problem-solving', 'analytical skills', 'critical thinking', 'leadership',
                'collaboration', 'creativity', 'adaptability', 'time management', 'attention to detail'
            ],
            'canonical_skill': [
                # Programmeringssprog
                'Python', 'Python', 'Python', 'Java', 'JavaScript', 'JavaScript', 'TypeScript', 'TypeScript',
                'C#', 'C#', 'C++', 'C++', 'PHP', 'Ruby', 'Ruby on Rails', 'Ruby on Rails', 'Go', 'Go', 'Swift', 'Kotlin',
                'Scala', 'R', 'R', 'MATLAB', 'Perl', 'PowerShell', 'Bash', 'Shell Scripting', 'SQL', 'SQL',
                'PL/SQL', 'T-SQL', 'T-SQL',
                # Web Teknologier & Frameworks (Frontend)
                'HTML', 'HTML5', 'CSS', 'CSS3', 'Sass', 'SCSS', 'LESS',
                'React', 'React', 'React', 'Angular', 'Angular', 'Angular', 'Vue.js', 'Vue.js', 'Vue.js',
                'jQuery', 'Bootstrap', 'Tailwind CSS', 'Redux', 'MobX', 'Next.js', 'Nuxt.js', 'Gatsby',
                # Web Teknologier & Frameworks (Backend)
                'Node.js', 'Node.js', 'Express.js', 'Django', 'Flask', 'Spring Framework', 'Spring Boot', 'ASP.NET', 'ASP.NET Core',
                '.NET Core', 'Laravel', 'Symfony', 'FastAPI',
                # Databaser & Databehandling
                'MySQL', 'PostgreSQL', 'PostgreSQL', 'Microsoft SQL Server', 'Microsoft SQL Server', 'Oracle Database', 'MongoDB', 'NoSQL Databases',
                'Redis', 'Elasticsearch', 'Apache Cassandra', 'SQLite', 'Big Data', 'Apache Hadoop', 'Apache Spark', 'Apache Spark', 'Apache Kafka', 'Apache Kafka',
                'Data Warehousing', 'ETL Development', 'Data Pipelines', 'Data Modeling', 'Pandas', 'NumPy', 'SciPy', 'Data Analysis',
                # Cloud & DevOps
                'AWS', 'AWS', 'Microsoft Azure', 'Microsoft Azure', 'Google Cloud Platform', 'Google Cloud Platform', 'Docker', 'Kubernetes', 'Kubernetes',
                'Terraform', 'Ansible', 'Jenkins', 'Git', 'GitHub', 'GitLab', 'CI/CD', 'Continuous Integration', 'Continuous Deployment',
                'Serverless Architecture', 'AWS Lambda', 'Azure Functions', 'Google Cloud Functions', 'Microservices Architecture', 'Infrastructure as Code (IaC)', 'Infrastructure as Code (IaC)',
                # AI & Machine Learning
                'Machine Learning', 'Machine Learning', 'Deep Learning', 'Deep Learning', 'Artificial Intelligence', 'Artificial Intelligence', 'Natural Language Processing (NLP)', 'Natural Language Processing (NLP)',
                'Computer Vision', 'TensorFlow', 'Keras', 'PyTorch', 'Scikit-learn', 'Reinforcement Learning', 'Neural Networks',
                'Data Science', 'Statistical Analysis', 'Data Visualization', 'Tableau', 'Microsoft Power BI',
                # Mobiludvikling
                'iOS Development', 'Android Development', 'SwiftUI', 'Objective-C', 'React Native', 'Flutter', 'Xamarin',
                # Test & QA
                'Software Testing', 'Quality Assurance (QA)', 'Quality Assurance (QA)', 'Selenium', 'JUnit', 'PyTest', 'Jest', 'Cypress', 'Test Automation',
                # Projektledelse & Metoder
                'Project Management', 'Project Management', 'Agile Methodologies', 'Agile Methodologies', 'Scrum', 'Kanban', 'Lean Methodologies',
                'Product Management', 'Stakeholder Management', 'Risk Management', 'Jira', 'Confluence',
                # Forretningsanalyse & Design
                'Business Analysis', 'Requirements Gathering', 'Use Case Development', 'User Story Mapping', 'UML', 'System Design',
                'UI Design', 'User Interface (UI) Design', 'UX Design', 'User Experience (UX) Design', 'Figma', 'Adobe XD', 'Sketch',
                # Operativsystemer & Netværk
                'Linux', 'Unix', 'Windows Server', 'macOS', 'Network Administration', 'TCP/IP', 'DNS Management', 'HTTP', 'REST APIs', 'GraphQL',
                # Cybersikkerhed
                'Cybersecurity', 'Information Security', 'Network Security', 'Penetration Testing', 'SIEM Solutions', 'Encryption Technologies',
                # Bløde færdigheder (eksempler)
                'Communication Skills', 'Teamwork', 'Problem-Solving Skills', 'Analytical Skills', 'Critical Thinking', 'Leadership Skills',
                'Collaboration Skills', 'Creativity', 'Adaptability', 'Time Management', 'Attention to Detail'
            ],
            # 'category' kolonnen er bevidst holdt simpel her, kan udvides efter behov
            'category': [
                'Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language',
                'Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Programming Language','Scripting','Scripting','Scripting','Database','Database',
                'Database','Database','Database',
                'Web Technology','Web Technology','Web Technology','Web Technology','CSS Preprocessor','CSS Preprocessor','CSS Preprocessor',
                'JavaScript Framework','JavaScript Framework','JavaScript Framework','JavaScript Framework','JavaScript Framework','JavaScript Framework','JavaScript Framework','JavaScript Framework','JavaScript Framework',
                'JavaScript Library','CSS Framework','CSS Framework','State Management','State Management','JavaScript Framework','JavaScript Framework','Static Site Generator',
                'Web Framework','Web Framework','Web Framework','Web Framework','Web Framework','Web Framework','Web Framework','Web Framework','Web Framework',
                '.NET Framework','Web Framework','Web Framework','Web Framework',
                'Database','Database','Database','Database','Database','Database','Database','Database',
                'Database Cache','Search Engine','Database','Database','Big Data Technology','Big Data Technology','Big Data Technology','Big Data Technology','Messaging System','Messaging System',
                'Data Storage','Data Processing','Data Engineering','Data Modeling','Data Analysis Library','Data Analysis Library','Data Analysis Library','Data Analysis',
                'Cloud Platform','Cloud Platform','Cloud Platform','Cloud Platform','Cloud Platform','Cloud Platform','Containerization','Orchestration','Orchestration',
                'IaC Tool','Configuration Management','CI/CD Tool','Version Control','Version Control Platform','Version Control Platform','DevOps Practice','DevOps Practice','DevOps Practice',
                'Cloud Computing Model','Serverless Platform','Serverless Platform','Serverless Platform','Software Architecture','DevOps Practice','DevOps Practice',
                'AI/ML','AI/ML','AI/ML','AI/ML','AI/ML','AI/ML','AI/ML','AI/ML',
                'AI/ML','AI/ML Framework','AI/ML Framework','AI/ML Framework','AI/ML Library','AI/ML','AI/ML',
                'Data Science','Statistical Method','Data Visualization','BI Tool','BI Tool',
                'Mobile Development','Mobile Development','Mobile UI Framework','Programming Language','Mobile Framework','Mobile Framework','Mobile Framework',
                'Software Development Practice','Software Development Practice','Software Development Practice','Testing Tool','Testing Framework','Testing Framework','Testing Framework','Testing Tool','Software Development Practice',
                'Methodology','Methodology','Methodology','Methodology','Methodology','Methodology','Methodology',
                'Role/Discipline','Project Management Skill','Project Management Skill','Project Management Tool','Project Management Tool',
                'Role/Discipline','Business Analysis Skill','Business Analysis Skill','Business Analysis Skill','Modeling Language','Software Development Practice',
                'Design Skill','Design Skill','Design Skill','Design Skill','Design Tool','Design Tool','Design Tool',
                'Operating System','Operating System','Operating System','Operating System','IT Skill','Networking Protocol','Networking Service','Networking Protocol','API Style','API Style',
                'Security Domain','Security Domain','Security Domain','Security Practice','Security Tool','Security Technology',
                'Soft Skill','Soft Skill','Soft Skill','Soft Skill','Soft Skill','Soft Skill',
                'Soft Skill','Soft Skill','Soft Skill','Soft Skill','Soft Skill'
            ]
        }
        # Sikrer at alle lister har samme længde for DataFrame konvertering
        # Dette er en simpel måde at gøre det på for dummy data.
        max_len = max(len(dummy_taxonomy_data['variation']), len(dummy_taxonomy_data['canonical_skill']), len(dummy_taxonomy_data['category']))
        for key in dummy_taxonomy_data:
            dummy_taxonomy_data[key].extend([None] * (max_len - len(dummy_taxonomy_data[key])))

        pd.DataFrame(dummy_taxonomy_data).to_csv(TAXONOMY_PATH, index=False)
        logger.info(f"Udvidet dummy taksonomifil {TAXONOMY_PATH} oprettet med eksempeldata.")
        
    main() 