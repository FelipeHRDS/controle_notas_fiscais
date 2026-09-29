@echo off
REM Gera o executavel ControleNotasFiscais.exe (rode este arquivo no Windows,
REM dentro da pasta do projeto, com o Python instalado).

echo Instalando dependencias...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Gerando o executavel...
pyinstaller --onefile --windowed --name "ControleNotasFiscais" --collect-all pdfplumber main.py

echo.
echo Pronto! O executavel esta em dist\ControleNotasFiscais.exe
pause
