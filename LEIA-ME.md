# Baixar Video

Aplicativo de janela para baixar videos do YouTube (e outros sites suportados
pelo yt-dlp). Cola o link, clica em **Baixar video**, o video sai em MP4.

## Como usar

Clique duas vezes em **Baixar Video.exe** (ja esta na sua Area de Trabalho).

1. Cole o link do video (botao **Colar** ou Ctrl+V).
2. Se quiser, mude a pasta em **Trocar...** (padrao: `C:\Users\Pedro\Videos`).
3. Clique em **Baixar video**. A barra mostra o andamento.
4. No fim, ele pergunta se quer abrir a pasta.

O `ffmpeg` vai embutido no `.exe` — nao precisa instalar nada.

## Arquivos deste projeto

| Arquivo | Para que serve |
|---|---|
| `app_baixar_video.pyw` | Codigo do aplicativo (a janela). |
| `gerar_icone.py` | Recria o `icone.ico`. |
| `build_exe.py` | Gera o `.exe` e copia para a Area de Trabalho. |
| `dist\Baixar Video.exe` | O aplicativo pronto (~94 MB). |
| `baixar_video.py` | Versao antiga, so linha de comando. |

## Gerar o .exe de novo (depois de mexer no codigo)

```
python build_exe.py
```

Precisa de: `pip install pyinstaller pillow` e o `ffmpeg` em `C:\ffmpeg\bin`.

## Atualizar o yt-dlp

Sites mudam e o download pode parar de funcionar. Para atualizar:

```
python -m pip install --upgrade yt-dlp
python build_exe.py
```
