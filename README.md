# SnapYou

SnapYou é um aplicativo de janela para Windows e Mac que baixa vídeos do YouTube (e de outros sites
suportados pelo [yt-dlp](https://github.com/yt-dlp/yt-dlp)) em **MP4**.
Cole o link, confira o vídeo encontrado e clique em **Baixar vídeo**.

- Interface escura feita com [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- Cartão com miniatura, título, duração e melhor qualidade antes de baixar
- Escolha da pasta de destino e progresso com porcentagem, velocidade, tempo restante e etapas
- Melhor qualidade disponível, convertida para MP4
- O arquivo é salvo como `AAAA-MM-DD - Título.mp4`
- O `ffmpeg` vai embutido no aplicativo: não precisa instalar Python, yt-dlp nem ffmpeg

## Como usar

1. Baixe o aplicativo na página de [**Releases**](https://github.com/vonhauke/baixar-video/releases):
   `SnapYou-Windows.exe` no Windows, ou o `.zip` do Mac (`AppleSilicon` para chip M1 ou mais novo,
   `Intel` para Macs com processador Intel). Dê dois cliques para abrir.
2. Cole o link do vídeo (botão **Colar** ou `Ctrl+V`).
3. Clique em **Buscar vídeo**: aparece o cartão com a miniatura, o título, a duração e a melhor qualidade.
4. Se quiser, troque a pasta em **Trocar** (padrão: `C:\Users\Usuario\Videos`).
5. Clique em **Baixar vídeo** e acompanhe: Informações → Baixando → Convertendo para MP4.
6. Ao terminar, a tela mostra **Concluído**. Use **Abrir** para ver o arquivo ou **Baixar outro vídeo** para recomeçar.

> O aplicativo não é assinado, então o sistema pede uma confirmação na primeira vez.
> No Windows, clique em **Mais informações → Executar assim mesmo** no aviso do SmartScreen.
> No Mac, vá em **Ajustes do Sistema → Privacidade e Segurança** e clique em **Abrir Mesmo Assim**.

## Rodar pelo código-fonte

Requisitos: Python 3.10+ e [ffmpeg](https://ffmpeg.org/download.html) no PATH.

```
pip install yt-dlp customtkinter pillow
python app_baixar_video.pyw
```

## Gerar o .exe (Windows)

```
pip install pyinstaller pillow yt-dlp customtkinter
python build_exe.py
```

O script empacota tudo com o PyInstaller (um único arquivo, sem janela de console),
embute o `ffmpeg.exe` e o `ffprobe.exe` de `C:\ffmpeg\bin` e deixa o resultado em
`dist\`, copiando também para a Área de Trabalho. Se o ffmpeg estiver em outra
pasta, ajuste `FFMPEG_BIN` no início do `build_exe.py`.

## Gerar o .app (Mac)

Só funciona rodando no próprio Mac (o PyInstaller não faz build cruzado).

```
brew install python ffmpeg
cd mac
pip3 install pyinstaller pillow yt-dlp customtkinter
python3 build_mac.py
```

O script usa o `ffmpeg`/`ffprobe` do Homebrew (achados no PATH), empacota tudo
com PyInstaller e deixa o resultado em `mac/dist/SnapYou.app`, copiando também
para a Área de Trabalho. Sem build, dá pra rodar direto o código-fonte:

```
brew install python ffmpeg
pip3 install yt-dlp customtkinter pillow
python3 app_baixar_video.pyw
```

## Arquivos

| Arquivo | Para que serve |
|---|---|
| `app_baixar_video.pyw` | Código do aplicativo (a janela), comum a Windows e Mac. |
| `build_exe.py` | Gera o `.exe` (Windows) com o ffmpeg embutido. |
| `mac/build_mac.py` | Gera o `.app` (Mac) com o ffmpeg do Homebrew embutido. |
| `gerar_icone.py` | Recria os ícones (`.ico`, `.icns` e `.png`). |
| `icone.ico` / `icone.icns` | Ícone do aplicativo (seta âmbar sobre grafite) no Windows / no Mac. |
| `icone.png` | Ícone em 1024 px, para usos gerais. |
| `baixar_video.py` | Versão original, só de linha de comando. |
| `.github/workflows/release.yml` | Gera o app de Windows e Mac no GitHub e publica a release. |
| `.github/release-notes.md` | Texto da release (downloads e avisos de primeira abertura). |

## Publicar uma versão nova

O GitHub gera o `.exe` e os dois `.zip` do Mac sozinho, num computador Windows e em dois Macs
dele, e anexa tudo a uma release. Basta criar uma tag e enviá-la:

```
git tag v2.1
git push origin v2.1
```

Para só testar o build sem publicar, use **Actions → Release → Run workflow**.

## Se o download parar de funcionar

Os sites mudam com frequência e o yt-dlp precisa acompanhar. Atualize e gere o `.exe` de novo:

```
python -m pip install --upgrade yt-dlp
python build_exe.py
```

## Aviso

Baixe apenas conteúdo que você tem direito de baixar. Respeite os termos de uso
dos sites e os direitos autorais.
