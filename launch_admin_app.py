#!/usr/bin/env python3
"""
SkillScopeJob Admin Application Launcher
This script properly sets up the Python path and launches the admin Streamlit app.
"""

import sys
import os
import subprocess

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
    
    # Path to the admin app
    admin_app_path = os.path.join(script_dir, 'src', 'skillscope', 'ui', 'admin_app.py')
    
    print("🔧 Starting SkillScopeJob Admin Dashboard...")
    print(f"📁 Project root: {script_dir}")
    print(f"🐍 Python path: {src_path}")
    print(f"🚀 Launching: {admin_app_path}")
    print()
    print("🌐 The application will open in your browser at http://localhost:8502")
    print("📝 Press Ctrl+C to stop the application")
    print("-" * 60)
    
    # Launch streamlit with the proper environment
    try:
        subprocess.run([
            'streamlit', 'run', admin_app_path,
            '--server.address', '0.0.0.0',
            '--server.port', '8502'
        ], env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error launching application: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
        return 0

if __name__ == "__main__":
    sys.exit(main())
