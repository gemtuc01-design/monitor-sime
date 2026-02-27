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

def enviar_mensaje_telegram(mensaje, botones=None):
    url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    if botones:
        payload["reply_markup"] = json.dumps(botones)
    
    requests.post(url_api, data=payload)

def normalizar(texto):
    reemplazos = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U"}
    t = texto.upper()
    for original, reemplazo in reemplazos.items():
        t = t.replace(original, reemplazo)
    return t

# --- HORARIOS ARGENTINA ---
ar_tz = timezone(timedelta(hours=-3))
ahora_ar = datetime.now(ar_tz)

# --- CARGAR ARCHIVOS ---
archivo_vistos = "vistos.txt"
if os.path.exists(archivo_vistos):
    with open(archivo_vistos, "r") as f:
        vistos = set(line.strip() for line in f if line.strip())
else:
    vistos = set()

archivo_agendados = "agendados.json"
agendados =[]
if os.path.exists(archivo_agendados):
    try:
        with open(archivo_agendados, "r") as f:
            agendados = json.load(f)
    except:
        pass

archivo_offset = "offset.txt"
offset = 0
if os.path.exists(archivo_offset):
    try:
        with open(archivo_offset, "r") as f:
            offset = int(f.read().strip())
    except:
        pass

# --- 1. LEER TUS BOTONES Y MENSAJES (INTERACTIVIDAD) ---
url_updates = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}"
try:
    res = requests.get(url_updates).json()
    if res.get("ok"):
        for item in res["result"]:
            offset = item["update_id"] + 1
            
            # Si tocaste un botón...
            if "callback_query" in item:
                cb = item["callback_query"]
                cb_id = cb["id"]
                data = cb["data"]
                
                # Le avisamos a Telegram que ya vimos el clic (para que deje de cargar el botón)
                requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery", data={"callback_query_id": cb_id})
                
                if data.startswith("agendar_"):
                    id_cargo = data.split("_")[1]
                    # El bot te responde y te "obliga" a responderle ese mensaje
                    texto_respuesta = f"📝 ¡Perfecto, Marcos!\nVas a agendar el cargo <b>{id_cargo}</b>.\n\nEscribí como respuesta la fecha de presentación (Ejemplo: 28/02/2026):"
                    enviar_mensaje_telegram(texto_respuesta, botones={"force_reply": True})
            
            # Si escribiste un texto...
            elif "message" in item and "text" in item["message"]:
                msg = item["message"]
                texto = msg["text"].strip()
                
                # Verificamos si estás respondiendo a la pregunta de la fecha
                if "reply_to_message" in msg:
                    texto_bot = msg["reply_to_message"].get("text", "")
                    if "Vas a agendar el cargo" in texto_bot:
                        try:
                            # Extraemos el ID del cargo de la pregunta que te hizo el bot
                            id_cargo = texto_bot.split("cargo ")[1].split(".")[0]
                            
                            # Verificamos que la fecha esté bien escrita
                            if re.match(r"^\d{2}/\d{2}/\d{4}$", texto):
                                agendados.append({"id": id_cargo, "fecha": texto})
                                enviar_mensaje_telegram(f"✅ ¡Listo el pollo! Agendé el cargo <b>{id_cargo}</b> para el <b>{texto}</b>.\n\n⏰ Quedate tranquilo que te hago acordar el día anterior a las 20:00 hs.")
                            else:
                                enviar_mensaje_telegram("❌ Mmm, me parece que escribiste mal la fecha. Acordate que tiene que ser con este formato: DD/MM/YYYY (ejemplo: 02/03/2026).")
                        except Exception as e:
                            print("Error procesando fecha", e)
except Exception as e:
    print(f"Error en Telegram Updates: {e}")

# --- 2. RECORDATORIO DE AGENDA (A las 20:00 hs AR) ---
if ahora_ar.hour == 20:
    mañana = ahora_ar + timedelta(days=1)
    fecha_mañana = mañana.strftime("%d/%m/%Y")
    
    for cargo in agendados:
        if cargo.get("fecha") == fecha_mañana:
            mensaje_agenda = (
                f"⏰ <b>¡HOLA MARCOS! RECORDATORIO PARA MAÑANA</b> ⏰\n\n"
                f"Mañana (<b>{fecha_mañana}</b>) tenés designación para este cargo:\n"
                f"🆔 <code>{cargo['id']}</code>\n\n"
                f"📍 ¡Prepará tus cosas y que sea con muchos éxitos!"
            )
            enviar_mensaje_telegram(mensaje_agenda)
            time.sleep(2)

# --- 3. REVISAR EL SIME ---
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
                    print(f"Entrando al detalle de: {id_tramite}")
                    
                    boton_detalle = fila.find_element(By.XPATH, ".//a[contains(text(), 'Ver Detalle')] | .//button[contains(text(), 'Ver Detalle')] | .//*[contains(text(), 'Ver Detalle')]")
                    driver.execute_script("arguments[0].click();", boton_detalle)
                    time.sleep(4)
                    
                    texto_detalle_original = driver.find_element(By.TAG_NAME, "body").text
                    texto_detalle_limpio = normalizar(texto_detalle_original)
                    
                    es_prioridad = False
                    palabras_clave =["JAURETCHE", "CRUZ ALTA", "BANDA DEL RIO SALI", "EVA PERON"]
                    
                    if any(palabra in texto_detalle_limpio for palabra in palabras_clave):
                        es_prioridad = True

                    # ARMAMOS LOS BOTONES INTERACTIVOS
                    botones_teclado = {
                        "inline_keyboard": [[{"text": "🔗 Postularme en SIME", "url": URL}],[{"text": "📅 Agendar este cargo", "callback_data": f"agendar_{id_tramite}"}]
                        ]
                    }

                    if es_prioridad:
                        mensaje = (
                            f"<b>🚨 ⭐ ¡ALERTA PRIORITARIA, COMPADRE! ⭐ 🚨</b>\n"
                            f"📍 <i>Detecté tus escuelas favoritas (Cruz Alta / Jauretche)</i>\n\n"
                            f"<b>Información del Cargo:</b>\n<code>{texto_detalle_original[:600]}...</code>"
                        )
                    else:
                        mensaje = (
                            f"<b>🍎 NUEVA VACANTE: MAESTRO DE GRADO</b>\n"
                            f"🆔 {id_tramite}\n\n"
                            f"<b>Detalles Generales:</b>\n<code>{texto_detalle_original[:400]}...</code>"
                        )
                    
                    enviar_mensaje_telegram(mensaje, botones=botones_teclado)
                    vistos.add(id_tramite)
                    procesado_alguno_nuevo = True
                    break 

        if not procesado_alguno_nuevo:
            break

    # --- GUARDAR TODO ---
    with open(archivo_vistos, "w") as f:
        for item in sorted(vistos):
            f.write(f"{item}\n")
            
    with open(archivo_agendados, "w") as f:
        json.dump(agendados, f)
        
    with open(archivo_offset, "w") as f:
        f.write(str(offset))

except Exception as e:
    print(f"Error General: {e}")
finally:
    driver.quit()
