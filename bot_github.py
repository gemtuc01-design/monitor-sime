import time
import requests
import os
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
URL = "https://sime.educaciontuc.gov.ar/Vacantes/Index#no-back-button"

def enviar_telegram(mensaje):
    url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url_api, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"})

# --- LÓGICA DE MEMORIA ---
archivo_vistos = "vistos.txt"
if os.path.exists(archivo_vistos):
    with open(archivo_vistos, "r") as f:
        vistos = set(line.strip() for line in f if line.strip())
else:
    vistos = set()

# Configuración de Chrome
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)
try:
    print(f"Iniciando revisión a las {datetime.now().strftime('%H:%M:%S')}")
    driver.get(URL)
    wait = WebDriverWait(driver, 40)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
    time.sleep(5)

    filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    nuevas_encontradas = 0

    for fila in filas:
        texto = fila.text.strip()
        texto_upper = texto.upper()
        
        if "PDVC-" in texto_upper and "MAESTRO DE GRADO" in texto_upper:
            id_tramite = texto.split()[0]
            
            if id_tramite not in vistos:
                mensaje = (
                    f"<b>🍎 NUEVA VACANTE: MAESTRO DE GRADO</b>\n\n"
                    f"<code>{texto}</code>\n\n"
                    f"🔗 <a href='{URL}'>Ir al SIME</a>"
                )
                enviar_telegram(mensaje)
                vistos.add(id_tramite)
                nuevas_encontradas += 1

    # Guardamos memoria
    with open(archivo_vistos, "w") as f:
        for item in sorted(vistos):
            f.write(f"{item}\n")

    # --- MENSAJE DE CHECK NOCTURNO ---
    # La última corrida es a las 23:00 UTC (20:00 Argentina)
    ahora_utc = datetime.now(timezone.utc)
    if ahora_utc.hour == 23:
        # Enviamos un mensaje de estado solo en la última corrida del día
        enviar_telegram(f"🌙 <b>Check Diario OK</b>\nEl bot finalizó su jornada correctamente.\nVacantes en memoria: {len(vistos)}")

except Exception as e:
    # Si algo falla en la última corrida, intentamos avisar del error
    ahora_utc = datetime.now(timezone.utc)
    if ahora_utc.hour == 23:
        enviar_telegram(f"⚠️ <b>Check Diario:</b> El bot tuvo un error: {e}")
    print(f"Error: {e}")
finally:
    driver.quit()
