"""
bot_github.py — Monitor SIME
La cabecera y lugar de designación están en el DETALLE de cada vacante,
no en la lista principal. El bot entra a cada PDVC nuevo y lee los comentarios.
"""

import time
import requests
import os
import json
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ── Config ────────────────────────────────────────────────────────────────────
TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
URL_BASE    = "https://sime.educaciontuc.gov.ar:8089"
URL_LISTA   = f"{URL_BASE}/Vacantes/Inscripcion#no-back-button"
URL_DETALLE = f"{URL_BASE}/Vacantes/Inscripcion"   # + ?id=PDVC-XXXXX
 
if not TOKEN or not CHAT_ID:
    print("❌ ERROR: Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")
    exit(1)

# ── Filtros ───────────────────────────────────────────────────────────────────
CARGO_KEYWORDS = ["MAESTRO DE GRADO"]

TURNO_KEYWORDS = [
    "TURNO MAÑANA", "TUMO MAÑANA", "T.MAÑANA",
    "T. MAÑANA", "# TM", "#TM", "TM]", "MAÑANA"
]

# Palabras clave que deben aparecer en los COMENTARIOS del detalle
# para saber que es de las cabeceras que te interesan
CABECERAS_KEYWORDS = [
    "CRUZ ALTA",
    "BANDA DEL RIO SALI",
    "BANDA DEL RÍO SALÍ",
    "BANDA DEL RIO SALÍ",
    "BURRUYACU",
    "BURRUYACÚ",
    "MARCOS PAZ 1425",
    "COLOMBRES",
    "DR. ARTURO AURETCHE",   # escuela de Cruz Alta / Banda
]

ARCHIVO_VISTOS    = "sime_vistos.txt"
ARCHIVO_HISTORIAL = "sime_historial.json"
ARCHIVO_ESTADO    = "sime_estado.json"

# ─────────────────────────────────────────────────────────────────────────────
def normalizar(texto):
    tabla = str.maketrans("ÁÉÍÓÚÜáéíóúü", "AEIOUUaeiouu")
    return texto.upper().translate(tabla)

CARGO_N    = [normalizar(c) for c in CARGO_KEYWORDS]
TURNO_N    = [normalizar(t) for t in TURNO_KEYWORDS]
CABECERAS_N = [normalizar(c) for c in CABECERAS_KEYWORDS]

def enviar_telegram(mensaje):
    url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    MAX = 4000
    for parte in [mensaje[i:i+MAX] for i in range(0, len(mensaje), MAX)]:
        try:
            r = requests.post(
                url_api,
                data={"chat_id": CHAT_ID, "text": parte, "parse_mode": "HTML"},
                timeout=10
            )
            if not r.ok:
                print(f"⚠️ Telegram error: {r.text}")
            time.sleep(0.5)
        except Exception as e:
            print(f"Error Telegram: {e}")

def cargar_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def guardar_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--log-level=3")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def es_cargo_manana(texto_fila):
    """Chequea cargo y turno en la fila de la lista."""
    t = normalizar(texto_fila)
    if "PDVC-" not in t:
        return False
    if not any(c in t for c in CARGO_N):
        return False
    if not any(turno in t for turno in TURNO_N):
        return False
    return True

def obtener_detalle(driver, id_tramite):
    """
    Entra a la página de detalle de la vacante.
    Devuelve (comentarios, texto_completo) o (None, None) si falla.
    """
    # La URL del detalle usa el código de trámite como parámetro
    url = f"{URL_BASE}/Vacantes/Inscripcion#{id_tramite}"
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(4)
        texto = driver.find_element(By.TAG_NAME, "body").text
        
        # Extraer la sección de comentarios
        match = re.search(r'Comentarios[:\s]*(.*?)(?:\n\n|\Z)', texto, re.IGNORECASE | re.DOTALL)
        comentarios = match.group(1).strip() if match else ""
        
        print(f"   📝 Comentarios: {comentarios[:150]!r}")
        return comentarios, texto
    except Exception as e:
        print(f"   ⚠️ Error obteniendo detalle de {id_tramite}: {e}")
        return None, None

def cabecera_en_comentarios(comentarios):
    """Devuelve la cabecera encontrada o None."""
    if not comentarios:
        return None
    c = normalizar(comentarios)
    return next((cab for cab in CABECERAS_N if cab in c), None)

