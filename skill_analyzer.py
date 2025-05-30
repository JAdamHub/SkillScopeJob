import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional
import spacy
from spacy.matcher import PhraseMatcher
from together import Together
from datetime import datetime
import time
import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
import aiofiles

# Konstanter og konfiguration
DB_PATH = Path("indeed_jobs.db")
SKILLS_FILE = Path("skills.txt")
LOG_FILE = Path("skill_analyzer.log")
OUTPUT_DIR = Path("output")
CACHE_DIR = Path("cache")
OUTPUT_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# Together AI konfiguration
TOGETHER_API_KEY = None
together_client = None

# Logging konfiguration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_cache_key(text: str) -> str:
    """Genererer en cache nøgle for en given tekst."""
    return hashlib.md5(text.encode()).hexdigest()

async def get_cached_llm_results(cache_key: str) -> Optional[List[str]]:
    """Henter cachede LLM resultater hvis de findes."""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            async with aiofiles.open(cache_file, 'r') as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"Fejl ved læsning af cache: {e}")
    return None

async def cache_llm_results(cache_key: str, results: List[str]):
    """Gemmer LLM resultater i cache."""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    try:
        async with aiofiles.open(cache_file, 'w') as f:
            await f.write(json.dumps(results))
    except Exception as e:
        logger.error(f"Fejl ved skrivning til cache: {e}")

def set_api_key(api_key: str) -> None:
    """Sætter Together AI API nøglen."""
    global TOGETHER_API_KEY, together_client
    TOGETHER_API_KEY = api_key
    together_client = Together(api_key=TOGETHER_API_KEY)
    logger.info("API nøgle sat succesfuldt og Together AI klient initialiseret")

def load_skills_from_file() -> Set[str]:
    """Indlæser kendte færdigheder fra skills.txt."""
    if not SKILLS_FILE.exists():
        logger.warning(f"skills.txt ikke fundet. Opretter tom fil på {SKILLS_FILE}")
        with open(SKILLS_FILE, 'w', encoding='utf-8') as f:
            f.write("python\naws infrastructure\ndocker\njavascript\nnlp techniques")
        
    with open(SKILLS_FILE, 'r', encoding='utf-8') as f:
        skills = {line.strip().lower() for line in f if line.strip() and not line.startswith('#')}
    logger.info(f"Indlæst {len(skills)} færdigheder fra {SKILLS_FILE}")
    return skills

def initialize_spacy():
    """Initialiserer spaCy med en engelsk model."""
    try:
        nlp = spacy.load("en_core_web_sm")
        logger.info("spaCy model indlæst succesfuldt")
        return nlp
    except OSError:
        logger.error("spaCy model ikke fundet. Installerer...")
        import subprocess
        subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
        return spacy.load("en_core_web_sm")

def build_matcher(nlp, skills: Set[str]) -> PhraseMatcher:
    """Bygger en spaCy PhraseMatcher med kendte færdigheder."""
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    patterns = [nlp.make_doc(skill) for skill in skills]
    matcher.add("SKILL", patterns)
    return matcher

def extract_skills_ner(text: str, matcher, nlp) -> List[str]:
    """Ekstraherer færdigheder ved hjælp af NER og pattern matching."""
    doc = nlp(text)
    matches = matcher(doc)
    
    # Saml alle matches fra PhraseMatcher
    matched_skills = set()
    for _, start, end in matches:
        skill = doc[start:end].text.lower()
        # Normaliser færdigheden (fjern "programming", etc.)
        skill = normalize_skill(skill)
        if skill:  # Hvis færdigheden ikke blev filtreret væk
            matched_skills.add(skill)
    
    return list(matched_skills)

async def get_llm_skills(text: str, matched_skills: List[str]) -> List[str]:
    """Bruger Together AI's Llama model til at identificere yderligere færdigheder."""
    if not together_client:
        logger.warning("Together AI klient ikke initialiseret. Springer LLM-analyse over.")
        return []
    
    # Check cache først
    cache_key = get_cache_key(text)
    cached_results = await get_cached_llm_results(cache_key)
    if cached_results is not None:
        logger.info("Bruger cachede LLM resultater")
        return cached_results
    
    try:
        # Forbered prompten for Llama
        prompt = f"""Analysér følgende jobbeskrivelse og identificér specifikke tekniske færdigheder, 
værktøjer eller teknologier som IKKE allerede er fundet via NER matching: {matched_skills}

Returner KUN en kommasepareret liste med nye færdigheder. 
Undgå generelle termer som "programming", "development", "IT".
Fokuser på specifikke værktøjer, sprog, frameworks og teknologier.

Jobbeskrivelse:
{text}

Returner kun færdighederne, ingen forklaringer eller andet tekst."""
        
        # Kald Llama via Together AI
        response = together_client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=150
        )
        
        # Parse svaret
        skills_text = response.choices[0].message.content.strip()
        new_skills = [
            normalize_skill(skill.strip()) 
            for skill in skills_text.split(',') 
            if skill.strip()
        ]
        
        # Filtrer tomme værdier og duplikater
        new_skills = [skill for skill in new_skills if skill]
        
        # Cache resultaterne
        await cache_llm_results(cache_key, new_skills)
        
        return list(set(new_skills))
        
    except Exception as e:
        logger.error(f"Fejl ved LLM-analyse: {str(e)}")
        return []

