import subprocess
import sys
from skill_analyzer import set_api_key, analyze_jobs
import asyncio

def install_dependencies():
    """Installerer nødvendige Python packages."""
    dependencies = ["aiofiles"]
    for dep in dependencies:
        subprocess.check_call([sys.executable, "-m", "pip", "install", dep])

# Konfiguration for Llama API
API_KEY = "f7f98865262e753df89a8ac3b7bc474ff5eb2e86416e78550148a64d061e36ed"  # Erstat med din rigtige API nøgle

if __name__ == "__main__":
    # Installer dependencies
    install_dependencies()
    
    # Sæt API nøglen
    set_api_key(API_KEY)
    
    # Kør analysen på kun 5 jobs for at teste hastighed
    asyncio.run(analyze_jobs(limit=5, batch_size=5)) 