#!/usr/bin/env python3
"""
baixar_video.py

Programa simples para baixar vídeos do YouTube e convertê-los
automaticamente para o formato desejado, salvando numa pasta fixa
já organizada por data e título.

Requisitos (precisam estar instalados e no PATH do Windows):
  - yt-dlp   -> pip install yt-dlp
  - ffmpeg   -> https://ffmpeg.org/download.html (precisa estar no PATH)

Uso:
  python baixar_video.py
"""

import subprocess
import sys
import shutil
from datetime import date

# ---------------------------------------------------------------
# CONFIGURAÇÃO FIXA — só mexer aqui se quiser mudar a pasta padrão
# ---------------------------------------------------------------
PASTA_SAIDA = r"C:\Users\Pedro\Videos"


def verificar_dependencias():
    """Confere se yt-dlp e ffmpeg estão instalados antes de começar."""
    faltando = []
    if shutil.which("yt-dlp") is None:
        faltando.append("yt-dlp (instale com: pip install yt-dlp)")
    if shutil.which("ffmpeg") is None:
        faltando.append("ffmpeg (baixe em https://ffmpeg.org/download.html e adicione ao PATH)")

    if faltando:
        print("\nAntes de continuar, instale o que está faltando:")
        for item in faltando:
            print(f"  - {item}")
        sys.exit(1)


def escolher_formato():
    """Pergunta ao usuário o formato desejado para este download."""
    print("\nEscolha o formato de saída:")
    print("  1) MP4 (vídeo)")
    print("  2) MOV (vídeo)")
    print("  3) MP3 (somente áudio)")

    opcoes = {"1": "mp4", "2": "mov", "3": "mp3"}
    escolha = input("Digite 1, 2 ou 3: ").strip()

    while escolha not in opcoes:
        escolha = input("Opção inválida. Digite 1, 2 ou 3: ").strip()

    return opcoes[escolha]


def montar_comando(url, formato):
    """Monta o comando yt-dlp de acordo com o formato escolhido."""
    # Nome do arquivo: data + título original do vídeo
    modelo_nome = f"{PASTA_SAIDA}\\%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s"

    if formato == "mp3":
        comando = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "-o", modelo_nome,
            url,
        ]
    else:
        comando = [
            "yt-dlp",
            "--recode-video", formato,
            "-o", modelo_nome,
            url,
        ]

    return comando


def main():
    print("=== Download e conversão de vídeos do YouTube ===")
    verificar_dependencias()

    url = input("\nCole o link do vídeo do YouTube: ").strip()
    if not url:
        print("Nenhum link informado. Encerrando.")
        sys.exit(1)

    formato = escolher_formato()
    comando = montar_comando(url, formato)

    print(f"\nBaixando e convertendo para {formato.upper()}...")
    print(f"Salvando em: {PASTA_SAIDA}\n")

    resultado = subprocess.run(comando)

    if resultado.returncode == 0:
        print("\nConcluído! Vídeo salvo na pasta configurada.")
    else:
        print("\nAlgo deu errado durante o download/conversão. Verifique o link e tente de novo.")


if __name__ == "__main__":
    main()
