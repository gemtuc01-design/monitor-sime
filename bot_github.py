import time
import requests
import os
import re
import urllib.parse
from datetime import datetime, timezone, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# URL principal del SIME
URL_PRINCIPAL = "https://sime.educaciontuc.gov.ar/Vacantes/Index#no-back-button"

def enviar_mensaje_telegram(mensaje, botones=None):
    url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    if botones:
        payload["reply_markup"] = json.dumps(botones)
    requests.post(url_api, json=payload)

def normalizar(texto):
    reemplazos = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U"}
    t = texto.upper()
    for original, reemplazo in reemplazos.items():
        t = t.replace(original, reemplazo)
    return t

# --- ARCHIVOS DE MEMORIA ---
archivo_vistos = "vistos.txt"
if os.path.exists(archivo_vistos):
    with open(archivo_vistos, "r") as f:
        vistos = set(line.strip() for line in f if line.strip())
else:
    vistos = set()

# --- CONFIGURAR NAVEGADOR ---
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)

try:
    while True:
        driver.get(URL_PRINCIPAL)
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
                    print(f"Entrando al detalle de: {id_tramite}")
                    
                    boton_detalle = fila.find_element(By.XPATH, ".//a[contains(text(), 'Ver Detalle')] | .//button[contains(text(), 'Ver Detalle')] | .//*[contains(text(), 'Ver Detalle')]")
                    driver.execute_script("arguments[0].click();", boton_detalle)
                    time.sleep(4)
                    
                    texto_detalle_original = driver.find_element(By.TAG_NAME, "body").text
                    texto_detalle_limpio = normalizar(texto_detalle_original)
                    
                    # 1. ESCUELA REAL
                    match_escuela = re.search(r'\[\d+/\d+\]\s*(.*?)(?=\sMAESTRO DE GRADO|\s-)', texto_detalle_original)
                    if match_escuela:
                        nombre_escuela_real = match_escuela.group(1).strip()
                    else:
                        nombre_escuela_real = "Escuela a designar"

                    # 2. DESCRIPCIÓN CABECERA
                    match_desc = re.search(r'Descripción:\s*(.*?)(?=\nVacantes|\nEstablecimiento)', texto_detalle_original, re.DOTALL)
                    descripcion_corta = match_desc.group(1).strip() if match_desc else "Ver detalles en SIME"

                    # 3. GOOGLE MAPS
                    mi_casa = "Calle 13 y 4, Villa Mariano Moreno, Tucuman, Argentina"
                    escuela_tarde = "Escuela N 2 Provincia de San Luis, Ranchillos, Tucuman, Argentina"
                    escuela_maps = nombre_escuela_real + ", Tucuman, Argentina"
                    url_maps = f"https://www.google.com/maps/dir/?api=1&origin={urllib.parse.quote(mi_casa)}&destination={urllib.parse.quote(escuela_tarde)}&waypoints={urllib.parse.quote(escuela_maps)}&travelmode=driving"
                    
                    # 4. GOOGLE CALENDAR (Extracción de Fecha)
                    parametros_fecha = ""
                    match_fecha = re.search(r'Fecha de Designación:\s*(\d{2}/\d{2}/\d{4})\s*(\d{1,2}:\d{2})', texto_detalle_original)
                    if match_fecha:
                        dia, mes, anio = match_fecha.group(1).split('/')
                        hora, minuto = match_fecha.group(2).split(':')
                        
                        hora_int = int(hora)
                        if "P.M." in texto_detalle_limpio and hora_int < 12:
                            hora_int += 12
                            
                        fecha_inicio = f"{anio}{mes}{dia}T{hora_int:02d}{minuto}00"
                        fecha_fin = f"{anio}{mes}{dia}T{(hora_int+1):02d}{minuto}00" # Evento de 1 hora
                        parametros_fecha = f"&dates={fecha_inicio}/{fecha_fin}"

                    titulo_cal = urllib.parse.quote(f"SIME: {nombre_escuela_real}")
                    detalles_cal = urllib.parse.quote(f"ID Cargo: {id_tramite}\n\nDetalles:\n{descripcion_corta}")
                    ubicacion_cal = urllib.parse.quote(f"{nombre_escuela_real}, Tucumán")
                    
                    url_calendar = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={titulo_cal}&details={detalles_cal}&location={ubicacion_cal}{parametros_fecha}"

                    # --- FILTRO PRIORIDAD ---
                    es_prioridad = False
                    palabras_clave =["JAURETCHE", "CRUZ ALTA", "BANDA DEL RIO SALI", "EVA PERON"]
                    if any(palabra in texto_detalle_limpio for palabra in palabras_clave):
                        es_prioridad = True

                    # --- BOTONES EN TELEGRAM (Sin el botón de SIME) ---
                    botones_teclado = {
                        "inline_keyboard": [[{"text": f"🗺️ Ruta (Casa -> {nombre_escuela_real[:10]}... -> Ranchillos)", "url": url_maps}],
                            [{"text": "📅 Agendar en Google Calendar", "url": url_calendar}]
                        ]
                    }

                    if es_prioridad:
                        mensaje = (
                            f"<b>🚨 ⭐ ¡ALERTA PRIORITARIA, COMPADRE! ⭐ 🚨</b>\n"
                            f"📍 <i>Detecté tus zonas favoritas</i>\n\n"
                            f"🏫 <b>Escuela de Trabajo:</b>\n<code>{nombre_escuela_real}</code>\n\n"
                            f"ℹ️ <b>Info / Cabecera:</b>\n<i>{descripcion_corta}</i>\n"
                        )
                    else:
                        mensaje = (
                            f"<b>🍎 NUEVA VACANTE: MAESTRO DE GRADO</b>\n"
                            f"🆔 {id_tramite}\n\n"
                            f"🏫 <b>Escuela de Trabajo:</b>\n<code>{nombre_escuela_real}</code>\n\n"
                            f"ℹ️ <b>Info / Cabecera:</b>\n<i>{descripcion_corta}</i>\n"
                        )
                    
                    enviar_mensaje_telegram(mensaje, botones=botones_teclado)
                    vistos.add(id_tramite)
                    procesado_alguno_nuevo = True
                    break 

        if not procesado_alguno_nuevo:
            break

    # Guardamos los vistos para no repetir
    with open(archivo_vistos, "w") as f:
        for item in sorted(vistos):
            f.write(f"{item}\n")

    # Mensaje de Buenas noches (20:00 AR)
    ar_tz = timezone(timedelta(hours=-3))
    ahora_ar = datetime.now(ar_tz)
    if ahora_ar.hour == 20:
        enviar_mensaje_telegram(f"🌙 <b>Check Diario OK</b>\nTodo en orden, bot trabajando al 100%.")

except Exception as e:
    print(f"Error General: {e}")
finally:
    driver.quit()
