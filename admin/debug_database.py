import sqlite3
import os
import json
from tabulate import tabulate

# Get the path to the root directory (one level up from admin_utils)
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Set the database path to the root directory
db_file = os.path.join(root_dir, 'indeed_jobs.db')

def generate_db_overview(output_format="text"):
    """Generate a comprehensive overview of the database structure.
    
    Args:
        output_format (str): Format to output the overview in ('text', 'json', or 'markdown')
    
    Returns:
        str: Database overview in the specified format
    """
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [table[0] for table in cursor.fetchall()]
        
        db_structure = {}
        sample_data = {}
        
        for table in tables:
            # Get column information
            cursor.execute(f"PRAGMA table_info({table});")
            columns_info = cursor.fetchall()
            
            # Format column information
            columns = []
            for col in columns_info:
                col_id, col_name, col_type, not_null, default_val, is_pk = col
                columns.append({
                    "name": col_name,
                    "type": col_type,
                    "nullable": not_null == 0,
                    "primary_key": is_pk == 1,
                    "default": default_val
                })
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            row_count = cursor.fetchone()[0]
            
            # Get sample data (first 3 rows)
            cursor.execute(f"SELECT * FROM {table} LIMIT 3;")
            rows = cursor.fetchall()
            
            # Get column names for the sample data
            column_names = [description[0] for description in cursor.description]
            
            # Format sample data
            formatted_rows = []
            for row in rows:
                formatted_row = {}
                for i, value in enumerate(row):
                    # Truncate long text values
                    if isinstance(value, str) and len(value) > 50:
                        formatted_row[column_names[i]] = value[:50] + "..."
                    else:
                        formatted_row[column_names[i]] = value
                formatted_rows.append(formatted_row)
            
            # Store table information
            db_structure[table] = {
                "columns": columns,
                "row_count": row_count
            }
            
            sample_data[table] = {
                "column_names": column_names,
                "rows": formatted_rows
            }
        
        # Format the output based on the requested format
        if output_format == "json":
            return json.dumps({"structure": db_structure, "sample_data": sample_data}, indent=2)
        
        elif output_format == "markdown":
            md_output = "# Database Overview: indeed_jobs.db\n\n"
            
            for table, info in db_structure.items():
                md_output += f"## Table: {table} ({info['row_count']} rows)\n\n"
                
                # Column information
                md_output += "### Columns\n\n"
                md_output += "| Name | Type | Nullable | Primary Key | Default |\n"
                md_output += "|------|------|----------|-------------|---------|\n"
                
                for col in info['columns']:
                    pk = "Yes" if col['primary_key'] else "No"
                    nullable = "Yes" if col['nullable'] else "No"
                    default = col['default'] if col['default'] is not None else ""
                    md_output += f"| {col['name']} | {col['type']} | {nullable} | {pk} | {default} |\n"
                
                # Sample data
                if sample_data[table]['rows']:
                    md_output += "\n### Sample Data\n\n"
                    headers = sample_data[table]['column_names']
                    
                    # Create a list of dictionaries for tabulate
                    rows = []
                    for row in sample_data[table]['rows']:
                        rows.append([row.get(col, "") for col in headers])
                    
                    md_output += tabulate(rows, headers=headers, tablefmt="pipe")
                    md_output += "\n\n"
                
            return md_output
        
        else:  # Default to text format
            text_output = "DATABASE OVERVIEW: indeed_jobs.db\n\n"
            
            for table, info in db_structure.items():
                text_output += f"TABLE: {table} ({info['row_count']} rows)\n"
                text_output += "=" * 50 + "\n\n"
                
                # Column information
                text_output += "COLUMNS:\n"
                for col in info['columns']:
                    pk = "PRIMARY KEY" if col['primary_key'] else ""
                    nullable = "NULLABLE" if col['nullable'] else "NOT NULL"
                    default = f"DEFAULT: {col['default']}" if col['default'] is not None else ""
                    text_output += f"  - {col['name']}: {col['type']} {nullable} {pk} {default}\n"
                
                # Sample data
                if sample_data[table]['rows']:
                    text_output += "\nSAMPLE DATA:\n"
                    headers = sample_data[table]['column_names']
                    
                    # Create a list of dictionaries for tabulate
                    rows = []
                    for row in sample_data[table]['rows']:
                        rows.append([row.get(col, "") for col in headers])
                    
                    text_output += tabulate(rows, headers=headers, tablefmt="grid")
                    text_output += "\n\n"
                
            return text_output
    
    except sqlite3.Error as e:
        return f"Error connecting to/querying the database: {e}"
    
    finally:
        if 'conn' in locals() and conn:
            conn.close()

# If this script is run directly, print the database overview
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate a database overview.')
    parser.add_argument('--format', choices=['text', 'json', 'markdown'], default='text',
                        help='Output format (text, json, or markdown)')
    parser.add_argument('--output', help='Output file path (if not specified, prints to console)')
    
    args = parser.parse_args()
    
    overview = generate_db_overview(args.format)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(overview)
        print(f"Database overview written to {args.output}")
    else:
        print(overview)
