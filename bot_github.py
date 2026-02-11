import time
import requests
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Datos desde los Secrets de GitHub
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
URL = "https://sime.educaciontuc.gov.ar/Vacantes/Index#no-back-button"

def enviar_telegram(mensaje):
    url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url_api, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"})

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

# Leemos vacantes ya enviadas
archivo_vistos = "vistos.txt"
if os.path.exists(archivo_vistos):
    with open(archivo_vistos, "r") as f:
        vistos = set(f.read().splitlines())
else:
    vistos = set()

driver = webdriver.Chrome(options=options)
try:
    driver.get(URL)
    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
    time.sleep(5)

    filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    
    for fila in filas:
        texto = fila.text.strip()
        if "PDVC-" in texto.upper() and "MAESTRO DE GRADO" in texto.upper():
            id_tramite = texto.split()[0]
            if id_tramite not in vistos:
                mensaje = f"<b>🍎 NUEVA VACANTE: MAESTRO DE GRADO</b>\n\n<code>{texto}</code>"
                enviar_telegram(mensaje)
                vistos.add(id_tramite)

    # Guardamos los nuevos vistos
    with open(archivo_vistos, "w") as f:
        f.write("\n".join(vistos))

except Exception as e:
    print(f"Error: {e}")
finally:
    driver.quit()
