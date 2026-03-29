"""
bot_github.py — Monitor SIME con todas las funciones
- Alerta inmediata de vacantes nuevas
- Historial persistente en JSON
- Alerta de vencimiento próximo
- Heartbeat diario
- Responde comandos de Telegram: /resumen, /estado, /historial
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

# ── Configuración ─────────────────────────────────────────────────────────────
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

# ── Archivos de estado ────────────────────────────────────────────────────────
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

# ── Telegram ──────────────────────────────────────────────────────────────────
def enviar_telegram(mensaje, parse_mode="HTML"):
    url_api = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    MAX = 4000
    partes = [mensaje[i:i+MAX] for i in range(0, len(mensaje), MAX)]
    for parte in partes:
        try:
            r = requests.post(
                url_api,
                data={"chat_id": CHAT_ID, "text": parte, "parse_mode": parse_mode},
                timeout=10
            )
            if not r.ok:
                print(f"⚠️ Telegram error: {r.text}")
            time.sleep(0.5)
        except Exception as e:
            print(f"Error Telegram: {e}")

def get_updates(offset=None):
    """Lee los comandos pendientes del bot de Telegram."""
    url_api = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 2}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(url_api, params=params, timeout=10)
        if r.ok:
            return r.json().get("result", [])
    except:
        pass
    return []

# ── Selenium ──────────────────────────────────────────────────────────────────
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

# ── Historial ─────────────────────────────────────────────────────────────────
def cargar_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_historial(historial):
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)

def cargar_estado():
    if os.path.exists(ARCHIVO_ESTADO):
        with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"ultima_revision": None, "total_notificadas": 0, "ultimo_update_id": 0}

def guardar_estado(estado):
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)

# ── Comandos de Telegram ───────────────────────────────────────────────────────
def procesar_comando(texto, historial):
    cmd = texto.strip().lower().split()[0]

    if cmd == "/estado":
        estado = cargar_estado()
        ultima = estado.get("ultima_revision") or "nunca"
        total  = estado.get("total_notificadas", 0)
        enviar_telegram(
            f"<b>🤖 Estado del Bot SIME</b>\n\n"
            f"✅ Bot activo y funcionando\n"
            f"🕐 Última revisión: <code>{ultima}</code>\n"
            f"📊 Total vacantes notificadas: <b>{total}</b>\n"
            f"🎯 Filtro: {CARGO} | Turno Mañana\n"
            f"📍 Cabeceras monitoreadas: {len(CABECERAS)}"
        )

    elif cmd == "/resumen":
        # Resumen de la semana actual desde el historial
        hoy   = datetime.now()
        lunes = (hoy - timedelta(days=hoy.weekday())).strftime("%Y-%m-%d")
        semana_actual = {
            k: v for k, v in historial.items()
            if v.get("fecha", "") >= lunes
        }
        if not semana_actual:
            enviar_telegram("😴 <i>No hay vacantes registradas esta semana todavía.</i>")
            return

        por_cab = defaultdict(list)
        for id_t, datos in semana_actual.items():
            por_cab[datos.get("cabecera", "OTRA")].append(datos)

        msg = (
            f"<b>📊 Resumen semana actual</b>\n"
            f"🗓️ Desde el {lunes}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        total = 0
        for cab in sorted(por_cab.keys()):
            items = por_cab[cab]
            msg += f"📍 <b>{cab}</b> — {len(items)} vacante(s)\n"
            msg += "─────────────────────\n"
            for v in items:
                msg += f"<code>{v['texto']}</code>\n"
                msg += f"<i>Detectada: {v.get('fecha','?')}</i>\n\n"
            total += len(items)
        msg += f"━━━━━━━━━━━━━━━━━━━━━━\n📌 <b>Total: {total}</b>"
        enviar_telegram(msg)

    elif cmd == "/historial":
        # Últimas 20 vacantes de todo el historial
        if not historial:
            enviar_telegram("📭 <i>El historial está vacío.</i>")
            return
        ultimas = sorted(historial.values(), key=lambda x: x.get("fecha",""), reverse=True)[:20]
        msg = "<b>📋 Últimas 20 vacantes registradas</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for v in ultimas:
            msg += f"📍 <b>{v.get('cabecera','?')}</b> — <i>{v.get('fecha','?')}</i>\n"
            msg += f"<code>{v['texto']}</code>\n\n"
        enviar_telegram(msg)

    else:
        enviar_telegram(
            "<b>🤖 Comandos disponibles:</b>\n\n"
            "/estado — Ver si el bot está activo\n"
            "/resumen — Vacantes de esta semana\n"
            "/historial — Últimas 20 vacantes registradas"
        )

# ── Heartbeat diario ──────────────────────────────────────────────────────────
def enviar_heartbeat(total_hoy, total_historico):
    hora = datetime.now().strftime("%d/%m/%Y %H:%M")
    enviar_telegram(
        f"<b>💓 Bot SIME — Reporte diario</b>\n\n"
        f"✅ Funcionando correctamente\n"
        f"🕐 Hora: <code>{hora}</code>\n"
        f"📬 Vacantes nuevas hoy: <b>{total_hoy}</b>\n"
        f"📊 Total histórico: <b>{total_historico}</b>\n"
        f"🎯 Maestro de Grado | Turno Mañana\n\n"
        f"<i>Próxima revisión en 30 minutos.</i>"
    )

# ── Alerta de vencimiento ─────────────────────────────────────────────────────
def chequear_vencimientos(historial):
    """
    Si una vacante tiene una fecha de cierre detectada en el texto
    y vence en las próximas 3 horas, manda alerta.
    """
    ahora = datetime.now()
    for id_t, datos in historial.items():
        if datos.get("alerta_vencimiento_enviada"):
            continue
        texto = datos.get("texto", "")
        # Buscamos patrones de fecha como 28/03/2026 o 28-03-2026
        match = re.search(r'(\d{2})[/-](\d{2})[/-](\d{4})', texto)
        if not match:
            continue
        try:
            fecha_cierre = datetime(
                int(match.group(3)),
                int(match.group(2)),
                int(match.group(1))
            )
            horas_restantes = (fecha_cierre - ahora).total_seconds() / 3600
            if 0 < horas_restantes <= 3:
                enviar_telegram(
                    f"⏰ <b>¡VACANTE POR VENCER!</b>\n\n"
                    f"Quedan menos de 3 horas para el cierre:\n\n"
                    f"<code>{texto}</code>\n\n"
                    f"🔗 <a href='{URL}'>Ir al SIME ahora</a>"
                )
                datos["alerta_vencimiento_enviada"] = True
        except:
            continue

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

# Cargar memoria
if os.path.exists(ARCHIVO_VISTOS):
    with open(ARCHIVO_VISTOS, "r") as f:
        vistos = set(line.strip() for line in f if line.strip())
else:
    vistos = set()

historial = cargar_historial()
estado    = cargar_estado()
hora_actual = datetime.now()
hora_str    = hora_actual.strftime("%H:%M")
es_heartbeat = hora_actual.strftime("%H") == "11"  # 08:00 ART = 11:00 UTC

print(f"🚀 Bot SIME iniciado — {hora_str}")

# ── 1. Procesar comandos pendientes de Telegram ───────────────────────────────
print("📨 Revisando comandos de Telegram...")
ultimo_update_id = estado.get("ultimo_update_id", 0)
updates = get_updates(offset=ultimo_update_id + 1 if ultimo_update_id else None)

for update in updates:
    uid = update.get("update_id", 0)
    if uid > ultimo_update_id:
        ultimo_update_id = uid
    msg = update.get("message", {})
    texto_cmd = msg.get("text", "")
    if texto_cmd.startswith("/"):
        print(f"  Comando recibido: {texto_cmd}")
        procesar_comando(texto_cmd, historial)

estado["ultimo_update_id"] = ultimo_update_id

# ── 2. Barrido del SIME ───────────────────────────────────────────────────────
driver = None
nuevos_esta_ejecucion = 0

try:
    driver = get_driver()
    driver.get(URL)

    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr td")))
    time.sleep(5)

    filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    print(f"📋 Filas en tabla: {len(filas)}")

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

        # Notificar
        enviar_telegram(
            f"<b>🍎 ¡NUEVA VACANTE: MAESTRO DE GRADO!</b>\n\n"
            f"📋 <code>{texto}</code>\n\n"
            f"📍 <b>Cabecera:</b> {cabecera_match}\n"
            f"🌅 <b>Turno:</b> Mañana\n\n"
            f"🔗 <a href='{URL}'>Ir al SIME</a>"
        )

        # Guardar en historial
        historial[id_tramite] = {
            "texto":     texto,
            "cabecera":  cabecera_match,
            "fecha":     hora_actual.strftime("%Y-%m-%d %H:%M"),
            "alerta_vencimiento_enviada": False,
        }

        vistos.add(id_tramite)
        nuevos_esta_ejecucion += 1
        estado["total_notificadas"] = estado.get("total_notificadas", 0) + 1
        time.sleep(2)

    print(f"✅ Barrido completo. Nuevas vacantes: {nuevos_esta_ejecucion}")

except Exception as e:
    print(f"❌ Error SIME: {e}")
    enviar_telegram(f"⚠️ <b>Error en bot SIME:</b> <code>{e}</code>")

finally:
    if driver:
        driver.quit()

# ── 3. Chequear vencimientos ──────────────────────────────────────────────────
chequear_vencimientos(historial)

# ── 4. Heartbeat diario (una vez por día a las 08:00 ART) ────────────────────
if es_heartbeat:
    print("💓 Enviando heartbeat diario...")
    enviar_heartbeat(nuevos_esta_ejecucion, estado.get("total_notificadas", 0))

# ── 5. Guardar todo ───────────────────────────────────────────────────────────
estado["ultima_revision"] = hora_actual.strftime("%Y-%m-%d %H:%M")

with open(ARCHIVO_VISTOS, "w") as f:
    for item in sorted(vistos):
        f.write(f"{item}\n")

guardar_historial(historial)
guardar_estado(estado)

print("💾 Estado guardado correctamente.")
