#!/usr/bin/env python3
"""
SkillScopeJob Main Application Launcher
This script properly sets up the Python path and launches the main Streamlit app.
"""

import sys
import os
import subprocess
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
ensure_directories()

def main():
    # Get the directory where this script is located (project root)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(script_dir, 'src')
    
    # Set the PYTHONPATH environment variable
    env = os.environ.copy()
    current_pythonpath = env.get('PYTHONPATH', '')
    if current_pythonpath:
        env['PYTHONPATH'] = f"{src_path}:{current_pythonpath}"
    else:
        env['PYTHONPATH'] = src_path
    
    # Path to the main app
    main_app_path = os.path.join(script_dir, 'src', 'skillscope', 'ui', 'main_app.py')
    
    print("🎯 Starting SkillScopeJob Main Application...")
    print(f"📁 Project root: {script_dir}")
    print(f"🐍 Python path: {src_path}")
    print(f"🚀 Launching: {main_app_path}")
    print()
    print("🌐 The application will open in your browser at http://localhost:8501")
    print("📝 Press Ctrl+C to stop the application")
    print("-" * 60)
    
    # Launch streamlit with the proper environment
    try:
        subprocess.run([
            'streamlit', 'run', main_app_path,
            '--server.address', '0.0.0.0',
            '--server.port', '8501'
        ], env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error launching application: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
        return 0

if __name__ == "__main__":
    sys.exit(main())
