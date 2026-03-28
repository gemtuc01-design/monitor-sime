import time
import requests
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURACIÓN (siempre desde variables de entorno) ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
URL = "https://sime.educaciontuc.gov.ar/Vacantes/Index#no-back-button"

if not TOKEN or not CHAT_ID:
    print("❌ ERROR: Faltan las variables de entorno TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")
    exit(1)

def enviar_telegram(mensaje):
    url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(
            url_api,
            data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"},
            timeout=10
        )
        if not r.ok:
            print(f"⚠️ Telegram respondió con error: {r.text}")
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

# --- MEMORIA: cargamos los ya vistos ---
archivo_vistos = "sime_vistos.txt"
if os.path.exists(archivo_vistos):
    with open(archivo_vistos, "r") as f:
        vistos = set(line.strip() for line in f if line.strip())
else:
    vistos = set()

print("🚀 Bot SIME iniciado (modo GitHub Actions — una sola pasada)...")

driver = None
nuevos_encontrados = 0

try:
    driver = get_driver()
    driver.get(URL)

    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
    time.sleep(5)

    filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    print(f"📋 Filas encontradas en la tabla: {len(filas)}")

    for fila in filas:
        texto = fila.text.strip()
        texto_upper = texto.upper()

        # FILTRO: vacante PDVC y Maestro de Grado
        if "PDVC-" in texto_upper and "MAESTRO DE GRADO" in texto_upper:
            id_tramite = texto.split()[0]

            if id_tramite not in vistos:
                print(f"✨ ¡MAESTRO DE GRADO DETECTADO!: {id_tramite}")

                mensaje = (
                    f"<b>🍎 ¡NUEVA VACANTE: MAESTRO DE GRADO!</b>\n\n"
                    f"<code>{texto}</code>\n\n"
                    f"🔗 <a href='{URL}'>Ir al SIME</a>"
                )

                enviar_telegram(mensaje)
                vistos.add(id_tramite)
                nuevos_encontrados += 1
                time.sleep(2)

    print(f"✅ Revisión SIME completa. Nuevas vacantes notificadas: {nuevos_encontrados}")

except Exception as e:
    print(f"❌ Error leyendo SIME: {e}")
    enviar_telegram(f"⚠️ <b>Error en bot SIME:</b> <code>{e}</code>")

finally:
    if driver:
        driver.quit()

# --- GUARDAR MEMORIA ---
with open(archivo_vistos, "w") as f:
    for item in sorted(vistos):
        f.write(f"{item}\n")
