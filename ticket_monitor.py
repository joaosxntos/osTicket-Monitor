"""
ticket_monitor.py — Monitor de tickets osTicket com ícone na system tray
=========================================================================
- Ícone azul na barra de tarefas (junto ao relógio)
- Clique direito → menu com estado, pausar, verificar agora, abrir browser, sair
- Notificações Windows nativas clicáveis (abre o ticket no browser)
- Som de alerta do Windows
- Credenciais em config.json (nunca no código)
- Compatível com PyInstaller (.exe)

REQUISITOS:
  pip install -r requirements.txt

UTILIZAÇÃO:
  1. Preenche o config.json com as tuas credenciais
  2. python ticket_monitor.py  (ou double-click no .exe)
"""

import time
import json
import os
import sys
import logging
import threading
import webbrowser
import winsound
from dataclasses import dataclass
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem
from winotify import Notification, audio


# ─────────────────────────────────────────────
#  PATHS — funciona tanto em .py como em .exe
# ─────────────────────────────────────────────
def _base_path() -> str:
    if getattr(sys, "frozen", False):   # a correr como .exe (PyInstaller)
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_PATH   = _base_path()
CONFIG_FILE = os.path.join(BASE_PATH, "config.json")
STATE_FILE  = os.path.join(BASE_PATH, "seen_tickets.json")


# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  CARREGA config.json
# ─────────────────────────────────────────────
def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(
            f"Ficheiro 'config.json' não encontrado em:\n{BASE_PATH}\n\n"
            f"Cria-o com o seguinte conteúdo:\n"
            f'{{\n'
            f'    "base_url": "https://empresa.supportsystem.com",\n'
            f'    "username": "o_teu_utilizador",\n'
            f'    "password": "a_tua_password"\n'
            f'}}'
        )
    with open(CONFIG_FILE, encoding="utf-8") as f:
        creds = json.load(f)
    for field in ("base_url", "username", "password"):
        if not creds.get(field):
            raise ValueError(f"Campo '{field}' em falta ou vazio no config.json")

    base_url = creds["base_url"].rstrip("/")
    return {
        "base_url":    base_url,
        "login_url":   f"{base_url}/scp/login.php",
        "tickets_url": f"{base_url}/scp/tickets.php",
        "username":    creds["username"],
        "password":    creds["password"],

        "selectors": {
            "ticket_row": "tr:has(input[name='tids[]'])",
        },
        "login_fields": {
            "username_field": "userid",
            "password_field": "passwd",
        },

        # Intervalo entre verificações em segundos (120 = 2 minutos)
        "interval_seconds": 120,

        # Filtro de prioridade — deixa [] para notificar todas
        "notify_priorities": [],

        # Som: "default" = som do Windows | "path/to/file.wav" | None = sem som
        "alert_sound": "default",
    }


# ─────────────────────────────────────────────
#  MODELO
# ─────────────────────────────────────────────
@dataclass
class Ticket:
    id: str        # ID interno (checkbox value) — usado para detetar duplicados
    number: str    # Número visível (ex: 972963)
    title: str
    date: str = ""
    user: str = ""
    priority: str = ""

    def __hash__(self):  return hash(self.id)
    def __eq__(self, o): return isinstance(o, Ticket) and self.id == o.id


