import time
import requests
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
URL_PRINCIPAL = "https://capacitaciondocente.educaciontuc.gov.ar/"

def enviar_mensaje_telegram(mensaje):
    url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    requests.post(url_api, json=payload)

def normalizar(texto):
    reemplazos = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ü": "U"}
    t = texto.upper()
    for original, reemplazo in reemplazos.items():
        t = t.replace(original, reemplazo)
    return t

# --- MEMORIA DEL BOT DE CURSOS ---
archivo_vistos = "cursos_vistos.txt"
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
    print("Revisando portal de Capacitación Docente...")
    driver.get(URL_PRINCIPAL)
    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(5)

    # 1. Buscamos TODOS los enlaces que lleven a un curso específico
    enlaces = driver.find_elements(By.XPATH, "//a[contains(@href, '/capacitaciones/')]")
    
    # Extraemos las URLs limpias para que no haya duplicados
    urls_cursos = set([e.get_attribute("href") for e in enlaces if e.get_attribute("href")])

    for url_curso in urls_cursos:
        # Extraemos el ID único del curso desde la URL (Ejemplo: AJ6NOpJ7)
        match_id = re.search(r'/capacitaciones/([^/]+)', url_curso)
        id_curso = match_id.group(1) if match_id else url_curso.split('/')[-1][:20]

        # Si el curso es nuevo y no lo vimos antes
        if id_curso not in vistos:
            print(f"Entrando al detalle del curso: {id_curso}")
            driver.get(url_curso)
            time.sleep(4) # Esperamos que cargue la página del curso

            # Leemos TODO lo que dice adentro de la página
            texto_pagina = driver.find_element(By.TAG_NAME, "body").text
            texto_norm = normalizar(texto_pagina)

            # --- FILTRO ESTRICTO: SOLO NIVEL PRIMARIO ---
            if "PRIMARI" in texto_norm:
                
                # 1. Extraer Título (Suele estar arriba grande)
                try:
                    titulo = driver.find_element(By.TAG_NAME, "h1").text
                except:
                    titulo = "Curso de Capacitación"

                # 2. Extraer Hora Mágica de "Inicio Preinscripción"
                match_inicio = re.search(r'Inicio Preinscripción\s*(.*?hs)', texto_pagina, re.IGNORECASE)
                inicio_pre = match_inicio.group(1).strip() if match_inicio else "¡Revisar en la web!"

                # 3. Extraer "Estado"
                match_estado = re.search(r'Estado\s*([A-Z\s]+)', texto_pagina)
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

            # --- TRUCO DE MEMORIA ---
            # Guardamos el ID en "vistos" INCLUSO SI ES DE SECUNDARIA.
            # Así el bot sabe que ya lo analizó, lo descarta, y no vuelve a entrar
            # a perder el tiempo en las próximas revisiones.
            vistos.add(id_curso)

    # --- GUARDAR MEMORIA DE CURSOS ---
    with open(archivo_vistos, "w") as f:
        for item in sorted(vistos):
            f.write(f"{item}\n")

except Exception as e:
    print(f"Error en bot de cursos: {e}")
finally:
    driver.quit()
