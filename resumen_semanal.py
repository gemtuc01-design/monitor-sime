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
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
URL = "https://sime.educaciontuc.gov.ar/Vacantes/Index#no-back-button"

# Cargos a monitorear (agregá más si necesitás)
CARGOS_BUSCADOS = [
    "MAESTRO DE GRADO",
]

if not TOKEN or not CHAT_ID:
    print("❌ ERROR: Faltan las variables de entorno TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")
    exit(1)

def enviar_telegram(mensaje):
    """Envía un mensaje a Telegram. Si supera los 4096 chars lo parte en trozos."""
    url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    # Telegram tiene límite de 4096 caracteres por mensaje
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
                print(f"⚠️ Telegram respondió con error: {r.text}")
            time.sleep(1)  # pequeña pausa entre mensajes
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

# ─────────────────────────────────────────────
# BARRIDO COMPLETO
# ─────────────────────────────────────────────
print("🔍 Iniciando barrido semanal del SIME...")

driver = None
# Diccionario: cargo → lista de filas encontradas
resultados = defaultdict(list)
total_filas = 0

# Calculamos el rango de la semana para el encabezado
hoy = datetime.now()
lunes = hoy - timedelta(days=hoy.weekday())
domingo = lunes + timedelta(days=6)
rango_semana = f"{lunes.strftime('%d/%m')} al {domingo.strftime('%d/%m/%Y')}"

try:
    driver = get_driver()
    driver.get(URL)

    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
    time.sleep(5)

    filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    total_filas = len(filas)
    print(f"📋 Total de filas en la tabla: {total_filas}")

    for fila in filas:
        texto = fila.text.strip()
        if not texto:
            continue
        texto_upper = texto.upper()

        # Solo procesamos vacantes (PDVC-)
        if "PDVC-" not in texto_upper:
            continue

        # Clasificamos por cargo buscado
        for cargo in CARGOS_BUSCADOS:
            if cargo in texto_upper:
                resultados[cargo].append(texto)
                break  # una fila solo cuenta para un cargo

    print(f"✅ Barrido completo.")
    for cargo, items in resultados.items():
        print(f"   {cargo}: {len(items)} vacante(s)")

except Exception as e:
    print(f"❌ Error durante el barrido: {e}")
    enviar_telegram(f"⚠️ <b>Error en resumen semanal SIME:</b>\n<code>{e}</code>")
    exit(1)

finally:
    if driver:
        driver.quit()

# ─────────────────────────────────────────────
# ARMAR Y ENVIAR EL MENSAJE
# ─────────────────────────────────────────────
total_vacantes = sum(len(v) for v in resultados.values())

# Encabezado
mensaje = (
    f"<b>📊 RESUMEN SEMANAL SIME</b>\n"
    f"🗓️ Semana del {rango_semana}\n"
    f"🕐 Generado: {hoy.strftime('%d/%m/%Y %H:%M')} hs\n"
    f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
)

if total_vacantes == 0:
    mensaje += "😴 <i>No se encontraron vacantes para los cargos monitoreados esta semana.</i>\n"
else:
    for cargo in CARGOS_BUSCADOS:
        vacantes = resultados.get(cargo, [])
        emoji = "🍎" if "MAESTRO DE GRADO" in cargo else "📌"
        mensaje += f"{emoji} <b>{cargo}</b> — {len(vacantes)} vacante(s)\n"
        mensaje += "─────────────────────\n"

        if vacantes:
            for v in vacantes:
                # Mostramos la fila en formato código para que sea legible
                mensaje += f"<code>{v}</code>\n\n"
        else:
            mensaje += "<i>Sin vacantes esta semana.</i>\n\n"

# Pie
mensaje += (
    f"━━━━━━━━━━━━━━━━━━━━━━\n"
    f"📌 <b>Total vacantes encontradas:</b> {total_vacantes}\n"
    f"🔗 <a href='{URL}'>Ver SIME completo</a>"
)

enviar_telegram(mensaje)
print(f"📨 Resumen enviado a Telegram. Total vacantes: {total_vacantes}")
