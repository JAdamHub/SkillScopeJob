"""
Dependency installer script for CV extraction functionality.
Handles version conflicts and provides fallback options.
"""

import subprocess
import sys
import importlib

def check_package(package_name):
    """Check if a package is installed"""
    try:
        importlib.import_module(package_name)
        return True
    except ImportError:
        return False

def install_package(package_spec):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_spec])
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package_spec}: {e}")
        return False

def main():
    print("CV Extractor Dependency Installer")
    print("=" * 40)
    
    # Core dependencies that are usually safe to install
    core_deps = [
        "streamlit>=1.28.0",
        "PyPDF2>=3.0.0", 
        "pdfplumber>=0.7.6",
        "python-docx>=0.8.11",
        "together>=1.0.0"  # Added Together AI
    ]
    
    # Optional dependencies that might conflict
    optional_deps = [
        ("spacy", "spacy>=3.6.0"),
    ]
    
    print("Installing core dependencies...")
    for dep in core_deps:
        package_name = dep.split(">=")[0].split("==")[0]
        if not check_package(package_name.replace("-", "_")):
            print(f"Installing {package_name}...")
            if install_package(dep):
                print(f"✅ {package_name} installed successfully")
            else:
                print(f"❌ Failed to install {package_name}")
        else:
            print(f"✅ {package_name} already installed")
    
    print("\nChecking optional dependencies...")
    for pkg_import, pkg_spec in optional_deps:
        if not check_package(pkg_import):
            print(f"📦 {pkg_import} not found. To install manually:")
            print(f"   pip install {pkg_spec}")
            print(f"   python -m spacy download en_core_web_sm")
        else:
            print(f"✅ {pkg_import} available")
    
    print("\nDependency check complete!")
    print("You can now run the CV extraction functionality.")
    
    # Test import
    try:
        from cv_extraction import LLMCVExtractor
        print("✅ LLMCVExtractor imported successfully")
        
        # Test dependency availability
        import os
        api_key = os.getenv("TOGETHER_API_KEY")
        if api_key:
            try:
                extractor = LLMCVExtractor(api_key=api_key)
                supported = extractor.get_supported_formats()
                print(f"✅ Supported file formats: {supported}")
            except Exception as e:
                print(f"⚠️  Extractor initialization failed: {e}")
        else:
            print("ℹ️  Set TOGETHER_API_KEY environment variable to test full functionality")
            
    except ImportError as e:
        print(f"\n⚠️  Import test failed: {e}")

if __name__ == "__main__":
    main()
