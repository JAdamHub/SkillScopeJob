# Job Market Skill Demand Analysis

Dette projekt analyserer jobopslag for at identificere efterspurgte færdigheder og tendenser på jobmarkedet.

## Opsætning

1.  **Klon projektet:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Opret og aktiver et virtuelt miljø (anbefales):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # På macOS/Linux
    # venv\Scripts\activate  # På Windows
    ```

3.  **Installer afhængigheder:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Download spaCy NLP-model:**
    ```bash
    python -m spacy download en_core_web_lg
    ```

5.  **Forbered inputfiler:**
    *   Placer din SQLite-database med jobopslag i projektmappen og navngiv den `job_postings.db`.
    *   Placer din CSV-fil med færdighedstaksonomi i projektmappen og navngiv den `skill_taxonomy.csv`.
        Filen skal som minimum have kolonnerne "variation" og "canonical_skill".

## Kørsel

Kør hovedscriptet:
```bash
python skill_analyzer.py
```

Scriptet vil:
1.  Indlæse jobopslag og færdighedstaksonomi.
2.  Udpakke færdigheder fra jobbeskrivelser.
3.  Logge potentielle nye færdigheder til `potential_new_skills_log.csv`.
4.  Analysere færdighedstendenser.
5.  Gemme en rapport i `skill_trend_report.json`.
6.  Logge procesinformation til konsollen og/eller `run_log.txt`.
