# SnapYou

SnapYou é um aplicativo de janela para Windows que baixa vídeos do YouTube (e de outros sites
suportados pelo [yt-dlp](https://github.com/yt-dlp/yt-dlp)) em **MP4**.
Cole o link, confira o vídeo encontrado e clique em **Baixar vídeo**.

- Interface escura feita com [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- Cartão com miniatura, título, duração e melhor qualidade antes de baixar
- Escolha da pasta de destino e progresso com porcentagem, velocidade, tempo restante e etapas
- Melhor qualidade disponível, convertida para MP4
- O arquivo é salvo como `AAAA-MM-DD - Título.mp4`
- O `ffmpeg` vai embutido no `.exe`: não precisa instalar Python, yt-dlp nem ffmpeg

## Como usar

1. Baixe o `.exe` na página de [**Releases**](https://github.com/vonhauke/baixar-video/releases) e dê dois cliques.
2. Cole o link do vídeo (botão **Colar** ou `Ctrl+V`).
3. Clique em **Buscar vídeo**: aparece o cartão com a miniatura, o título, a duração e a melhor qualidade.
4. Se quiser, troque a pasta em **Trocar** (padrão: `C:\Users\Pedro\Videos`).
5. Clique em **Baixar vídeo** e acompanhe: Informações → Baixando → Convertendo para MP4.
6. Ao terminar, a tela mostra **Concluído**. Use **Abrir** para ver o arquivo ou **Baixar outro vídeo** para recomeçar.

> O Windows pode mostrar um aviso do SmartScreen na primeira vez, porque o `.exe`
> não é assinado. Clique em **Mais informações → Executar assim mesmo**.

## Rodar pelo código-fonte

Requisitos: Python 3.10+ e [ffmpeg](https://ffmpeg.org/download.html) no PATH.

```
pip install yt-dlp customtkinter pillow
python app_baixar_video.pyw
```

## Gerar o .exe

```
pip install pyinstaller pillow yt-dlp customtkinter
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
| `gerar_icone.py` | Recria os ícones (`.ico`, `.icns` e `.png`). |
| `icone.ico` / `icone.icns` | Ícone do aplicativo (seta âmbar sobre grafite) no Windows / no Mac. |
| `icone.png` | Ícone em 1024 px, para usos gerais. |
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
