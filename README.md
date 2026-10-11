# Baixar Vídeo

Aplicativo de janela para Windows que baixa vídeos do YouTube (e de outros sites
suportados pelo [yt-dlp](https://github.com/yt-dlp/yt-dlp)) em **MP4**.
Cole o link, clique em **Baixar video** e pronto.

- Interface simples, no estilo Windows 11 (tema [sv_ttk](https://github.com/rdbende/Sun-Valley-ttk-theme))
- Escolha da pasta de destino e barra de progresso
- Melhor qualidade disponível, convertida para MP4
- O arquivo é salvo como `AAAA-MM-DD - Título.mp4`
- O `ffmpeg` vai embutido no `.exe`: não precisa instalar Python, yt-dlp nem ffmpeg

## Como usar

1. Baixe o `.exe` na página de [**Releases**](https://github.com/vonhauke/baixar-video/releases) e dê dois cliques.
2. Cole o link do vídeo (botão **Colar** ou `Ctrl+V`).
3. Se quiser, troque a pasta em **Trocar...** (padrão: `C:\Users\Pedro\Videos`).
4. Clique em **Baixar video** e acompanhe a barra de progresso.
5. Ao terminar, o app pergunta se você quer abrir a pasta.

> O Windows pode mostrar um aviso do SmartScreen na primeira vez, porque o `.exe`
> não é assinado. Clique em **Mais informações → Executar assim mesmo**.

## Rodar pelo código-fonte

Requisitos: Python 3.10+ e [ffmpeg](https://ffmpeg.org/download.html) no PATH.

```
pip install yt-dlp sv-ttk
python app_baixar_video.pyw
```

## Gerar o .exe

```
pip install pyinstaller pillow yt-dlp sv-ttk
python build_exe.py
```

O script empacota tudo com o PyInstaller (um único arquivo, sem janela de console),
embute o `ffmpeg.exe` e o `ffprobe.exe` de `C:\ffmpeg\bin` e deixa o resultado em
`dist\`, copiando também para a Área de Trabalho. Se o ffmpeg estiver em outra
pasta, ajuste `FFMPEG_BIN` no início do `build_exe.py`.

## Arquivos

| Arquivo | Para que serve |
|---|---|
| `app_baixar_video.pyw` | Código do aplicativo (a janela). |
| `build_exe.py` | Gera o `.exe` com o ffmpeg embutido. |
| `gerar_icone.py` | Recria o `icone.ico`. |
| `icone.ico` | Ícone do aplicativo. |
| `baixar_video.py` | Versão original, só de linha de comando. |

## Se o download parar de funcionar

Os sites mudam com frequência e o yt-dlp precisa acompanhar. Atualize e gere o `.exe` de novo:

```
python -m pip install --upgrade yt-dlp
python build_exe.py
```

## Aviso

Baixe apenas conteúdo que você tem direito de baixar. Respeite os termos de uso
dos sites e os direitos autorais.
