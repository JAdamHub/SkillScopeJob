import sqlite3

db_file = 'indeed_jobs.db'  # Replace with your actual file name
table_name = 'job_postings'  # Replace with your actual table name

try:
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Get column names (optional, but helpful)
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [col[1] for col in cursor.fetchall()]
    print("Column names:", columns)

    # Select all columns, but truncate the 'description' column to the first 20 characters
    cursor.execute(f"""
        SELECT 
            *, 
            SUBSTR(description, 1, 20) AS short_description 
        FROM {table_name} 
        LIMIT 3;
    """)
    rows = cursor.fetchall()

    if rows:
        print("\nFirst 3 rows (with 'description' truncated to 20 characters):")
        for row in rows:
            # The last element in each row will be 'short_description'
            print(row)
    else:
        print(f"No rows found in the table '{table_name}' or the table does not exist.")

except sqlite3.Error as e:
    print(f"Error connecting to/querying the database: {e}")

finally:
    if conn:
        conn.close()
