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

def scroll_completo(driver):
    """Hace scroll hasta el fondo de la página para forzar la carga de todos los elementos."""
    ultima_altura = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        nueva_altura = driver.execute_script("return document.body.scrollHeight")
        if nueva_altura == ultima_altura:
            break
        ultima_altura = nueva_altura
    # Volvemos arriba
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

# --- MEMORIA ---
archivo_vistos = "cursos_vistos.txt"
if os.path.exists(archivo_vistos):
    with open(archivo_vistos, "r") as f:
        vistos = set(line.strip() for line in f if line.strip())
else:
    vistos = set()

print("🚀 Bot Cursos iniciado...")

driver = None
nuevos_encontrados = 0

try:
    driver = get_driver()
    driver.get(URL_PRINCIPAL)

    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    # Esperamos que cargue el JS inicial
    time.sleep(8)

    # Scroll completo para que carguen todos los cursos (lazy loading)
    print("📜 Haciendo scroll para cargar todos los cursos...")
    scroll_completo(driver)

    # Buscamos enlaces con el patrón correcto: /capacitaciones/{ID}/
    # Ejemplo: /capacitaciones/bmg6aX1M/nombre-del-curso
    enlaces = driver.find_elements(By.XPATH, "//a[contains(@href, '/capacitaciones/')]")
    
    # Usamos el ID (segundo segmento) como clave única, ignorando el slug de texto
    urls_por_id = {}
    for e in enlaces:
        href = e.get_attribute("href") or ""
        match = re.search(r'/capacitaciones/([^/?#]+)', href)
        if match:
            id_curso = match.group(1)
            # Normalizamos la URL quitando el hash (#) del final si lo tiene
            url_limpia = href.split('#')[0]
            urls_por_id[id_curso] = url_limpia

    print(f"📋 Cursos únicos encontrados: {len(urls_por_id)}")
    for id_c, url_c in list(urls_por_id.items())[:10]:
        print(f"   [{id_c}] {url_c}")

    if len(urls_por_id) == 0:
        body_preview = driver.find_element(By.TAG_NAME, "body").text[:400]
        print(f"⚠️ Sin cursos. Vista previa del body:\n{body_preview}")
        enviar_mensaje_telegram(
            f"⚠️ <b>Bot Cursos:</b> No se encontraron cursos en el portal.\n\n"
            f"<i>Vista previa:</i>\n<code>{body_preview[:300]}</code>"
        )

    for id_curso, url_curso in urls_por_id.items():

        if id_curso in vistos:
            continue

        print(f"🔍 Revisando curso nuevo: {id_curso}")
        try:
            driver.get(url_curso)
            time.sleep(5)

            texto_pagina = driver.find_element(By.TAG_NAME, "body").text
            texto_norm = normalizar(texto_pagina)

            # FILTRO: Solo nivel Primario
            if "PRIMARI" in texto_norm:

                # Título
                try:
                    titulo = driver.find_element(By.TAG_NAME, "h1").text.strip() or "Curso de Capacitación"
                except:
                    titulo = "Curso de Capacitación"

                # Inicio Preinscripción
                match_inicio = re.search(
                    r'Inicio\s+Preinscripci[oó]n\s*[:\-]?\s*([\d/\s:\w]+?hs)',
                    texto_pagina, re.IGNORECASE
                )
                inicio_pre = match_inicio.group(1).strip() if match_inicio else "¡Revisar en la web!"

                # Estado
                match_estado = re.search(
                    r'Estado\s*[:\-]?\s*([A-Za-záéíóúÁÉÍÓÚ\s]{3,30})',
                    texto_pagina
                )
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
                print(f"⏭️  Curso {id_curso} no es nivel Primario, descartado.")

        except Exception as e_curso:
            print(f"⚠️ Error procesando curso {id_curso}: {e_curso}")

        # Siempre marcamos como visto
        vistos.add(id_curso)

    print(f"✅ Revisión completa. Nuevos cursos Primario notificados: {nuevos_encontrados}")

except Exception as e:
    print(f"❌ Error en bot de cursos: {e}")
    enviar_mensaje_telegram(f"⚠️ <b>Error en bot Cursos:</b> <code>{e}</code>")

finally:
    if driver:
        driver.quit()

# --- GUARDAR MEMORIA ---
with open(archivo_vistos, "w") as f:
    for item in sorted(vistos):
        f.write(f"{item}\n")
