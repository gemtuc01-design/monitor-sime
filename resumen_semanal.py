import time
import requests
import os
from datetime import datetime, timedelta
from collections import defaultdict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURACIÓN ---
TOKEN   = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
URL     = "https://sime.educaciontuc.gov.ar/Vacantes/Index#no-back-button"

if not TOKEN or not CHAT_ID:
    print("❌ ERROR: Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")
    exit(1)

# ── Filtros (idénticos al bot principal) ─────────────────────────────────────
CARGO = "MAESTRO DE GRADO"
TURNO = "MAÑANA"
CABECERAS = [
    "CRUZ ALTA",
    "BANDA DEL RIO SALI",
    "BANDA DEL RÍO SALÍ",
    "BURRUYACU",
    "BURRUYACÚ",
    "MARCOS PAZ",
    "COLOMBRES",
    "DR MARCOS PAZ 1425",
    "RAUL COLOMBRES",
    "RAÚL COLOMBRES",
]
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
    partes = [mensaje[i:i+MAX] for i in range(0, len(mensaje), MAX)]
    for parte in partes:
        try:
            r = requests.post(
                url_api,
                data={"chat_id": CHAT_ID, "text": parte, "parse_mode": "HTML"},
                timeout=10
            )
            if not r.ok:
                print(f"⚠️ Telegram error: {r.text}")
            time.sleep(1)
        except Exception as e:
            print(f"Error Telegram: {e}")

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

# ─────────────────────────────────────────────────────────────────────────────
print("🔍 Iniciando resumen semanal SIME...")

hoy    = datetime.now()
lunes  = hoy - timedelta(days=hoy.weekday())
domingo = lunes + timedelta(days=6)
rango  = f"{lunes.strftime('%d/%m')} al {domingo.strftime('%d/%m/%Y')}"

driver = None
por_cabecera = defaultdict(list)

try:
    driver = get_driver()
    driver.get(URL)

    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
    time.sleep(5)

    filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    print(f"📋 Total filas: {len(filas)}")

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

        por_cabecera[cabecera_match].append(texto)

except Exception as e:
    print(f"❌ Error: {e}")
    enviar_telegram(f"⚠️ <b>Error en resumen semanal:</b> <code>{e}</code>")
    exit(1)
finally:
    if driver:
        driver.quit()

# ── Armar mensaje ─────────────────────────────────────────────────────────────
total = sum(len(v) for v in por_cabecera.values())

mensaje = (
    f"<b>📊 RESUMEN SEMANAL SIME</b>\n"
    f"🗓️ Semana del {rango}\n"
    f"🕐 {hoy.strftime('%d/%m/%Y %H:%M')} hs\n"
    f"🎯 Maestro de Grado | Turno Mañana\n"
    f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
)

if total == 0:
    mensaje += "😴 <i>Sin vacantes para las cabeceras seleccionadas esta semana.</i>\n"
else:
    for cab in sorted(por_cabecera.keys()):
        items = por_cabecera[cab]
        mensaje += f"📍 <b>{cab}</b> — {len(items)} vacante(s)\n"
        mensaje += "─────────────────────\n"
        for v in items:
            mensaje += f"<code>{v}</code>\n\n"

mensaje += (
    f"━━━━━━━━━━━━━━━━━━━━━━\n"
    f"📌 <b>Total:</b> {total} vacante(s)\n"
    f"🔗 <a href='{URL}'>Ver SIME completo</a>"
)

enviar_telegram(mensaje)
print(f"📨 Resumen enviado. Total vacantes: {total}")
