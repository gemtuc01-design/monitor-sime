import time
import requests
import os
import re
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
URL_PRINCIPAL = "https://capacitaciondocente.educaciontuc.gov.ar/"

if not TOKEN or not CHAT_ID:
    print("❌ ERROR: Faltan las variables de entorno TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")
    exit(1)

def enviar_mensaje_telegram(mensaje):
    url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(
            url_api,
            json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"},
            timeout=10
        )
        if not r.ok:
            print(f"⚠️ Telegram respondió con error: {r.text}")
    except Exception as e:
        print(f"Error Telegram: {e}")

def normalizar(texto):
    reemplazos = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U"}
    t = texto.upper()
    for original, reemplazo in reemplazos.items():
        t = t.replace(original, reemplazo)
    return t

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--log-level=3")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

# --- MEMORIA DEL BOT DE CURSOS ---
archivo_vistos = "cursos_vistos.txt"
if os.path.exists(archivo_vistos):
    with open(archivo_vistos, "r") as f:
        vistos = set(line.strip() for line in f if line.strip())
else:
    vistos = set()

print("🚀 Bot Cursos iniciado (modo GitHub Actions — una sola pasada)...")

driver = None
nuevos_encontrados = 0

try:
    driver = get_driver()
    driver.get(URL_PRINCIPAL)

    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(5)

    # Buscamos todos los enlaces a cursos específicos
    enlaces = driver.find_elements(By.XPATH, "//a[contains(@href, '/capacitaciones/')]")
    urls_cursos = set(e.get_attribute("href") for e in enlaces if e.get_attribute("href"))
    print(f"📋 Cursos encontrados en el portal: {len(urls_cursos)}")

    for url_curso in urls_cursos:
        match_id = re.search(r'/capacitaciones/([^/?#]+)', url_curso)
        id_curso = match_id.group(1) if match_id else url_curso.split('/')[-1][:20]

        if id_curso not in vistos:
            print(f"🔍 Revisando curso nuevo: {id_curso}")
            try:
                driver.get(url_curso)
                time.sleep(4)

                texto_pagina = driver.find_element(By.TAG_NAME, "body").text
                texto_norm = normalizar(texto_pagina)

                # FILTRO: Solo nivel Primario
                if "PRIMARI" in texto_norm:

                    # Título
                    try:
                        titulo = driver.find_element(By.TAG_NAME, "h1").text.strip()
                        if not titulo:
                            raise ValueError("h1 vacío")
                    except:
                        titulo = "Curso de Capacitación"

                    # Inicio Preinscripción
                    match_inicio = re.search(
                        r'Inicio\s+Preinscripci[oó]n\s*[:\-]?\s*([\d/\s:\w]+?hs)',
                        texto_pagina, re.IGNORECASE
                    )
                    inicio_pre = match_inicio.group(1).strip() if match_inicio else "¡Revisar en la web!"

                    # Estado
                    match_estado = re.search(r'Estado\s*[:\-]?\s*([A-Za-záéíóúÁÉÍÓÚ\s]+)', texto_pagina)
                    estado = match_estado.group(1).strip() if match_estado else "Desconocido"

                    mensaje = (
                        f"<b>🎓 ¡NUEVO CURSO INFoD / FORMAR!</b>\n\n"
                        f"📚 <b>{titulo}</b>\n\n"
                        f"🎯 <b>Nivel detectado:</b> Primario\n"
                        f"🗓️ <b>Apertura de Inscripción:</b>\n<code>{inicio_pre}</code>\n"
                        f"📊 <b>Estado:</b> <i>{estado}</i>\n\n"
                        f"🔗 <a href='{url_curso}'>¡ENTRAR AL CURSO ACÁ!</a>"
                    )

                    enviar_mensaje_telegram(mensaje)
                    nuevos_encontrados += 1
                    print(f"✅ Notificado: {titulo}")
                else:
                    print(f"⏭️  Curso {id_curso} no es de nivel Primario, descartado.")

            except Exception as e_curso:
                print(f"⚠️ Error procesando curso {id_curso}: {e_curso}")

            # Marcar como visto siempre (sea Primario o no)
            vistos.add(id_curso)

    print(f"✅ Revisión completa. Nuevos cursos Primario notificados: {nuevos_encontrados}")

except Exception as e:
    print(f"❌ Error en bot de cursos: {e}")
    enviar_telegram(f"⚠️ <b>Error en bot Cursos:</b> <code>{e}</code>")

finally:
    if driver:
        driver.quit()

# --- GUARDAR MEMORIA ---
with open(archivo_vistos, "w") as f:
    for item in sorted(vistos):
        f.write(f"{item}\n")
