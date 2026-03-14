import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURACIÓN ---
TOKEN = "8203580734:AAFXpNjy9tFuLVQpyxYn6owDd2bmS73f09k"
CHAT_ID = 1403512312
URL = "https://sime.educaciontuc.gov.ar/Vacantes/Index#no-back-button"

def enviar_telegram(mensaje):
    url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url_api, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Error Telegram: {e}")

options = Options()
options.add_argument("--headless") 
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage") # Clave para que no se rompa en GitHub
options.add_argument("--disable-gpu")
options.add_argument("--log-level=3")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

vistos = set()

print("🚀 Monitor SIME iniciado con Chrome...")
enviar_telegram("🎯 <b>Monitor Reiniciado:</b> Buscando vacantes de <u>Maestro de Grado</u>.")

while True:
    driver = None
    try:
        # Usamos Chrome, el estándar en la nube
        driver = webdriver.Chrome(options=options)
        driver.get(URL)
        
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
        
        time.sleep(5) 

        filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        
        for fila in filas:
            texto = fila.text.strip()
            texto_upper = texto.upper()
            
            # FILTRO DOBLE: Que sea vacante (PDVC) Y que sea Maestro de Grado
            if "PDVC-" in texto_upper and "MAESTRO DE GRADO" in texto_upper:
                id_tramite = texto.split()[0] 
                
                if id_tramite not in vistos:
                    print(f"✨ ¡MAESTRO DE GRADO DETECTADO!: {id_tramite}")
                    
                    mensaje_lindo = (
                        f"<b>🍎 ¡NUEVA VACANTE: MAESTRO DE GRADO!</b>\n\n"
                        f"<code>{texto}</code>\n\n"
                        f"🔗 <a href='{URL}'>Ir al SIME</a>"
                    )
                    
                    enviar_telegram(mensaje_lindo)
                    vistos.add(id_tramite)
                    time.sleep(2)

        print(f"✅ Revisión completa: {time.strftime('%H:%M:%S')}. (En espera...)")

    except Exception as e:
        print(f"❌ Error leyendo SIME: {e}")
    
    finally:
        if driver:
            driver.quit()

    # Revisa cada 10 minutos
    time.sleep(600)
