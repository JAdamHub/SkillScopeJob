import asyncio
from skill_analyzer import analyze_jobs, set_api_key
import os
from config import TOGETHER_API_KEY, DEFAULT_BATCH_SIZE

async def main():
    # Brug miljøvariabel hvis tilgængelig, ellers brug config værdi
    api_key = os.getenv('TOGETHER_API_KEY', TOGETHER_API_KEY)
    if api_key:
        set_api_key(api_key)
        print("API nøgle sat succesfuldt")
    else:
        print("ADVARSEL: Ingen API nøgle fundet. LLM analyse vil blive sprunget over.")
    
    # Kør analyse på alle jobs med konfigureret batch størrelse
    print("Starter analyse af alle jobs...")
    await analyze_jobs(batch_size=DEFAULT_BATCH_SIZE)
    print("Analyse færdig!")

if __name__ == "__main__":
    asyncio.run(main()) 