# 🎫 Ticket Notifier

Monitor automático de novos tickets para supportsystem com notificações nativas no Windows.

## Funcionalidades
- Login automático no supportsystem
- Verifica novos tickets a cada 2 minutos
- Notificação nativa Windows 10/11 clicável (abre o ticket no browser)
- Som de alerta do Windows
- Não re-notifica o mesmo ticket após reinício

## Instalação
```bash
pip install -r requirements.txt
```

## Configuração

Cria um ficheiro `config.json` na pasta do projeto (não é incluído no repositório):
```json
{
    "base_url": "https://empresa.supportsystem.com",
    "username": "o_teu_utilizador",
    "password": "a_tua_password"
}
```

## Utilização
```bash
python ticket_monitor.py
```

## Notas
- O `config.json` está no `.gitignore` — as credenciais nunca são enviadas para o GitHub
- Compatível com Windows 10/11