# ── Cargar memoria ────────────────────────────────────────────────────────────
if os.path.exists(ARCHIVO_VISTOS):
    with open(ARCHIVO_VISTOS, "r") as f:
        vistos = set(line.strip() for line in f if line.strip())
else:
    vistos = set()

historial = cargar_json(ARCHIVO_HISTORIAL, {})
estado    = cargar_json(ARCHIVO_ESTADO, {})
ahora     = datetime.now()

print(f"🚀 Bot SIME iniciado — {ahora.strftime('%Y-%m-%d %H:%M UTC')}")
print(f"📂 Vacantes ya vistas: {len(vistos)}")

# ── Barrido ───────────────────────────────────────────────────────────────────
driver = None
nuevos = 0

try:
    driver = get_driver()
    driver.get(URL_LISTA)

    wait = WebDriverWait(driver, 40)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
    time.sleep(8)

    filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    filas = [f for f in filas if f.text.strip()]
    print(f"📋 Filas con contenido: {len(filas)}")

    # Prefiltramos: solo Maestro de Grado Turno Mañana, no vistos aún
    candidatos = []
    for fila in filas:
        texto = fila.text.strip()
        if not es_cargo_manana(texto):
            continue
        id_tramite = texto.split()[0]
        if id_tramite in vistos:
            continue
        candidatos.append((id_tramite, texto))

    print(f"🎯 Candidatos Maestro de Grado Mañana nuevos: {len(candidatos)}")

    # Para cada candidato, entramos al detalle a ver la cabecera
    for id_tramite, texto_fila in candidatos:
        print(f"\n🔍 Revisando detalle: {id_tramite}")

        comentarios, texto_detalle = obtener_detalle(driver, id_tramite)

        cabecera = cabecera_en_comentarios(comentarios)

        if not cabecera:
            print(f"   ⏭️  No es de las cabeceras buscadas. Comentarios: {(comentarios or '')[:100]!r}")
            # Lo marcamos como visto para no revisarlo de nuevo
            vistos.add(id_tramite)
            continue

        print(f"   ✨ COINCIDE con cabecera: {cabecera}")

        # Extraer fecha de designación de los comentarios para la alerta de vencimiento
        match_hora = re.search(r'(\d{2}:\d{2})\s*HS', normalizar(comentarios or ""))
        hora_desig = match_hora.group(1) + " hs" if match_hora else "ver detalle"

        # Extraer fecha de publicación de la fila
        match_fecha = re.search(r'(\d{2}/\d{2}/\d{4})', texto_fila)
        fecha_pub = match_fecha.group(1) if match_fecha else ""

        mensaje = (
            f"<b>🍎 ¡NUEVA VACANTE: MAESTRO DE GRADO!</b>\n\n"
            f"🏫 <code>{texto_fila[:200]}</code>\n\n"
            f"📍 <b>Cabecera:</b> {cabecera}\n"
            f"🌅 <b>Turno:</b> Mañana\n"
            f"🕘 <b>Hora designación:</b> {hora_desig}\n"
            f"📅 <b>Publicación:</b> {fecha_pub}\n\n"
            f"📝 <i>{(comentarios or '')[:300]}</i>\n\n"
            f"🔗 <a href='{URL_LISTA}'>Ir al SIME</a>"
        )

        enviar_telegram(mensaje)

        historial[id_tramite] = {
            "texto":       texto_fila,
            "comentarios": comentarios or "",
            "cabecera":    cabecera,
            "fecha":       ahora.strftime("%Y-%m-%d %H:%M"),
            "alerta_vencimiento_enviada": False,
        }

        vistos.add(id_tramite)
        estado["total_notificadas"] = estado.get("total_notificadas", 0) + 1
        nuevos += 1
        time.sleep(3)

    print(f"\n✅ Revisión completa. Nuevas vacantes notificadas: {nuevos}")

except Exception as e:
    print(f"❌ Error SIME: {e}")
    enviar_telegram(f"⚠️ <b>Error en bot SIME:</b> <code>{e}</code>")

finally:
    if driver:
        driver.quit()

# ── Guardar ───────────────────────────────────────────────────────────────────
estado["ultima_revision"] = ahora.strftime("%Y-%m-%d %H:%M")

with open(ARCHIVO_VISTOS, "w") as f:
    for item in sorted(vistos):
        f.write(f"{item}\n")

guardar_json(ARCHIVO_HISTORIAL, historial)
guardar_json(ARCHIVO_ESTADO, estado)
print("💾 Estado guardado.")
