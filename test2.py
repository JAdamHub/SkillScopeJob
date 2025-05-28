import cloudscraper
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# Opsæt Selenium
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

# Forsøg med cloudscraper først
scraper = cloudscraper.create_scraper()
response = scraper.get("https://www.indeed.com/jobs?q=python&l=remote")

# Gå til siden med Selenium
driver.get("https://www.indeed.com/jobs?q=python&l=remote")
time.sleep(5)

# Tjek for Cloudflare verifikation
try:
    verify_button = driver.find_element(By.ID, "challenge-form")
    if verify_button:
        print("Manuel verifikation kræves. Udfyld venligst udfordringen.")
        while driver.find_elements(By.ID, "challenge-form"):
            time.sleep(2)  # Vent på manuel fuldførelse
except:
    pass

# Scrap jobopslag
job_titles = driver.find_elements(By.CLASS_NAME, "jobTitle")
for job in job_titles:
    print(job.text)

# Luk browseren
driver.quit()