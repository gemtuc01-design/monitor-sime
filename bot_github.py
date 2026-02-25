import time
import requests
import os
import json
import re
from datetime import datetime, timezone, timedelta
from selenium import webdriver
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

def normalizar(texto):
    reemplazos = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U"}
    t = texto.upper()
    for original, reemplazo in reemplazos.items():
        t = t.replace(original, reemplazo)
    return t

# Ajustamos la hora exacta de Argentina (UTC-3)
ar_tz = timezone(timedelta(hours=-3))
ahora_ar = datetime.now(ar_tz)

# --- 1. CARGAMOS LAS MEMORIAS ---
archivo_vistos = "vistos.txt"
if os.path.exists(archivo_vistos):
    with open(archivo_vistos, "r") as f:
        vistos = set(line.strip() for line in f if line.strip())
else:
    vistos = set()

# Esta es la nueva "Agenda"
archivo_agendados = "agendados.json"
agendados =[]
if os.path.exists(archivo_agendados):
    with open(archivo_agendados, "r") as f:
        try: agendados = json.load(f)
        except: pass

# --- 2. EL RECORDATORIO DE LAS 21:00 HS ---
if ahora_ar.hour == 21:
    mañana = ahora_ar + timedelta(days=1)
    fecha_mañana = mañana.strftime("%d/%m/%Y") # Ejemplo: 12/02/2026
    
    for cargo in agendados:
        # Si la fecha de mañana está dentro de las fechas que guardó el bot
        if fecha_mañana in cargo.get("fechas",[]):
            mensaje = (
                f"⏰ <b>¡RECORDATORIO PARA MAÑANA!</b> ⏰\n\n"
                f"Mañana (<b>{fecha_mañana}</b>) tenés que asistir o estar atento a esta designación:\n\n"
                f"<code>{cargo['texto'][:500]}...</code>\n\n"
                f"📍 Prepará todo. ¡Éxitos!"
            )
            enviar_telegram(mensaje)

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)

try:
    while True:
        driver.get(URL)
        wait = WebDriverWait(driver, 40)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
        time.sleep(5)

        filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        procesado_alguno_nuevo = False

        for fila in filas:
            texto_fila = fila.text.strip()
            texto_norm = normalizar(texto_fila)
            
            if "PDVC-" in texto_norm and "MAESTRO DE GRADO" in texto_norm:
                id_tramite = texto_fila.split()[0]
                
                if id_tramite not in vistos:
                    boton_detalle = fila.find_element(By.XPATH, ".//a[contains(text(), 'Ver Detalle')] | .//button[contains(text(), 'Ver Detalle')] | .//*[contains(text(), 'Ver Detalle')]")
                    driver.execute_script("arguments[0].click();", boton_detalle)
                    time.sleep(4)
                    
                    texto_detalle_original = driver.find_element(By.TAG_NAME, "body").text
                    texto_detalle_limpio = normalizar(texto_detalle_original)
                    
                    es_prioridad = False
                    palabras_clave =["JAURETCHE", "CRUZ ALTA", "BANDA DEL RIO SALI", "EVA PERON"]
                    
                    if any(palabra in texto_detalle_limpio for palabra in palabras_clave):
                        es_prioridad = True

                    if es_prioridad:
                        mensaje = (
                            f"<b>🚨 ⭐ ¡ALERTA PRIORITARIA: TU ZONA! ⭐ 🚨</b>\n"
                            f"📍 <i>Detectado en 'Ver Detalles'</i>\n\n"
                            f"<code>{texto_detalle_original[:600]}...</code>\n\n"
                            f"🔗 <a href='{URL}'>¡POSTULATE YA! CLICK AQUÍ</a>"
                        )
                        
                        # Extraemos automáticamente las fechas del texto (DD/MM/YYYY)
                        texto_completo = texto_fila + " " + texto_detalle_original
                        fechas_encontradas = re.findall(r'\d{2}/\d{2}/\d{4}', texto_completo)
                        
                        # Lo guardamos en la agenda digital
                        agendados.append({
                            "id": id_tramite,
                            "fechas": fechas_encontradas,
                            "texto": texto_detalle_original
                        })
                    else:
                        mensaje = (
                            f"<b>🍎 NUEVA VACANTE: MAESTRO DE GRADO</b>\n"
                            f"🆔 {id_tramite}\n\n"
                            f"<code>{texto_detalle_original[:400]}...</code>\n\n"
                            f"🔗 <a href='{URL}'>Ir al SIME</a>"
                        )
                    
                    enviar_telegram(mensaje)
                    vistos.add(id_tramite)
                    procesado_alguno_nuevo = True
                    break 

        if not procesado_alguno_nuevo:
            break

    # Guardamos las memorias
    with open(archivo_vistos, "w") as f:
        for item in sorted(vistos):
            f.write(f"{item}\n")
            
    with open(archivo_agendados, "w") as f:
        json.dump(agendados, f)

except Exception as e:
    print(f"Error General: {e}")
finally:
    driver.quit()
