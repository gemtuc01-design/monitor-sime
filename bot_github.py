"""
bot_github.py — Monitor SIME con detección robusta de tabla
"""

import time
import requests
import os
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict
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
URL     = "https://sime.educaciontuc.gov.ar/Vacantes/Index#no-back-button"

if not TOKEN or not CHAT_ID:
    print("❌ ERROR: Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")
    exit(1)

# ── Filtros ───────────────────────────────────────────────────────────────────
CARGO = "MAESTRO DE GRADO"
TURNO = "MAÑANA"
CABECERAS = [
    "CRUZ ALTA", "BANDA DEL RIO SALI", "BANDA DEL RÍO SALÍ",
    "BURRUYACU", "BURRUYACÚ", "MARCOS PAZ", "COLOMBRES",
    "DR MARCOS PAZ 1425", "RAUL COLOMBRES", "RAÚL COLOMBRES",
]

ARCHIVO_VISTOS    = "sime_vistos.txt"
ARCHIVO_HISTORIAL = "sime_historial.json"
ARCHIVO_ESTADO    = "sime_estado.json"

# ─────────────────────────────────────────────────────────────────────────────
def normalizar(texto):
    tabla = str.maketrans("ÁÉÍÓÚÜáéíóúü", "AEIOUUaeiouu")
    return texto.upper().translate(tabla)

CARGO_N     = normalizar(CARGO)
TURNO_N     = normalizar(TURNO)
CABECERAS_N = [normalizar(c) for c in CABECERAS]

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

def obtener_filas(driver):
    """
    Intenta obtener las filas de la tabla con múltiples estrategias.
    Devuelve la lista de filas y el método que funcionó.
    """
    wait = WebDriverWait(driver, 40)

    # Estrategia 1: selector estándar con espera explícita
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
        time.sleep(6)
        filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        filas = [f for f in filas if f.text.strip()]
        if filas:
            print(f"✅ Estrategia 1 OK: {len(filas)} filas")
            return filas, "CSS table tbody tr"
    except Exception as e:
        print(f"⚠️ Estrategia 1 falló: {e}")

    # Estrategia 2: esperar más tiempo y reintentar
    print("⏳ Estrategia 2: esperando 15s adicionales...")
    time.sleep(15)
    try:
        filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        filas = [f for f in filas if f.text.strip()]
        if filas:
            print(f"✅ Estrategia 2 OK: {len(filas)} filas")
            return filas, "CSS con espera extra"
    except Exception as e:
        print(f"⚠️ Estrategia 2 falló: {e}")

    # Estrategia 3: buscar cualquier <tr> en la página
    try:
        filas = driver.find_elements(By.TAG_NAME, "tr")
        filas = [f for f in filas if f.text.strip() and "PDVC" in f.text.upper()]
        if filas:
            print(f"✅ Estrategia 3 OK: {len(filas)} filas con PDVC")
            return filas, "TAG tr filtrado por PDVC"
    except Exception as e:
        print(f"⚠️ Estrategia 3 falló: {e}")

    # Estrategia 4: buscar por XPath
    try:
        filas = driver.find_elements(By.XPATH, "//tr[contains(., 'PDVC')]")
        filas = [f for f in filas if f.text.strip()]
        if filas:
            print(f"✅ Estrategia 4 OK: {len(filas)} filas por XPath")
            return filas, "XPath PDVC"
    except Exception as e:
        print(f"⚠️ Estrategia 4 falló: {e}")

    # Estrategia 5: leer todo el body como texto y extraer líneas con PDVC
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        lineas = [l.strip() for l in body_text.splitlines() if "PDVC-" in l.upper() and l.strip()]
        if lineas:
            print(f"✅ Estrategia 5 OK: {len(lineas)} líneas con PDVC en body")
            # Devolvemos objetos simulados con .text
            class FakeRow:
                def __init__(self, t): self.text = t
            return [FakeRow(l) for l in lineas], "body text parse"
    except Exception as e:
        print(f"⚠️ Estrategia 5 falló: {e}")

    return [], "ninguna"

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
    print(f"🌐 Cargando: {URL}")
    driver.get(URL)
    time.sleep(8)

    # Diagnóstico: capturar estado de la página
    titulo = driver.title
    body_preview = driver.find_element(By.TAG_NAME, "body").text[:300]
    print(f"📄 Título de página: {titulo!r}")
    print(f"📄 Preview body:\n{body_preview}\n---")

    # Contar todos los elementos de tabla para diagnóstico
    todas_tablas = driver.find_elements(By.TAG_NAME, "table")
    print(f"🔍 Tablas encontradas en la página: {len(todas_tablas)}")
    for i, tabla in enumerate(todas_tablas[:3]):
        filas_tabla = tabla.find_elements(By.TAG_NAME, "tr")
        print(f"   Tabla {i+1}: {len(filas_tabla)} filas")

    # Obtener filas con estrategia múltiple
    filas, metodo = obtener_filas(driver)
    print(f"📋 Filas válidas obtenidas: {len(filas)} (método: {metodo})")

    if len(filas) == 0:
        msg_diag = (
            f"⚠️ <b>Bot SIME: 0 filas encontradas</b>\n\n"
            f"Título página: <code>{titulo}</code>\n"
            f"Preview:\n<code>{body_preview[:200]}</code>\n\n"
            f"Tablas en página: {len(todas_tablas)}"
        )
        enviar_telegram(msg_diag)

    for fila in filas:
        texto = fila.text.strip()
        if not texto:
            continue
        t = normalizar(texto)

        if "PDVC-" not in t:
            continue
        if CARGO_N not in t:
            continue
        if TURNO_N not in t:
            continue

        cabecera_match = next((c for c in CABECERAS_N if c in t), None)
        if not cabecera_match:
            continue

        id_tramite = texto.split()[0]
        if id_tramite in vistos:
            continue

        print(f"✨ NUEVA VACANTE: {id_tramite} | {cabecera_match}")

        enviar_telegram(
            f"<b>🍎 ¡NUEVA VACANTE: MAESTRO DE GRADO!</b>\n\n"
            f"📋 <code>{texto}</code>\n\n"
            f"📍 <b>Cabecera:</b> {cabecera_match}\n"
            f"🌅 <b>Turno:</b> Mañana\n\n"
            f"🔗 <a href='{URL}'>Ir al SIME</a>"
        )

        historial[id_tramite] = {
            "texto":    texto,
            "cabecera": cabecera_match,
            "fecha":    ahora.strftime("%Y-%m-%d %H:%M"),
            "alerta_vencimiento_enviada": False,
        }

        vistos.add(id_tramite)
        estado["total_notificadas"] = estado.get("total_notificadas", 0) + 1
        nuevos += 1
        time.sleep(2)

    print(f"✅ Revisión completa. Nuevas vacantes: {nuevos}")

except Exception as e:
    print(f"❌ Error SIME: {e}")
    enviar_telegram(f"⚠️ <b>Error en bot SIME:</b> <code>{e}</code>")

finally:
    if driver:
        driver.quit()

# ── Guardar todo ──────────────────────────────────────────────────────────────
estado["ultima_revision"] = ahora.strftime("%Y-%m-%d %H:%M")

with open(ARCHIVO_VISTOS, "w") as f:
    for item in sorted(vistos):
        f.write(f"{item}\n")

guardar_json(ARCHIVO_HISTORIAL, historial)
guardar_json(ARCHIVO_ESTADO, estado)
print("💾 Estado guardado.")
