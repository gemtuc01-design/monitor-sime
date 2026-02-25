import time
import requests
import os
from datetime import datetime, timezone
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
    # Usamos un bucle para procesar los detalles de a uno y no marear al navegador
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
            
            # Buscamos Maestro de Grado
            if "PDVC-" in texto_norm and "MAESTRO DE GRADO" in texto_norm:
                id_tramite = texto_fila.split()[0]
                
                if id_tramite not in vistos:
                    print(f"Entrando al detalle de: {id_tramite}")
                    
                    # Buscamos el botón 'Ver Detalle' específico de esta fila
                    boton_detalle = fila.find_element(By.XPATH, ".//a[contains(text(), 'Ver Detalle')] | .//button[contains(text(), 'Ver Detalle')] | .//*[contains(text(), 'Ver Detalle')]")
                    driver.execute_script("arguments[0].click();", boton_detalle)
                    
                    # Esperamos a que cargue la página del detalle
                    time.sleep(4)
                    
                    # Leemos TODO el texto que hay adentro del detalle
                    texto_detalle_original = driver.find_element(By.TAG_NAME, "body").text
                    texto_detalle_limpio = normalizar(texto_detalle_original)
                    
                    # --- BÚSQUEDA DE TUS ESCUELAS EN EL DETALLE ---
                    es_prioridad = False
                    palabras_clave =["JAURETCHE", "CRUZ ALTA", "BANDA DEL RIO SALI", "EVA PERON"]
                    
                    if any(palabra in texto_detalle_limpio for palabra in palabras_clave):
                        es_prioridad = True

                    if es_prioridad:
                        mensaje = (
                            f"<b>🚨 ⭐ ¡ALERTA PRIORITARIA: TU ZONA! ⭐ 🚨</b>\n"
                            f"📍 <i>Detectado en 'Ver Detalles' (Cruz Alta / Jauretche)</i>\n\n"
                            f"<b>Información del Cargo:</b>\n<code>{texto_detalle_original[:600]}...</code>\n\n"
                            f"🔗 <a href='{URL}'>¡POSTULATE YA! CLICK AQUÍ</a>"
                        )
                    else:
                        mensaje = (
                            f"<b>🍎 NUEVA VACANTE: MAESTRO DE GRADO</b>\n"
                            f"🆔 {id_tramite}\n\n"
                            f"<b>Detalles Generales:</b>\n<code>{texto_detalle_original[:400]}...</code>\n\n"
                            f"🔗 <a href='{URL}'>Ir al SIME</a>"
                        )
                    
                    enviar_telegram(mensaje)
                    vistos.add(id_tramite)
                    procesado_alguno_nuevo = True
                    
                    # Salimos del FOR para recargar la página principal y seguir con el próximo
                    # (Esto evita que el navegador se rompa al volver atrás)
                    break 

        # Si recorrió todas las filas y no encontró nada nuevo, termina el ciclo
        if not procesado_alguno_nuevo:
            break

    # Guardamos en la memoria todo lo que procesó
    with open(archivo_vistos, "w") as f:
        for item in sorted(vistos):
            f.write(f"{item}\n")

    # Check nocturno de estado (A las 20:00 hs de Argentina)
    ahora_utc = datetime.now(timezone.utc)
    if ahora_utc.hour == 23:
        enviar_telegram(f"🌙 <b>Check Diario OK</b>\nBúsqueda profunda en 'Detalles' completada.\nVacantes guardadas: {len(vistos)}")

except Exception as e:
    ahora_utc = datetime.now(timezone.utc)
    if ahora_utc.hour == 23:
        enviar_telegram(f"⚠️ <b>Check Diario:</b> Error: {e}")
    print(f"Error General: {e}")
finally:
    driver.quit()