def normalize_skill(skill: str) -> Optional[str]:
    """Normaliserer en færdighed ved at fjerne generiske termer og standardisere formatet."""
    skill = skill.lower().strip()
    
    # Liste over generiske termer der skal ignoreres
    generic_terms = {
        "programming", "development", "software", "it", "cloud", 
        "computer", "technology", "system", "platform"
    }
    
    # Hvis færdigheden KUN består af generiske termer, spring den over
    if skill in generic_terms:
        return None
        
    # Fjern "programming" fra enden af færdigheder (f.eks. "python programming" -> "python")
    for term in generic_terms:
        if skill.endswith(f" {term}"):
            skill = skill[:-len(term)].strip()
    
    # Standardiser nogle almindelige færdigheder
    skill_mapping = {
        "js": "javascript",
        "py": "python",
        "react.js": "react",
        "node.js": "node",
        # Tilføj flere mappings efter behov
    }
    
    return skill_mapping.get(skill, skill)

async def process_job(job_id: int, description: str, matcher, nlp) -> Dict:
    """Behandler en enkelt jobbeskrivelse og returnerer fundne færdigheder."""
    # Mål tid for NER
    ner_start = time.time()
    matched_skills = extract_skills_ner(description, matcher, nlp)
    ner_time = time.time() - ner_start
    
    # Mål tid for LLM
    llm_start = time.time()
    llm_skills = await get_llm_skills(description, matched_skills)
    llm_time = time.time() - llm_start
    
    # Kombiner og fjern duplikater
    all_skills = list(set(matched_skills + llm_skills))
    
    logger.info(f"Job {job_id} - NER tid: {ner_time:.2f}s, LLM tid: {llm_time:.2f}s")
    
    return {
        "job_id": job_id,
        "matched_skills": matched_skills,
        "llm_suggested_skills": llm_skills,
        "final_skills": all_skills,
        "processing_times": {
            "ner_time": round(ner_time, 2),
            "llm_time": round(llm_time, 2)
        }
    }

def aggregate_skills(results: List[Dict]) -> Dict[str, List[str]]:
    """Samler alle unikke færdigheder fra alle jobs i én liste."""
    all_skills = {
        "ner_skills": set(),
        "llm_skills": set(),
        "combined_skills": set()
    }
    
    for result in results:
        all_skills["ner_skills"].update(result["matched_skills"])
        all_skills["llm_skills"].update(result["llm_suggested_skills"])
        all_skills["combined_skills"].update(result["final_skills"])
    
    return {
        "ner_skills": sorted(list(all_skills["ner_skills"])),
        "llm_skills": sorted(list(all_skills["llm_skills"])),
        "combined_skills": sorted(list(all_skills["combined_skills"]))
    }

async def analyze_jobs(limit: Optional[int] = None, batch_size: int = 50):
    """Hovedfunktion der analyserer jobs i databasen.
    
    Args:
        limit: Maksimalt antal jobs der skal analyseres. None = alle jobs.
        batch_size: Antal jobs der behandles ad gangen før der gemmes til fil.
    """
    # Initialiser komponenter
    skills = load_skills_from_file()
    nlp = initialize_spacy()
    matcher = build_matcher(nlp, skills)
    
    # Opret output filer
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    detailed_output = OUTPUT_DIR / f"detailed_analysis_{timestamp}.json"
    aggregated_output = OUTPUT_DIR / f"aggregated_skills_{timestamp}.json"
    
    try:
        # Opret database forbindelse
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Hent alle job IDs og beskrivelser
        if limit:
            cursor.execute("SELECT id, description FROM job_postings WHERE description IS NOT NULL LIMIT ?", (limit,))
        else:
            cursor.execute("SELECT id, description FROM job_postings WHERE description IS NOT NULL")
        
        jobs = cursor.fetchall()
        results = []
        
        # Opret tasks for alle jobs
        tasks = [process_job(job_id, description, matcher, nlp) for job_id, description in jobs]
        
        # Kør jobs asynkront i batches
        for i in range(0, len(tasks), batch_size):
            batch_tasks = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)
            logger.info(f"Behandlet {len(results)}/{len(jobs)} jobs...")
            
            # Gem detaljerede resultater
            with open(detailed_output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            # Aggreger og gem samlede færdigheder
            aggregated_skills = aggregate_skills(results)
            with open(aggregated_output, 'w', encoding='utf-8') as f:
                json.dump(aggregated_skills, f, indent=2, ensure_ascii=False)
        
        logger.info(f"""Analyse færdig:
        - Behandlet {len(results)} jobs
        - Detaljerede resultater gemt i {detailed_output}
        - Aggregerede færdigheder gemt i {aggregated_output}""")
        
    except Exception as e:
        logger.error(f"Kritisk fejl under jobanalyse: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    logger.info("Starter færdighedsanalyse...")
    logger.info("BEMÆRK: Sæt Together AI API nøgle med set_api_key() før kørsel hvis LLM-analyse ønskes")
    asyncio.run(analyze_jobs()) 