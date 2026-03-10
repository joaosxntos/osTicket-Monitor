@echo off
REM build.bat — Gera o ticket_monitor.exe
REM Corre este ficheiro uma vez para criar o .exe distribuível

echo A instalar dependências...
pip install -r requirements.txt

echo.
echo A gerar o executável...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --name "TicketMonitor" ^
    ticket_monitor.py

echo.
echo ============================================
echo  Concluido!
echo  O executavel esta em: dist\TicketMonitor.exe
echo.
echo  Para distribuir aos colegas, partilha:
echo    - dist\TicketMonitor.exe
echo    - config.json  (cada um preenche com as suas credenciais)
echo ============================================
pause
