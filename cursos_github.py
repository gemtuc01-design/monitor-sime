import time
import requests
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
URL = "https://capacitaciondocente.educaciontuc.gov.ar/"

def enviar_telegram(mensaje):
    url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url_api, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"})

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

archivo_vistos = "cursos_vistos.txt"
if os.path.exists(archivo_vistos):
    with open(archivo_vistos, "r") as f:
        vistos = set(line.strip() for line in f if line.strip())
else:
    vistos = set()

driver = webdriver.Chrome(options=options)
try:
    driver.get(URL)
    wait = WebDriverWait(driver, 40)
    # Esperamos a que carguen las ofertas de capacitación
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(5)

    # Buscamos elementos que contengan información de cursos
    # En esta web suelen ser títulos dentro de bloques o cards
    elementos = driver.find_elements(By.XPATH, "//h3 | //h4 | //h5 | //p")
    
    for el in elementos:
        texto = el.text.strip()
        texto_upper = texto.upper()
        
        # Filtro: Que mencione Primaria o Inicial
        if ("PRIMARIA" in texto_upper or "INICIAL" in texto_upper) and len(texto) > 10:
            if texto not in vistos:
                mensaje = (
                    f"<b>🎓 ¡NUEVA CAPACITACIÓN DETECTADA!</b>\n\n"
                    f"📚 <code>{texto}</code>\n\n"
                    f"🔗 <a href='{URL}'>Ir a Capacitación Docente</a>"
                )
                enviar_telegram(mensaje)
                vistos.add(texto)

    with open(archivo_vistos, "w") as f:
        for item in vistos:
            f.write(f"{item}\n")

except Exception as e:
    print(f"Error en cursos: {e}")
finally:
    driver.quit()
