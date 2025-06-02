import sqlite3
import pandas as pd

db_file = 'indeed_jobs.db'
table_name = 'job_postings'

try:
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Vis tabelnavne i databasen
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tabeller i databasen:")
    for table in tables:
        print(f"- {table[0]}")
    
    # Vis kolonnenavne for job_postings tabellen
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [col[1] for col in cursor.fetchall()]
    print("\nKolonner i job_postings:")
    for col in columns:
        print(f"- {col}")
    
    # Vis en kort oversigt over de første 3 rækker med ALLE kolonner
    print("\nEksempel på data (første 3 rækker):")
    
    # Brug pandas til at vise dataene i et mere læsbart format
    # Dette viser alle kolonner, men begrænser tekstlængden for lange felter
    query = f"SELECT * FROM {table_name} LIMIT 3;"
    df = pd.read_sql_query(query, conn)
    
    # Konverter lange tekstfelter til kortere versioner
    for col in df.columns:
        if df[col].dtype == 'object':  # Hvis kolonnen indeholder tekst
            df[col] = df[col].astype(str).apply(lambda x: x[:30] + '...' if len(x) > 30 else x)
    
    # Vis dataframe
    pd.set_option('display.max_columns', None)  # Vis alle kolonner
    pd.set_option('display.width', 1000)  # Bredere visning
    print(df)

except sqlite3.Error as e:
    print(f"Fejl ved forbindelse til/forespørgsel på databasen: {e}")

finally:
    if 'conn' in locals() and conn:
        conn.close()
