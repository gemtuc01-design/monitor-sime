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

# --- MEMORIA ---
archivo_vistos = "vistos.txt"
if os.path.exists(archivo_vistos):
    with open(archivo_vistos, "r") as f:
        vistos = set(line.strip() for line in f if line.strip())
else:
    vistos = set()

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)
try:
    driver.get(URL)
    wait = WebDriverWait(driver, 40)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
    time.sleep(5)

    filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    
    for fila in filas:
        texto = fila.text.strip()
        texto_upper = texto.upper()
        
        # Filtro base: Maestro de Grado
        if "PDVC-" in texto_upper and "MAESTRO DE GRADO" in texto_upper:
            id_tramite = texto.split()[0]
            
            if id_tramite not in vistos:
                # --- LÓGICA DE PRIORIDAD (ZONA ESTRATÉGICA) ---
                es_prioridad = False
                # Definimos tus palabras clave de interés
                zonas_interes = ["JAURETCHE", "CRUZ ALTA", "BANDA DEL RIO SALI", "EVA PERON"]
                
                if any(zona in texto_upper for zona in zonas_interes):
                    es_prioridad = True

                if es_prioridad:
                    mensaje = (
                        f"<b>🚨 ⭐ ¡ALERTA PRIORITARIA: TU ZONA! ⭐ 🚨</b>\n"
                        f"📍 <i>Detectado: JAURETCHE / CRUZ ALTA</i>\n\n"
                        f"<code>{texto}</code>\n\n"
                        f"🔗 <a href='{URL}'>¡POSTULATE YA! CLICK AQUÍ</a>"
                    )
                else:
                    mensaje = (
                        f"<b>🍎 NUEVA VACANTE: MAESTRO DE GRADO</b>\n\n"
                        f"<code>{texto}</code>\n\n"
                        f"🔗 <a href='{URL}'>Ir al SIME</a>"
                    )
                
                enviar_telegram(mensaje)
                vistos.add(id_tramite)
                time.sleep(2)

    with open(archivo_vistos, "w") as f:
        for item in sorted(vistos):
            f.write(f"{item}\n")

    # Check nocturno (20hs Argentina)
    ahora_utc = datetime.now(timezone.utc)
    if ahora_utc.hour == 23:
        enviar_telegram(f"🌙 <b>Check Diario OK</b>\nTodo en orden por hoy.\nVacantes guardadas: {len(vistos)}")

except Exception as e:
    ahora_utc = datetime.now(timezone.utc)
    if ahora_utc.hour == 23:
        enviar_telegram(f"⚠️ <b>Check Diario:</b> Error: {e}")
    print(f"Error: {e}")
finally:
    driver.quit()
