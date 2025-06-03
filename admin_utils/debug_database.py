import sqlite3
import pandas as pd
import os

# Get the path to the root directory (one level up from admin_utils)
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Set the database path to the root directory
db_file = os.path.join(root_dir, 'indeed_jobs.db')
table_name = 'job_postings'

try:
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Show tables in the database
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables in the database:")
    for table in tables:
        print(f"- {table[0]}")
    
    # Show column names for the job_postings table
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [col[1] for col in cursor.fetchall()]
    print("\nColumns in job_postings:")
    for col in columns:
        print(f"- {col}")
    
    # Show a brief overview of the first 3 rows with ALL columns
    print("\nSample data (first 3 rows):")
    
    # Use pandas to display the data in a more readable format
    # This shows all columns but limits the length of text fields
    query = f"SELECT * FROM {table_name} LIMIT 3;"
    df = pd.read_sql_query(query, conn)
    
    # Convert long text fields to shorter versions
    for col in df.columns:
        if df[col].dtype == 'object':  # If the column contains text
            df[col] = df[col].astype(str).apply(lambda x: x[:30] + '...' if len(x) > 30 else x)
    
    # Display dataframe
    pd.set_option('display.max_columns', None)  # Show all columns
    pd.set_option('display.width', 1000)  # Wider display
    print(df)

except sqlite3.Error as e:
    print(f"Error connecting to/querying the database: {e}")

finally:
    if 'conn' in locals() and conn:
        conn.close()
