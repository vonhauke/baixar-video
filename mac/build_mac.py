#!/usr/bin/env python3
"""
build_mac.py

Gera "SnapYou.app" a partir de ../app_baixar_video.pyw. O ffmpeg e o ffprobe
vao embutidos, entao o app roda em qualquer Mac sem precisar instalar Python,
yt-dlp ou ffmpeg. Por padrao usa os do PATH ("brew install ffmpeg"); para usar
binarios estaticos (que nao dependem do Homebrew), aponte a pasta deles na
variavel FFMPEG_DIR - e o que faz a automacao do GitHub (gerar-exe.yml).

So funciona rodando no proprio Mac (o PyInstaller nao faz build cruzado).

Uso:
    cd mac
    pip3 install pyinstaller yt-dlp customtkinter pillow
    python3 build_mac.py

Depois, copie "dist/SnapYou.app" para a pasta Aplicativos.
"""

import os
import shutil
import sys

if sys.platform != "darwin":
    sys.exit("build_mac.py so roda no macOS. No Windows, use build_exe.py.")

import PyInstaller.__main__

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

PASTA_FFMPEG = os.environ.get("FFMPEG_DIR")
if PASTA_FFMPEG:
    ffmpeg_exe = os.path.join(PASTA_FFMPEG, "ffmpeg")
    ffprobe_exe = os.path.join(PASTA_FFMPEG, "ffprobe")
    for exe in (ffmpeg_exe, ffprobe_exe):
        if not os.path.isfile(exe):
            sys.exit(f"FFMPEG_DIR aponta para {PASTA_FFMPEG}, mas {exe} nao existe.")
else:
    ffmpeg_exe = shutil.which("ffmpeg")
    ffprobe_exe = shutil.which("ffprobe")

args = [
    os.path.join(RAIZ, "app_baixar_video.pyw"),
    "--noconfirm",
    "--clean",
    # pasta (onedir), o formato recomendado pelo PyInstaller para .app:
    # abre mais rapido que o arquivo unico (que nao combina com .app)
    "--windowed",
    "--name", "SnapYou",
    "--distpath", os.path.join(AQUI, "dist"),
    "--workpath", os.path.join(AQUI, "build"),
    "--specpath", AQUI,
    "--icon", os.path.join(RAIZ, "icone.icns"),
    "--add-data", f"{os.path.join(RAIZ, 'icone.png')}:.",
    "--collect-all", "yt_dlp",
    "--collect-all", "customtkinter",
]

if ffmpeg_exe:
    args += ["--add-binary", f"{ffmpeg_exe}:ffmpeg"]
else:
    print("AVISO: ffmpeg nao encontrado no PATH (rode 'brew install ffmpeg') - "
          "o app vai depender do ffmpeg instalado na maquina.")

if ffprobe_exe:
    args += ["--add-binary", f"{ffprobe_exe}:ffmpeg"]

print("Gerando o aplicativo (pode levar alguns minutos)...\n")
PyInstaller.__main__.run(args)

destino = os.path.join(AQUI, "dist", "SnapYou.app")
if os.path.isdir(destino):
    print(f"\nPronto: {destino}")

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if os.path.isdir(desktop):
        try:
            copia = os.path.join(desktop, "SnapYou.app")
            if os.path.isdir(copia):
                shutil.rmtree(copia)
            shutil.copytree(destino, copia)
            print(f"Copiado para a Area de Trabalho: {copia}")
        except Exception as e:
            print(f"Nao consegui copiar para a Area de Trabalho automaticamente: {e}")
else:
    print("\nAlgo deu errado: o aplicativo nao foi encontrado em dist/.")
