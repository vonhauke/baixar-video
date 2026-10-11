#!/usr/bin/env python3
"""
build_exe.py

Gera "Baixar Video.exe" (um unico arquivo) a partir de app_baixar_video.pyw.
O ffmpeg e o ffprobe vao embutidos, entao o .exe roda em qualquer PC Windows
sem precisar instalar Python, yt-dlp ou ffmpeg.

Uso:
    python build_exe.py

Depois, copie "dist\\Baixar Video.exe" para a Area de Trabalho.
"""

import os
import shutil
import PyInstaller.__main__

AQUI = os.path.dirname(os.path.abspath(__file__))
FFMPEG_BIN = r"C:\ffmpeg\bin"


def _pasta_area_de_trabalho():
    """Descobre a Area de Trabalho real (considera redirecionamento do OneDrive)."""
    try:
        import winreg

        chave = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave) as k:
            valor, _ = winreg.QueryValueEx(k, "Desktop")
            return os.path.expandvars(valor)
    except Exception:
        padrao = os.path.join(os.path.expanduser("~"), "Desktop")
        return padrao if os.path.isdir(padrao) else None

ffmpeg_exe = os.path.join(FFMPEG_BIN, "ffmpeg.exe")
ffprobe_exe = os.path.join(FFMPEG_BIN, "ffprobe.exe")

args = [
    "app_baixar_video.pyw",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", "Baixar Video",
    "--icon", "icone.ico",
    "--add-data", "icone.ico;.",
    "--collect-all", "yt_dlp",
    "--collect-all", "customtkinter",
]

if os.path.isfile(ffmpeg_exe):
    args += ["--add-binary", f"{ffmpeg_exe};ffmpeg"]
else:
    print(f"AVISO: {ffmpeg_exe} nao encontrado - o .exe vai depender do ffmpeg no PATH.")

if os.path.isfile(ffprobe_exe):
    args += ["--add-binary", f"{ffprobe_exe};ffmpeg"]

print("Gerando o executavel (pode levar alguns minutos)...\n")
PyInstaller.__main__.run(args)

destino = os.path.join(AQUI, "dist", "Baixar Video.exe")
if os.path.isfile(destino):
    mb = os.path.getsize(destino) / (1024 * 1024)
    print(f"\nPronto: {destino}  ({mb:.0f} MB)")

    desktop = _pasta_area_de_trabalho()
    if desktop and os.path.isdir(desktop):
        try:
            shutil.copy2(destino, os.path.join(desktop, "Baixar Video.exe"))
            print(f"Copiado para a Area de Trabalho: {desktop}\\Baixar Video.exe")
        except Exception as e:
            print(f"Nao consegui copiar para a Area de Trabalho automaticamente: {e}")
else:
    print("\nAlgo deu errado: o executavel nao foi encontrado em dist\\.")
