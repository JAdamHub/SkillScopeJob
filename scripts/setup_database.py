#!/usr/bin/env python3
"""
Database Initialization Script for SkillScopeJob

This script initializes the SQLite database with all necessary tables
and performs any required migrations.
"""

import os
import sys
import sqlite3
from pathlib import Path

def ensure_directories():
    """Ensure all necessary directories exist BEFORE importing modules"""
    directories = [
        'data/databases',
        'data/logs',
        'data/cache',
        'data/ontologies'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Directory ensured: {directory}")

# Create directories FIRST, before any imports
ensure_directories()

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from skillscope.models.database_models import Base, engine, SessionLocal
    from skillscope.scrapers.indeed_scraper import init_database
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

def initialize_database():
    """Initialize the database with all tables"""
    try:
        print("🗄️ Initializing database tables...")
        
        # Create all tables using SQLAlchemy
        Base.metadata.create_all(bind=engine)
        print("✅ SQLAlchemy tables created")
        
        # Initialize the job scraper database
        init_database()
        print("✅ Job scraper database initialized")
        
        # Test database connection
        session = SessionLocal()
        session.close()
        print("✅ Database connection test successful")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False
    
    return True

def check_ontologies():
    """Check if ontology files exist"""
    ontology_files = [
        'data/ontologies/skill_ontology.csv',
        'data/ontologies/roles_industries_ontology.csv'
    ]
    
    missing_files = []
    for file_path in ontology_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
        else:
            print(f"✅ Ontology file found: {file_path}")
    
    if missing_files:
        print("⚠️  Missing ontology files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        print("   These files are needed for proper application functionality.")
        return False
    
    return True

def main():
    """Main initialization function"""
    print("🎯 SkillScopeJob Database Initialization")
    print("=" * 50)
    
    # Initialize database
    if not initialize_database():
        print("❌ Database initialization failed")
        return 1
    
    # Check ontologies
    if not check_ontologies():
        print("⚠️  Ontology files missing - application may not work properly")
    
    print("\n✅ Database initialization complete!")
    print("🚀 You can now start the SkillScopeJob applications")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
