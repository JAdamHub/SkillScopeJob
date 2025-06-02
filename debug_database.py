import sqlite3

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
    
    # Vis en kort oversigt over de første 3 rækker med kun nøglekolonner
    print("\nEksempel på data (første 3 rækker):")
    
    # Vælg kun relevante kolonner - tilpas dette efter behov
    # Dette er et eksempel - du kan ændre hvilke kolonner der vises
    select_columns = "id, title, company, location, date_posted"
    
    cursor.execute(f"SELECT {select_columns} FROM {table_name} LIMIT 3;")
    rows = cursor.fetchall()
    
    if rows:
        for i, row in enumerate(rows):
            print(f"\nRække {i+1}:")
            for j, col in enumerate(select_columns.split(', ')):
                print(f"  {col}: {row[j]}")
    else:
        print(f"Ingen rækker fundet i tabellen '{table_name}' eller tabellen eksisterer ikke.")

except sqlite3.Error as e:
    print(f"Fejl ved forbindelse til/forespørgsel på databasen: {e}")

finally:
    if 'conn' in locals() and conn:
        conn.close()
