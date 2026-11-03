# SnapYou

SnapYou é um aplicativo de janela para Windows e Mac que baixa vídeos do YouTube (e de outros sites
suportados pelo [yt-dlp](https://github.com/yt-dlp/yt-dlp)) em **MP4**, ou só o áudio em **MP3**.
Cole o link, confira o vídeo encontrado e clique em **Baixar vídeo**.

![SnapYou nos temas claro e escuro](docs/capturas/vitrine.png)

- Visual no estilo dos apps do Claude (design system **Argila**, em `ui/ds/`): fundo creme, laranja terracota,
  títulos em serifa (Source Serif 4) e interface em DM Sans, com **tema escuro automático** que segue o Windows/Mac
- Cores com contraste conferido pela WCAG 2.1 (nível AA)
- Caixa do link no estilo da caixa de mensagem do Claude, com o formato (Vídeo/Áudio) e a pasta dentro dela
- Cartão com miniatura, origem, título, duração, melhor qualidade, formato e tamanho estimado antes de baixar
- Vídeo (MP4) ou só áudio (MP3), cada um com a sua pasta de destino
- Progresso com porcentagem, quantidade baixada, velocidade, tempo restante e etapas
- **Cancelar download** a qualquer momento (os arquivos incompletos são apagados)
- Avisos de erro dentro da janela, em português claro, com botão **Tentar de novo**
- Tela de conclusão com **Abrir arquivo** e **Mostrar na pasta**
- Melhor qualidade disponível; o arquivo é salvo como `AAAA-MM-DD - Título.mp4` (ou `.mp3`)
- O `ffmpeg` vai embutido no `.exe`: não precisa instalar Python, yt-dlp nem ffmpeg

| Início | Baixando | Concluído | Erro |
|---|---|---|---|
| ![](docs/capturas/inicio-claro.png) | ![](docs/capturas/baixando-claro.png) | ![](docs/capturas/concluido-claro.png) | ![](docs/capturas/erro-claro.png) |

## Como usar

1. Baixe o `.exe` na página de [**Releases**](https://github.com/vonhauke/baixar-video/releases) e dê dois cliques.
2. Cole o link do vídeo na caixa (botão **Colar**, ou `Ctrl+V` em qualquer lugar da janela; no Mac, `⌘V`).
3. Escolha **Vídeo MP4** ou **Áudio MP3**, logo abaixo do link.
4. Clique na seta laranja (ou tecle `Enter`): aparece o cartão com a miniatura, o título, a duração e a melhor qualidade.
5. Se quiser, troque a pasta no botão da pasta (padrão: `Vídeos` para vídeo, `Música` para áudio):
   **Trocar pasta…** escolhe outra, **Abrir pasta** mostra a atual.
6. Clique em **Baixar vídeo** e acompanhe: Informações → Baixando → Convertendo para MP4.
   Para interromper, clique em **Cancelar** (ou tecle `Esc`).
7. Ao terminar, use **Abrir arquivo**, **Mostrar na pasta** ou **Baixar outro vídeo** para recomeçar.

Se algo der errado (link inválido, vídeo privado, sem internet…), um aviso aparece no topo da janela
explicando o motivo, com o botão **Tentar de novo**.

> O Windows pode mostrar um aviso do SmartScreen na primeira vez, porque o `.exe`
> não é assinado. Clique em **Mais informações → Executar assim mesmo**.

## Rodar pelo código-fonte

Requisitos: Python 3.10+ e [ffmpeg](https://ffmpeg.org/download.html) no PATH. No Linux, também o WebKit
(`sudo apt install python3-gi gir1.2-webkit2-4.1`).

```
pip install yt-dlp pywebview
python app_baixar_video.pyw
```

## Builds automáticos (GitHub Actions)

A cada envio para a `main`, a automação `.github/workflows/gerar-exe.yml` roda o teste de ponta a ponta
(`.github/teste_e2e.py`) na janela real, num Windows e num Mac da nuvem do GitHub. Depois gera:

- `SnapYou-Windows`: o `SnapYou.exe`, com o ffmpeg embutido;
- `SnapYou-Mac-AppleSilicon` e `SnapYou-Mac-Intel`: o `SnapYou.app` de cada tipo de Mac, com um ffmpeg
  estático embutido.

Para baixar, abra a aba **Actions** do repositório, entre na execução mais recente e role até
**Artifacts**. No Mac, o app não é assinado com certificado da Apple. Na primeira vez, clique nele com
o botão direito → **Abrir**, ou vá em **Ajustes do Sistema → Privacidade e Segurança → Abrir Mesmo Assim**.

## Gerar o .exe (Windows)

```
pip install pyinstaller yt-dlp pywebview
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
pip3 install pyinstaller yt-dlp pywebview
python3 build_mac.py
```

O script usa o `ffmpeg`/`ffprobe` do Homebrew (achados no PATH), empacota tudo
com PyInstaller e deixa o resultado em `mac/dist/SnapYou.app`, copiando também
para a Área de Trabalho. Para embutir binários estáticos, que não dependem do Homebrew
no Mac de quem usa, aponte a pasta deles: `FFMPEG_DIR=/caminho/da/pasta python3 build_mac.py`.

Sem build, dá pra rodar direto o código-fonte:

```
brew install python ffmpeg
pip3 install yt-dlp pywebview
python3 app_baixar_video.pyw
```

## Arquivos

| Arquivo | Para que serve |
|---|---|
| `app_baixar_video.pyw` | Motor do app (busca e download com o yt-dlp, conversão com o ffmpeg) e a ponte com a interface. |
| `ui/` | A interface: `index.html`, `app.css` e `app.js`. |
| `ui/ds/` | Design system **Argila** (cores, fontes, componentes e ícones), igual em todos os apps. |
| `build_exe.py` | Gera o `.exe` (Windows) com o ffmpeg embutido. |
| `mac/build_mac.py` | Gera o `.app` (Mac) com o ffmpeg embutido. |
| `gerar_icone.py` | Recria os ícones (`.ico`, `.icns`, `.png` e `ui/icone.png`). |
| `icone.ico` / `icone.icns` | Ícone do aplicativo (seta creme sobre laranja terracota) no Windows / no Mac. |
| `icone.png` | Ícone em 1024 px, para usos gerais. |
| `.github/teste_e2e.py` | Teste de ponta a ponta: abre a janela real e baixa vídeo e áudio, cancela e provoca um erro. |
| `docs/capturas/` | Capturas de tela usadas neste README. |
| `baixar_video.py` | Versão original, só de linha de comando. |

## Design

A tela é feita em HTML/CSS e mostrada numa janela nativa pelo [pywebview](https://pywebview.flowrl.com/):
Edge WebView2 no Windows (já vem no Windows 10 e 11) e WebKit no Mac.

- **Design system Argila** (`ui/ds/`): inspirado no visual dos apps do Claude. `tokens.css` tem as cores
  (claro e escuro), fontes, espaçamentos e sombras; `components.css` tem os componentes (botões, caixa do
  link, cartões, menus, avisos, progresso, etapas, formulários, tabelas); `icons.js` tem os ícones
  ([Lucide](https://lucide.dev), licença ISC).
- **Fontes:** Source Serif 4 (títulos) e DM Sans (interface), ambas livres (licença OFL), embutidas em `ui/ds/fonts/`.
- **Cores:** fundo creme `#FAF9F5`, texto `#141413`, laranja `#D97757` (destaques) e `#BB5835` nos botões
  (texto branco sobre ele com contraste 4,6:1). Tema escuro quente: fundo `#262624`, cartões `#30302E`.
- **Tema:** segue o sistema. Para forçar um tema, use `<html data-tema="claro">` ou `"escuro"` em `ui/index.html`.
- **Janela:** 640 × 660 px ao abrir, redimensionável.

## Se o download parar de funcionar

Os sites mudam com frequência e o yt-dlp precisa acompanhar. Atualize e gere o `.exe` de novo:

```
python -m pip install --upgrade yt-dlp
python build_exe.py
```

## Aviso

Baixe apenas conteúdo que você tem direito de baixar. Respeite os termos de uso
dos sites e os direitos autorais.