# ─────────────────────────────────────────────
#  MONITOR
# ─────────────────────────────────────────────
class TicketMonitor:
    def __init__(self, config: dict):
        self.cfg     = config
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        self.seen_ids: set[str] = self._load_state()

        # Estado partilhado com a tray (atualizado pelo loop)
        self.paused      = False
        self.last_check  = None   # datetime
        self.last_count  = 0
        self.status_text = "A iniciar..."

    # ── Estado persistente ──────────────────────────────────────────────

    def _load_state(self) -> set[str]:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                data = json.load(f)
            log.info(f"Estado carregado: {len(data)} tickets já vistos.")
            return set(data)
        return set()

    def _save_state(self):
        with open(STATE_FILE, "w") as f:
            json.dump(list(self.seen_ids), f)

    # ── Login ───────────────────────────────────────────────────────────

    def login(self) -> bool:
        log.info("A fazer login...")
        try:
            resp = self.session.get(self.cfg["login_url"], timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Constrói payload com TODOS os campos do form
            # (inclui __CSRFToken__, 'do', e outros hidden fields automaticamente)
            payload = {}
            for inp in soup.find_all("input"):
                name  = inp.get("name", "")
                itype = inp.get("type", "text")
                value = inp.get("value", "")
                if not name:
                    continue
                if name == self.cfg["login_fields"]["username_field"]:
                    payload[name] = self.cfg["username"]
                elif itype == "password" or name == self.cfg["login_fields"]["password_field"]:
                    payload[name] = self.cfg["password"]
                else:
                    payload[name] = value   # hidden fields (CSRF, etc.)

            resp = self.session.post(
                self.cfg["login_url"], data=payload,
                timeout=15, allow_redirects=True,
            )
            resp.raise_for_status()

            if "login.php" in resp.url.lower():
                self.status_text = "❌ Login falhou — verifica o config.json"
                log.warning("Login falhou — ainda em login.php.")
                return False

            log.info(f"Login bem-sucedido! ({resp.url})")
            return True

        except requests.RequestException as e:
            self.status_text = "❌ Erro de rede"
            log.error(f"Erro de rede no login: {e}")
            return False

    # ── Scraping ────────────────────────────────────────────────────────

    def fetch_tickets(self) -> list[Ticket]:
        try:
            resp = self.session.get(self.cfg["tickets_url"], timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.error(f"Erro ao obter tickets: {e}")
            return []

        if "login.php" in resp.url:
            log.warning("Sessão expirada — a fazer re-login...")
            self.login()
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select(self.cfg["selectors"]["ticket_row"])

        if not rows:
            log.warning("Nenhuma linha de ticket encontrada.")
            return []

        tickets = []
        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 4:
                continue

            # td[0] — id interno
            checkbox = tds[0].find("input", {"name": "tids[]"})
            tid = checkbox["value"] if checkbox else ""
            if not tid:
                continue

            # td[1] — número visível
            number_el = tds[1].find("a", class_="preview")
            number    = number_el.get_text(strip=True) if number_el else tid

            # td[2] — data
            date = tds[2].get_text(strip=True) if len(tds) > 2 else ""

            # td[3] — título
            title_el = tds[3].find("a")
            title = (title_el.get_text(strip=True) if title_el
                     else tds[3].get_text(strip=True)) or "(sem título)"

            # td[4] — utilizador
            user = tds[4].get_text(strip=True) if len(tds) > 4 else ""

            # td[5] — prioridade
            priority = tds[5].get_text(strip=True) if len(tds) > 5 else ""

            tickets.append(Ticket(id=tid, number=number, title=title,
                                  date=date, user=user, priority=priority))
        return tickets

    # ── Som ─────────────────────────────────────────────────────────────

    def play_sound(self):
        sound = self.cfg.get("alert_sound", "default")
        if not sound:
            return
        try:
            if sound == "default":
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif os.path.isfile(sound):
                winsound.PlaySound(sound, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            log.warning(f"Som falhou: {e}")

    # ── Notificação ─────────────────────────────────────────────────────

    def notify(self, ticket: Ticket):
        ticket_url = f"{self.cfg['base_url']}/scp/tickets.php?id={ticket.id}"
        lines = [ticket.title]
        if ticket.user:     lines.append(f"De: {ticket.user}")
        if ticket.priority: lines.append(f"Prioridade: {ticket.priority}")
        if ticket.date:     lines.append(ticket.date)

        try:
            toast = Notification(
                app_id="Monitor de Tickets",
                title=f"🎫 Novo Ticket #{ticket.number}",
                msg="\n".join(lines),
                duration="long",
                launch=ticket_url,   # ← abre o ticket no browser ao clicar
            )
            toast.set_audio(audio.Default, loop=False)
            toast.show()
            log.info(f"✅ #{ticket.number} | {ticket.title} | {ticket.user}")
        except Exception as e:
            log.warning(f"Notificação falhou ({e}).")
            print(f"\n🎫 #{ticket.number}: {ticket.title} ({ticket.user})\n   {ticket_url}\n")

        self.play_sound()

    # ── Verificação única ────────────────────────────────────────────────

    def check_once(self):
        tickets = self.fetch_tickets()
        self.last_check = datetime.now()
        self.last_count = len(tickets)

        if not tickets:
            return

        new_tickets = []
        for t in tickets:
            if t.id not in self.seen_ids:
                if self.cfg["notify_priorities"] and t.priority not in self.cfg["notify_priorities"]:
                    self.seen_ids.add(t.id)
                    continue
                new_tickets.append(t)

        if new_tickets:
            log.info(f"🆕 {len(new_tickets)} ticket(s) novo(s)!")
            for t in new_tickets:
                self.notify(t)
                self.seen_ids.add(t.id)
            self._save_state()
        else:
            log.info(f"Sem tickets novos. (total: {len(tickets)})")

    # ── Loop principal (corre em thread separada) ────────────────────────

    def run_loop(self):
        if not self.login():
            self.status_text = "❌ Login falhou — verifica o config.json"
            return

        consecutive_errors = 0
        while True:
            try:
                if not self.paused:
                    self.check_once()
                    t = self.last_check.strftime("%H:%M") if self.last_check else "--:--"
                    self.status_text = (
                        f"🟢 A monitorizar  |  último check: {t}  |  {self.last_count} tickets"
                    )
                    consecutive_errors = 0
                else:
                    self.status_text = "⏸ Pausado"

            except Exception as e:
                log.error(f"Erro no loop: {e}")
                consecutive_errors += 1
                self.status_text = "⚠️ Erro — a tentar reconectar..."
                if consecutive_errors >= 3:
                    log.warning("Re-login por erros consecutivos...")
                    self.login()
                    consecutive_errors = 0

            time.sleep(self.cfg["interval_seconds"])


# ─────────────────────────────────────────────
#  ÍCONE DA TRAY — círculo azul com "T" branco
# ─────────────────────────────────────────────
def create_tray_icon() -> Image.Image:
    img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, 62, 62], fill=(0, 120, 212))   # azul Windows
    draw.rectangle([16, 14, 48, 24], fill="white")     # barra horizontal T
    draw.rectangle([26, 14, 38, 52], fill="white")     # barra vertical T
    return img


# ─────────────────────────────────────────────
#  MENU DA TRAY
# ─────────────────────────────────────────────
def build_menu(monitor: TicketMonitor, cfg: dict) -> Menu:

    def toggle_pause(icon, item):
        monitor.paused = not monitor.paused
        log.info("⏸ Pausado." if monitor.paused else "▶ Retomado.")

    def check_now(icon, item):
        if not monitor.paused:
            threading.Thread(target=monitor.check_once, daemon=True).start()

    def open_browser(icon, item):
        webbrowser.open(cfg["tickets_url"])

    def quit_app(icon, item):
        log.info("A sair...")
        icon.stop()

    return Menu(
        MenuItem(lambda item: monitor.status_text, None, enabled=False),
        Menu.SEPARATOR,
        MenuItem(lambda item: "▶ Retomar" if monitor.paused else "⏸ Pausar", toggle_pause),
        MenuItem("🔄 Verificar agora",  check_now),
        MenuItem("🌐 Abrir no browser", open_browser),
        Menu.SEPARATOR,
        MenuItem("❌ Sair", quit_app),
    )


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        cfg = load_config()
    except (FileNotFoundError, ValueError) as e:
        # Se correr como .exe sem config.json, mostra popup de erro
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, str(e),
            "Monitor de Tickets — Configuração em falta",
            0x10  # MB_ICONERROR
        )
        sys.exit(1)

    monitor = TicketMonitor(cfg)

    # Monitor corre em background (daemon — termina automaticamente com a app)
    threading.Thread(target=monitor.run_loop, daemon=True).start()

    # Tray tem de correr na main thread no Windows
    Icon(
        name="TicketMonitor",
        icon=create_tray_icon(),
        title="Monitor de Tickets",
        menu=build_menu(monitor, cfg),
    ).run()