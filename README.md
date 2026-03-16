# 🎫 Ticket Monitor — osTicket

Monitor automático de novos tickets para osTicket com notificações nativas no Windows.

## Funcionalidades

- Ícone discreto na barra de tarefas (junto ao relógio)
- Notificação nativa Windows 10/11 ao receber ticket novo
- Som de alerta do Windows
- Abre o ticket no browser ao clicar na notificação
- Verifica novos tickets a cada 2 minutos
- Re-login automático se a sessão expirar
- Credenciais seguras em ficheiro local (nunca no repositório)

## Menu da tray (clique direito no ícone)

```
🟢 A monitorizar  |  último check: 14:32  |  8 tickets
─────────────────────────────────────────────────────
⏸ Pausar
🔄 Verificar agora
🌐 Abrir no browser
─────────────────────────────────────────────────────
❌ Sair
```

## Instalação

### Requisitos
- Python 3.10+
- Windows 10 ou 11

### Passos

**1. Clona o repositório**
```bash
git clone https://github.com/joaosxntos/ticket-monitor.git
cd ticket-monitor
```

**2. Instala as dependências**
```bash
pip install -r requirements.txt
```

**3. Cria o ficheiro `config.json`** na pasta do projeto com as tuas credenciais:
```json
{
    "base_url": "https://empresa.supportsystem.com",
    "username": "o_teu_utilizador",
    "password": "a_tua_password"
}
```

> ⚠️ O `config.json` está no `.gitignore` — as tuas credenciais nunca são enviadas para o GitHub.

**4. Corre**
```bash
python ticket_monitor.py
```

O ícone 🔵 aparece na barra de tarefas junto ao relógio.

## Gerar o executável (.exe)

Para distribuir aos colegas sem precisarem de instalar Python:

```bash
build.bat
```

Gera `dist\TicketMonitor.exe`. Partilha esse ficheiro juntamente com um `config.json` em branco para cada colega preencher com as suas credenciais.

## Estrutura do projeto

```
📁 ticket-monitor
 ├── ticket_monitor.py   ← código principal
 ├── build.bat           ← gera o .exe
 ├── requirements.txt    ← dependências Python
 ├── README.md
 ├── .gitignore
 ├── config.json         ← credenciais (não está no repositório)
 └── seen_tickets.json   ← criado automaticamente ao correr
```

## Tecnologias

- [requests](https://requests.readthedocs.io) + [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — scraping
- [winotify](https://github.com/versa-syahptr/winotify) — notificações Windows nativas
- [pystray](https://github.com/moses-palmer/pystray) — ícone na system tray
- [Pillow](https://python-pillow.org) — geração do ícone
- [PyInstaller](https://pyinstaller.org) — compilação para .exe
