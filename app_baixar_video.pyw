#!/usr/bin/env python3
"""
app_baixar_video.pyw

SnapYou: aplicativo de janela para baixar videos do YouTube (e outros sites
suportados pelo yt-dlp). Cole o link, clique em "Buscar video" para ver a
miniatura, o titulo, a duracao e a melhor qualidade, e depois em "Baixar
video". Pode escolher entre baixar o video (MP4) ou so o audio (MP3),
sempre na melhor qualidade disponivel.

Empacotado como .exe com PyInstaller (ver build_exe.py). O ffmpeg vai junto
dentro do executavel, entao nao precisa de nada instalado na maquina.

Visual: CustomTkinter com tema claro inspirado nas diretrizes da Apple
(Human Interface Guidelines) e tema escuro automatico, que segue o sistema.
Cada cor e um par (claro, escuro); o CustomTkinter troca sozinho.
"""

import functools
import io
import math
import os
import re
import sys
import queue
import threading
import subprocess
import urllib.request
import tkinter as tk
from tkinter import filedialog
from tkinter import font as tkfont

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageOps

import yt_dlp

APP_TITLE = "SnapYou"
if sys.platform == "win32":
    DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Videos")
elif sys.platform == "darwin":
    DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Movies")
else:
    DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Videos")
DEFAULT_DIR_AUDIO = os.path.join(os.path.expanduser("~"), "Music")
ATALHO_COLAR = "⌘V" if sys.platform == "darwin" else "Ctrl+V"

# ---------------------------------------------------------------------------
# Medidas
# ---------------------------------------------------------------------------
LARGURA = 560                       # largura util da janela; a altura acompanha o conteudo
ALTURA_MIN = 420
PAD_X, PAD_Y = 28, 26
ESPACO = 14                         # espaco vertical entre blocos
RAIO = 12                           # cantos de cartoes, campo e botoes grandes
MINI_W, MINI_H = 168, 94            # miniatura 16:9
ESC = 3                             # imagens desenhadas em 3x para telas HiDPI

# ---------------------------------------------------------------------------
# Cores: (claro, escuro). Paleta baseada nas cores de sistema da Apple, com
# contraste conferido pela WCAG 2.1 (texto >= 4,5:1).
# ---------------------------------------------------------------------------
C = {
    "fundo":          ("#F5F5F7", "#1C1C1E"),
    "superficie":     ("#FFFFFF", "#2C2C2E"),
    "borda":          ("#E3E3E8", "#3A3A3C"),
    "separador":      ("#ECECF0", "#38383A"),
    "texto":          ("#1D1D1F", "#F5F5F7"),
    "texto_sec":      ("#6E6E73", "#98989D"),   # 4,66:1 sobre o fundo claro
    "texto_terc":     ("#8E8E93", "#7C7C80"),   # so para placeholder
    "acento":         ("#0071E3", "#0071E3"),   # branco sobre ele: 4,7:1
    "acento_hover":   ("#0062C4", "#1A82F0"),
    "acento_desab":   ("#A9CBF2", "#1F3B5C"),
    "acento_texto_desab": ("#FFFFFF", "#7C93AE"),
    "link":           ("#0066CC", "#4DA3FF"),   # acento usado como texto
    "acento_suave":   ("#E8F1FD", "#16324F"),
    "acento_suave_hover": ("#D9E8FC", "#1C3D61"),
    "acento_suave_texto": ("#0058B9", "#8CC4FF"),
    "neutro":         ("#EDEDF0", "#3A3A3C"),   # botoes secundarios
    "neutro_hover":   ("#E2E2E7", "#48484A"),
    "trilha":         ("#E8E8ED", "#3A3A3C"),   # trilha do progresso e do seletor
    "seletor_ativo":  ("#FFFFFF", "#636366"),
    "ok":             ("#1E7F37", "#30D158"),
    "ok_fundo":       ("#E8F6EC", "#1C3524"),
    "erro":           ("#C4161C", "#FF6961"),
    "erro_fundo":     ("#FFF2F1", "#3A1F1E"),
    "erro_borda":     ("#FBD4D1", "#5C2B28"),
    "info_fundo":     ("#F0F0F3", "#2C2C2E"),
}


def claro(chave):
    return C[chave][0]


def escuro(chave):
    return C[chave][1]


# melhor video+audio em MP4; cai para o melhor arquivo unico se preciso.
# Usado na busca de informacoes e no download, para que a qualidade mostrada
# no cartao seja a que sera de fato baixada. "bv*"/"ba" ja pedem a MAIOR
# qualidade disponivel automaticamente — nao precisa (nem da) escolher um
# numero, o yt-dlp sempre tenta o melhor stream que o site oferecer.
FORMATO_VIDEO = "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b"

# melhor audio disponivel, para extrair e converter para MP3.
FORMATO_AUDIO = "ba/b"

NOMES_FONTE = {
    "YOUTUBE": "YouTube", "YOUTUBETAB": "YouTube", "INSTAGRAM": "Instagram",
    "TWITTER": "X", "TIKTOK": "TikTok", "VIMEO": "Vimeo", "FACEBOOK": "Facebook",
    "TWITCH": "Twitch", "TWITCHVOD": "Twitch", "TWITCHCLIPS": "Twitch",
    "REDDIT": "Reddit", "DAILYMOTION": "Dailymotion", "SOUNDCLOUD": "SoundCloud",
    "GLOBO": "Globoplay", "GENERIC": "Vídeo",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def resource_path(rel):
    """Caminho de um recurso, funcionando tanto rodando o .py quanto o .exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def ffmpeg_dir():
    """Pasta com o ffmpeg embarcado no executavel. Se nao houver, retorna None
    e o yt-dlp tenta achar o ffmpeg no PATH do sistema."""
    cand = resource_path("ffmpeg")
    nome = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    if os.path.isfile(os.path.join(cand, nome)):
        return cand
    return None


def abrir_no_sistema(caminho):
    """Abre um arquivo ou pasta com o programa padrao. Levanta excecao se falhar."""
    if os.path.isdir(caminho) or not os.path.splitext(caminho)[1]:
        os.makedirs(caminho, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(caminho)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", caminho], check=True)
    else:
        subprocess.run(["xdg-open", caminho], check=True)


def mostrar_na_pasta(arquivo):
    """Abre a pasta do arquivo com ele ja selecionado (Explorer / Finder)."""
    arquivo = os.path.normpath(arquivo)
    if sys.platform == "win32":
        # o explorer devolve 1 mesmo quando da certo; por isso sem check
        subprocess.run(["explorer", "/select,", arquivo])
    elif sys.platform == "darwin":
        subprocess.run(["open", "-R", arquivo], check=True)
    else:
        subprocess.run(["xdg-open", os.path.dirname(arquivo)], check=True)


def formatar_duracao(segundos):
    """12:47 ou 1:02:03."""
    if not segundos:
        return ""
    segundos = int(segundos)
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def formatar_velocidade(bytes_por_s):
    """4,8 MB/s (decimal, virgula)."""
    if not bytes_por_s:
        return ""
    mb = bytes_por_s / 1_000_000
    if mb >= 1:
        return f"{mb:.1f}".replace(".", ",") + " MB/s"
    return f"{bytes_por_s / 1000:.0f} KB/s"


def formatar_tamanho(n):
    """245 MB / 1,2 GB (decimal, virgula)."""
    if not n:
        return ""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}".replace(".", ",") + " GB"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f} MB"
    return f"{max(n / 1000, 1):.0f} KB"


def nome_da_fonte(chave):
    if not chave:
        return "Vídeo"
    chave = chave.upper()
    return NOMES_FONTE.get(chave, chave.title())


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def explicar_erro(mensagem, contexto):
    """Traduz o erro do yt-dlp em (titulo, explicacao, detalhe) para leigos."""
    texto = _ANSI.sub("", mensagem or "").strip()
    detalhe = texto.splitlines()[-1] if texto else ""
    detalhe = re.sub(r"^(ERROR|ERRO):\s*", "", detalhe)
    detalhe = re.sub(r"^\[[^\]]+\]\s*[\w-]+:\s*", "", detalhe)
    baixo = texto.lower()

    titulo = ("Não foi possível encontrar o vídeo" if contexto == "busca"
              else "O download não foi concluído")
    regras = [
        (r"unsupported url", "Esse link não é de um site suportado. Confira se copiou o endereço do vídeo."),
        (r"is not a valid url|invalid url|no such file",
         "Isso não parece ser um link. Copie o endereço completo do vídeo, começando com https://"),
        (r"\bage\b|age[- ]restricted|confirm your age",
         "Este vídeo tem restrição de idade e exige login para ser baixado."),
        (r"private video|sign in|login required|log in|cookies",
         "Este vídeo é privado ou exige login, por isso não pode ser baixado."),
        (r"video unavailable|not available|has been removed|\b404\b",
         "Este vídeo não está disponível. Ele pode ter sido removido ou bloqueado na sua região."),
        (r"getaddrinfo|network is unreachable|timed out|urlopen error|connection|name resolution|temporary failure",
         "Não há conexão com a internet, ou o site não respondeu. Verifique a rede e tente de novo."),
        (r"ffmpeg|ffprobe", "O componente de conversão (ffmpeg) não foi encontrado. Reinstale o SnapYou."),
        (r"no space left|disk full", "Não há espaço livre no disco. Libere espaço ou escolha outra pasta."),
        (r"permission denied|access is denied|errno 13",
         "Sem permissão para salvar nessa pasta. Escolha outra pasta em Trocar."),
        (r"\b429\b|too many requests", "O site recebeu pedidos demais. Aguarde alguns minutos e tente de novo."),
    ]
    for padrao, explicacao in regras:
        if re.search(padrao, baixo):
            return titulo, explicacao, detalhe
    return titulo, "Verifique se o link está correto e se há conexão com a internet.", detalhe


# ---------------------------------------------------------------------------
# Tipografia: fonte nativa de cada sistema
# ---------------------------------------------------------------------------
def escolher_fontes(raiz):
    """Devolve (familia_texto, familia_titulo, familia_semibold_ou_None).
    Windows 11: Segoe UI Variable; Windows 10: Segoe UI; Mac: San Francisco
    (fonte padrao do Tk no Mac); Linux: Inter/Noto/DejaVu."""
    familias = set(tkfont.families(raiz))
    padrao = tkfont.nametofont("TkDefaultFont").actual("family")

    def primeira(nomes, reserva):
        for n in nomes:
            if n in familias:
                return n
        return reserva

    if sys.platform == "win32":
        texto = primeira(["Segoe UI Variable Text", "Segoe UI"], padrao)
        titulo = primeira(["Segoe UI Variable Display", "Segoe UI"], texto)
        semi = primeira(["Segoe UI Variable Text Semibold", "Segoe UI Semibold"], None)
    elif sys.platform == "darwin":
        texto = titulo = padrao             # .AppleSystemUIFont = San Francisco
        semi = None
    else:
        texto = primeira(["Inter", "Noto Sans", "Cantarell", "DejaVu Sans"], padrao)
        titulo = primeira(["Inter Display", "Inter"], texto)
        semi = primeira(["Inter SemiBold"], None)
    return texto, titulo, semi


# ---------------------------------------------------------------------------
# Imagens desenhadas com Pillow (icones e miniatura)
# ---------------------------------------------------------------------------
def _fonte_pil(tamanho_px, negrito=False):
    if negrito:
        nomes = ("segoeuisb.ttf", "segoeuib.ttf", "arialbd.ttf",
                 "/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Helvetica.ttc",
                 "Inter-SemiBold.otf", "DejaVuSans-Bold.ttf")
    else:
        nomes = ("segoeui.ttf", "arial.ttf",
                 "/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Helvetica.ttc",
                 "Inter-Medium.otf", "DejaVuSans.ttf")
    for nome in nomes:
        try:
            return ImageFont.truetype(nome, int(tamanho_px))
        except OSError:
            continue
    return ImageFont.load_default(size=int(tamanho_px))


def _hex(cor, alfa=255):
    cor = cor.lstrip("#")
    return (int(cor[0:2], 16), int(cor[2:4], 16), int(cor[4:6], 16), alfa)


def _tela(lado):
    """Tela RGBA supersampled (4x) para desenhar um icone de `lado` px."""
    n = lado * ESC * 4
    return Image.new("RGBA", (n, n), (0, 0, 0, 0)), n


def _reduzir(img, lado):
    return img.resize((lado * ESC, lado * ESC), Image.LANCZOS)


def _linha_redonda(d, pts, largura, cor):
    """Polilinha com pontas e juncoes redondas (estilo SF Symbols)."""
    d.line(pts, fill=cor, width=int(largura), joint="curve")
    r = largura / 2
    for x, y in pts:
        d.ellipse([x - r, y - r, x + r, y + r], fill=cor)


def desenhar_marca(n):
    """Marca do SnapYou em n x n px: squircle azul com seta de download branca.
    Mesma arte do gerar_icone.py."""
    k = n / 1024
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))

    topo, base = (64, 156, 255), (0, 98, 214)
    grad = Image.new("RGBA", (n, n))
    g = ImageDraw.Draw(grad)
    for y in range(n):
        t = y / max(n - 1, 1)
        g.line([(0, y), (n, y)], fill=tuple(int(topo[i] + (base[i] - topo[i]) * t) for i in range(3)) + (255,))
    mascara = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, n - 1, n - 1], radius=int(230 * k), fill=255)
    img.paste(grad, (0, 0), mascara)

    d = ImageDraw.Draw(img)
    branco = (255, 255, 255, 255)
    _linha_redonda(d, [(512 * k, 232 * k), (512 * k, 640 * k)], 96 * k, branco)          # haste
    _linha_redonda(d, [(330 * k, 470 * k), (512 * k, 652 * k), (694 * k, 470 * k)], 96 * k, branco)  # ponta
    d.rounded_rectangle([284 * k, 764 * k, 740 * k, 852 * k], radius=44 * k, fill=(255, 255, 255, 235))  # bandeja
    return img


def icone_app(lado=40):
    return desenhar_marca(lado * ESC * 4).resize((lado * ESC, lado * ESC), Image.LANCZOS)


def icone_prancheta(lado=16, cor="#1D1D1F"):
    img, n = _tela(lado)
    s = n / 24
    d = ImageDraw.Draw(img)
    traco = int(1.8 * s)
    d.rounded_rectangle([5 * s, 5 * s, 19 * s, 21 * s], radius=2.5 * s, outline=_hex(cor), width=traco)
    d.rectangle([8 * s, 2 * s, 16 * s, 7 * s], fill=(0, 0, 0, 0))       # abre a borda de cima
    d.rounded_rectangle([8.5 * s, 3 * s, 15.5 * s, 7 * s], radius=1.2 * s, outline=_hex(cor), width=traco)
    return _reduzir(img, lado)


def icone_pasta(lado=18, cor="#0071E3"):
    img, n = _tela(lado)
    s = n / 24
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([3 * s, 5 * s, 11 * s, 10 * s], radius=1.8 * s, fill=_hex(cor))
    d.rounded_rectangle([3 * s, 7.5 * s, 21 * s, 19.5 * s], radius=2.2 * s, fill=_hex(cor))
    return _reduzir(img, lado)


def icone_check(lado, fundo, marca="#FFFFFF"):
    """Circulo cheio com um check (sucesso / etapa concluida)."""
    img, n = _tela(lado)
    s = n / 24
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, n - 1, n - 1], fill=_hex(fundo))
    _linha_redonda(d, [(7.2 * s, 12.4 * s), (10.6 * s, 15.6 * s), (16.8 * s, 9 * s)], 2.4 * s, _hex(marca))
    return _reduzir(img, lado)


def icone_etapa_ativa(lado, cor, trilha):
    """Anel com ponto no meio (etapa em andamento)."""
    img, n = _tela(lado)
    s = n / 24
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, n - 1, n - 1], fill=_hex(trilha))
    d.ellipse([2.2 * s, 2.2 * s, n - 2.2 * s, n - 2.2 * s], fill=_hex(cor))
    d.ellipse([8 * s, 8 * s, 16 * s, 16 * s], fill=(255, 255, 255, 255))
    return _reduzir(img, lado)


def icone_etapa_pendente(lado, cor):
    img, n = _tela(lado)
    s = n / 24
    ImageDraw.Draw(img).ellipse([1 * s, 1 * s, n - 1 * s, n - 1 * s], outline=_hex(cor), width=int(2 * s))
    return _reduzir(img, lado)


def icone_alerta(lado, cor):
    """Circulo cheio com '!' (erro)."""
    img, n = _tela(lado)
    s = n / 24
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, n - 1, n - 1], fill=_hex(cor))
    branco = (255, 255, 255, 255)
    _linha_redonda(d, [(12 * s, 6.6 * s), (12 * s, 13 * s)], 2.6 * s, branco)
    r = 1.6 * s
    d.ellipse([12 * s - r, 17 * s - r, 12 * s + r, 17 * s + r], fill=branco)
    return _reduzir(img, lado)


def icone_info(lado, cor):
    """Circulo cheio com 'i' (aviso neutro)."""
    img, n = _tela(lado)
    s = n / 24
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, n - 1, n - 1], fill=_hex(cor))
    branco = (255, 255, 255, 255)
    _linha_redonda(d, [(12 * s, 11 * s), (12 * s, 17.4 * s)], 2.6 * s, branco)
    r = 1.6 * s
    d.ellipse([12 * s - r, 7 * s - r, 12 * s + r, 7 * s + r], fill=branco)
    return _reduzir(img, lado)


def icone_fechar(lado, cor):
    img, n = _tela(lado)
    s = n / 24
    d = ImageDraw.Draw(img)
    _linha_redonda(d, [(7 * s, 7 * s), (17 * s, 17 * s)], 2 * s, _hex(cor))
    _linha_redonda(d, [(17 * s, 7 * s), (7 * s, 17 * s)], 2 * s, _hex(cor))
    return _reduzir(img, lado)


def quadros_spinner(lado=18, cor="#FFFFFF", total=12):
    """Quadros de um arco girando, para o botao enquanto busca."""
    quadros = []
    for i in range(total):
        img, n = _tela(lado)
        d = ImageDraw.Draw(img)
        m = n * 0.12
        inicio = i * 360 / total
        d.arc([m, m, n - m, n - m], inicio, inicio + 270, fill=_hex(cor), width=int(n * 0.12))
        quadros.append(_reduzir(img, lado))
    return quadros


@functools.lru_cache(maxsize=2)
def _gradiente_miniatura(w, h, escuro_=False):
    """Degrade neutro (claro ou escuro) usado enquanto a miniatura real nao chega."""
    if escuro_:
        c0, c1 = _hex("#3A3A3C"), _hex("#242426")
    else:
        c0, c1 = _hex("#E9E9EE"), _hex("#D5D7DE")
    # degrade diagonal: media de um degrade vertical com um horizontal
    vertical = Image.linear_gradient("L").resize((w, h))
    horizontal = Image.linear_gradient("L").rotate(90).transpose(Image.FLIP_LEFT_RIGHT).resize((w, h))
    grad = Image.blend(vertical, horizontal, 0.5)
    return Image.composite(Image.new("RGBA", (w, h), c1), Image.new("RGBA", (w, h), c0), grad)


def montar_miniatura(foto, duracao_texto, escuro_=False):
    """Miniatura 16:9 com cantos de 10px, botao de play e a duracao no canto.
    `foto` e uma PIL.Image (ou None para o degrade padrao). Cantos transparentes,
    para servir em qualquer tema."""
    w, h = MINI_W * ESC, MINI_H * ESC

    if foto is not None:
        base = ImageOps.fit(foto.convert("RGB"), (w, h), Image.LANCZOS).convert("RGBA")
    else:
        base = _gradiente_miniatura(w, h, escuro_).copy()

    ss = 4  # sobreamostragem do que e desenhado por cima
    cam = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    u = ESC * ss  # 1 px de tela
    cx, cy = w * ss / 2, h * ss / 2
    r = 17 * u
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 0x5c))
    d.polygon([(cx - 5 * u, cy - 7.5 * u), (cx + 8 * u, cy), (cx - 5 * u, cy + 7.5 * u)],
              fill=(255, 255, 255, 245))

    if duracao_texto:
        fonte = _fonte_pil(11 * u, negrito=True)
        caixa = d.textbbox((0, 0), duracao_texto, font=fonte)
        tw, th = caixa[2] - caixa[0], caixa[3] - caixa[1]
        bw, bh = tw + 12 * u, th + 8 * u
        x1, y1 = w * ss - 6 * u, h * ss - 6 * u
        d.rounded_rectangle([x1 - bw, y1 - bh, x1, y1], radius=5 * u, fill=(0, 0, 0, 0xb0))
        d.text((x1 - bw + 6 * u - caixa[0], y1 - bh + 4 * u - caixa[1]), duracao_texto,
               font=fonte, fill=(255, 255, 255, 255))

    cam = cam.resize((w, h), Image.LANCZOS)
    base = Image.alpha_composite(base, cam)

    mascara = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        [0, 0, w * ss - 1, h * ss - 1], radius=10 * ESC * ss, fill=255
    )
    mascara = mascara.resize((w, h), Image.LANCZOS)
    saida = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    saida.paste(base, (0, 0), mascara)
    return saida


def miniaturas(foto, duracao_texto):
    """Par (claro, escuro). Com foto real as duas sao a mesma imagem."""
    if foto is not None:
        img = montar_miniatura(foto, duracao_texto)
        return img, img
    return montar_miniatura(None, duracao_texto), montar_miniatura(None, duracao_texto, True)


def baixar_foto(url):
    """Baixa a miniatura do video. Devolve uma PIL.Image ou None se falhar."""
    if not url or not url.lower().startswith(("http://", "https://")):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            dados = resp.read(5_000_000)
        return Image.open(io.BytesIO(dados)).convert("RGB")
    except Exception:
        return None


def limitar_linhas(texto, fonte, largura, max_linhas=2):
    """Quebra o texto em linhas de ate `largura` px e corta com reticencias
    se passar de `max_linhas` (o cartao nao cresce com titulos longos)."""

    def cabe(t):
        return fonte.measure(t) <= largura

    def cortar(t):
        if cabe(t):
            return t
        while t and not cabe(t + "…"):
            t = t[:-1]
        return t.rstrip() + "…"

    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if cabe(teste) or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)

    linhas = [cortar(l) for l in linhas]  # palavra maior que a linha
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        ultima = linhas[-1].rstrip("…")
        while ultima and not cabe(ultima + "…"):
            ultima = ultima[:-1]
        linhas[-1] = ultima.rstrip() + "…"
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Busca de informacoes e download (rodam em threads para nao travar a janela)
# ---------------------------------------------------------------------------
def buscar_info(url, busca_id, msg_queue, modo):
    """Busca so os metadados (sem baixar), manda o resultado e depois a miniatura."""
    opcoes = {
        "format": FORMATO_AUDIO if modo == "audio" else FORMATO_VIDEO,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        msg_queue.put(("erro_busca", (busca_id, str(e))))
        return

    formatos = info.get("requested_formats") or [info]
    dados = {
        "id": busca_id,
        "url": url,
        "modo": modo,
        "titulo": info.get("title") or "Sem título",
        "duracao": info.get("duration"),
        "fonte": (info.get("extractor_key") or info.get("extractor") or "").upper(),
        "altura": max((f.get("height") or 0 for f in formatos), default=0) or None,
        "abr": max((f.get("abr") or 0 for f in formatos), default=0) or None,
        "tamanho": sum(f.get("filesize") or f.get("filesize_approx") or 0 for f in formatos) or None,
    }
    msg_queue.put(("info", dados))

    foto = baixar_foto(info.get("thumbnail"))
    msg_queue.put(("miniatura", (busca_id, miniaturas(foto, formatar_duracao(dados["duracao"])))))


def baixar(url, pasta_saida, msg_queue, modo, cancelar=None):
    """Baixa o video (ou so o audio) e envia o andamento pela fila msg_queue.
    Se o evento `cancelar` for acionado, interrompe e apaga os arquivos parciais."""
    cancelar = cancelar or threading.Event()
    parciais = set()

    def hook(d):
        if cancelar.is_set():
            raise yt_dlp.utils.DownloadCancelled("Cancelado pelo usuario")
        status = d.get("status")
        for chave in ("tmpfilename", "filename"):
            if d.get(chave):
                parciais.add(d[chave])
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            baixado = d.get("downloaded_bytes", 0)
            if total:
                msg_queue.put(("progresso", baixado / total * 100))
            pct = (d.get("_percent_str") or "").strip()
            vel = (d.get("_speed_str") or "").strip()
            eta = (d.get("_eta_str") or "").strip()
            texto = "Baixando..."
            if pct:
                texto += f"  {pct}"
            if vel:
                texto += f"   {vel}"
            if eta:
                texto += f"   faltam {eta}"
            msg_queue.put(("status", texto))
            # valores brutos para a janela calcular porcentagem, velocidade e
            # tempo restante somando o video e o audio
            msg_queue.put(("bytes", {
                "fluxo": d.get("filename"),
                "baixado": baixado,
                "total": total,
                "velocidade": d.get("speed"),
                "eta": d.get("eta"),
            }))
        elif status == "finished":
            msg_queue.put(("progresso", 100))
            texto = "Convertendo para MP3..." if modo == "audio" else "Convertendo para MP4..."
            msg_queue.put(("status", texto))

    def hook_pos(d):
        # a juncao de video+audio (Merger) ou a extracao do audio (ExtractAudio)
        # e a etapa "Convertendo"
        nome = d.get("postprocessor") or ""
        if d.get("status") == "started" and any(
            k in nome for k in ("Merger", "Convertor", "Remuxer", "ExtractAudio")
        ):
            if cancelar.is_set():
                raise yt_dlp.utils.DownloadCancelled("Cancelado pelo usuario")
            msg_queue.put(("convertendo", None))

    if modo == "audio":
        opcoes = {
            "format": FORMATO_AUDIO,
            # preferredquality "0" = a melhor (escala 0-10, nao e automatico:
            # sem isso o yt-dlp usa qualidade media por padrao).
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}
            ],
        }
    else:
        opcoes = {
            "format": FORMATO_VIDEO,
            "merge_output_format": "mp4",
        }
    opcoes.update({
        "outtmpl": os.path.join(pasta_saida, "%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s"),
        "progress_hooks": [hook],
        "postprocessor_hooks": [hook_pos],
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "noplaylist": True,
    })
    ff = ffmpeg_dir()
    if ff:
        opcoes["ffmpeg_location"] = ff

    def limpar_parciais():
        for p in parciais:
            for cand in (p, p + ".part", p + ".ytdl", p + ".part.ytdl"):
                try:
                    if os.path.isfile(cand):
                        os.remove(cand)
                except OSError:
                    pass

    try:
        os.makedirs(pasta_saida, exist_ok=True)
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(url, download=True)
            nome = ydl.prepare_filename(info)
        base, _ = os.path.splitext(nome)
        final = base + (".mp3" if modo == "audio" else ".mp4")
        msg_queue.put(("concluido", final if os.path.exists(final) else nome))
    except Exception as e:
        if cancelar.is_set() or isinstance(e, yt_dlp.utils.DownloadCancelled):
            limpar_parciais()
            msg_queue.put(("cancelado", None))
        else:
            msg_queue.put(("erro", str(e)))


# ---------------------------------------------------------------------------
# Janela
# ---------------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=C["fundo"])
        self.title(APP_TITLE)
        self.resizable(False, False)

        # o CustomTkinter troca o icone da janela uns 200 ms depois de abrir
        self.after(250, self._definir_icone)

        self.modo = "video"             # video (MP4) | audio (MP3)
        self.pasta_video = DEFAULT_DIR
        self.pasta_audio = DEFAULT_DIR_AUDIO
        self.msg_queue = queue.Queue()
        self.estado = "inicio"          # inicio | encontrado | baixando | concluido
        self.ocupado = False            # buscando informacoes ou baixando
        self.convertendo = False
        self.busca_id = 0
        self.info = None
        self.arquivo_final = None
        self.aviso = None               # banner de erro/aviso visivel (dict) ou None
        self.cancelar_evento = threading.Event()
        self._fluxos = {}
        self._quadro_spinner = 0

        self._criar_fontes()

        self.corpo = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.corpo.pack(fill="both", expand=True, padx=PAD_X, pady=PAD_Y)

        self._montar_cabecalho()
        self._montar_aviso()
        self._montar_campo_link()
        self._montar_modo()
        self._montar_cartao_video()
        self._montar_progresso()
        self._montar_sucesso()
        self._montar_destino()
        self._montar_botoes()

        self.bind("<Return>", lambda e: self._acao_principal())
        self.bind("<KP_Enter>", lambda e: self._acao_principal())
        self.bind("<Control-v>", self._ctrl_v_global)
        if sys.platform == "darwin":
            self.bind("<Command-v>", self._ctrl_v_global)
        self.bind("<Escape>", self._tecla_esc)
        self._mostrar("inicio")
        self._centralizar()
        self.after(100, self._ler_fila)

    # ----- construcao -----
    def _definir_icone(self):
        try:
            if sys.platform == "win32":
                self.iconbitmap(resource_path("icone.ico"))
            else:
                caminho = resource_path("icone.png")
                if os.path.isfile(caminho):
                    self._icone_janela = tk.PhotoImage(file=caminho).subsample(16, 16)
                    self.iconphoto(True, self._icone_janela)
        except Exception:
            pass

    def _criar_fontes(self):
        texto, titulo, semi = escolher_fontes(self)

        def f(tam, peso="normal", familia=None):
            if peso == "semibold":
                if semi:
                    return ctk.CTkFont(family=semi, size=tam)
                return ctk.CTkFont(family=familia or texto, size=tam, weight="bold")
            return ctk.CTkFont(family=familia or texto, size=tam, weight=peso)

        self.f_app = ctk.CTkFont(family=titulo, size=20, weight="bold")
        self.f_sub = f(13)
        self.f_secao = f(13, "semibold")
        self.f_campo = f(14)
        self.f_corpo = f(13)
        self.f_corpo_b = f(13, "semibold")
        self.f_botao = f(15, "semibold")
        self.f_botao_p = f(13, "semibold")
        self.f_video = f(15, "semibold")
        self.f_fonte = f(12, "semibold")
        self.f_pequeno = f(12)
        self.f_chip = f(12, "semibold")
        self.f_pct = ctk.CTkFont(family=titulo, size=26, weight="bold")
        self.f_aviso_t = f(14, "semibold")

    def _img(self, gerador, *args, chave_claro=None, chave_escuro=None, lado=16, **kw):
        """CTkImage com versao clara e escura de um icone desenhado em Pillow."""
        cl = gerador(lado, *[claro(a) for a in args], **kw)
        es = gerador(lado, *[escuro(a) for a in args], **kw)
        return ctk.CTkImage(light_image=cl, dark_image=es, size=(lado, lado))

    def _cartao(self, **kw):
        opcoes = dict(fg_color=C["superficie"], corner_radius=RAIO, border_width=1,
                      border_color=C["borda"])
        opcoes.update(kw)
        return ctk.CTkFrame(self.corpo, **opcoes)

    def _montar_cabecalho(self):
        self.cabecalho = ctk.CTkFrame(self.corpo, fg_color="transparent")
        self._img_app = ctk.CTkImage(light_image=icone_app(44), size=(44, 44))
        ctk.CTkLabel(self.cabecalho, text="", image=self._img_app).pack(side="left", padx=(0, 14))
        textos = ctk.CTkFrame(self.cabecalho, fg_color="transparent")
        textos.pack(side="left")
        ctk.CTkLabel(textos, text="SnapYou", font=self.f_app, text_color=C["texto"],
                     anchor="w", height=26).pack(anchor="w")
        ctk.CTkLabel(textos, text="Baixe vídeos e músicas do YouTube, Instagram, X e outros sites",
                     font=self.f_sub, text_color=C["texto_sec"], anchor="w", height=18).pack(anchor="w")
        self.cabecalho.pack(fill="x", pady=(0, 22))

    def _montar_aviso(self):
        """Banner de erro/aviso dentro da janela (substitui as caixas de dialogo)."""
        self.aviso_frame = ctk.CTkFrame(self.corpo, corner_radius=RAIO, border_width=1)
        interno = ctk.CTkFrame(self.aviso_frame, fg_color="transparent")
        interno.pack(fill="x", padx=(14, 8), pady=(12, 14))
        interno.columnconfigure(1, weight=1)
        self._img_alerta = self._img(icone_alerta, "erro", lado=20)
        self._img_info = self._img(icone_info, "texto_sec", lado=20)
        self.aviso_icone = ctk.CTkLabel(interno, text="", image=self._img_alerta, width=20, height=20)
        self.aviso_icone.grid(row=0, column=0, sticky="n", padx=(0, 10), pady=(2, 0))
        self.aviso_titulo = ctk.CTkLabel(interno, text="", font=self.f_aviso_t,
                                         text_color=C["texto"], anchor="w", justify="left", height=22)
        self.aviso_titulo.grid(row=0, column=1, sticky="ew")
        self.aviso_texto = ctk.CTkLabel(interno, text="", font=self.f_corpo,
                                        text_color=C["texto"], anchor="w", justify="left",
                                        wraplength=410)
        self.aviso_texto.grid(row=1, column=1, sticky="ew", pady=(2, 0))
        self.aviso_detalhe = ctk.CTkLabel(interno, text="", font=self.f_pequeno,
                                          text_color=C["texto_sec"], anchor="w", justify="left",
                                          wraplength=410)
        self.aviso_detalhe.grid(row=2, column=1, sticky="ew", pady=(4, 0))
        self.aviso_acao = ctk.CTkButton(
            interno, text="Tentar de novo", height=32, corner_radius=8, width=0,
            font=self.f_botao_p, fg_color=C["superficie"], hover_color=C["neutro_hover"],
            text_color=C["texto"], border_width=1, border_color=C["borda"],
            command=self._acao_do_aviso,
        )
        self.aviso_acao.grid(row=3, column=1, sticky="w", pady=(10, 0))
        self._img_fechar = self._img(icone_fechar, "texto_sec", lado=16)
        self.aviso_fechar = ctk.CTkButton(
            interno, text="", image=self._img_fechar, width=28, height=28, corner_radius=8,
            fg_color="transparent", hover_color=C["neutro_hover"], command=self._fechar_aviso,
        )
        self.aviso_fechar.grid(row=0, column=2, sticky="ne", padx=(6, 0))

    def _montar_campo_link(self):
        self.rotulo_link = ctk.CTkLabel(self.corpo, text="Link do vídeo", font=self.f_secao,
                                        text_color=C["texto"], anchor="w", height=18)
        self.campo = ctk.CTkFrame(self.corpo, height=50, corner_radius=RAIO, border_width=1,
                                  border_color=C["borda"], fg_color=C["superficie"])
        self.campo.pack_propagate(False)
        self._img_colar = self._img(icone_prancheta, "texto", lado=16)
        self.btn_colar = ctk.CTkButton(
            self.campo, text="Colar", image=self._img_colar, compound="left", width=88, height=34,
            corner_radius=8, font=self.f_botao_p, fg_color=C["neutro"], hover_color=C["neutro_hover"],
            text_color=C["texto"], command=self._colar,
        )
        self.btn_colar.pack(side="right", padx=(0, 8))
        self.entrada = ctk.CTkEntry(
            self.campo, border_width=0, fg_color="transparent", text_color=C["texto"],
            placeholder_text="Cole aqui o link do vídeo", placeholder_text_color=C["texto_terc"],
            font=self.f_campo, height=40,
        )
        self.entrada.pack(side="left", fill="x", expand=True, padx=(10, 4))
        self.entrada.bind("<KeyRelease>", lambda e: self._texto_mudou())
        self.entrada.bind("<FocusIn>", lambda e: self.campo.configure(border_color=C["acento"], border_width=2))
        self.entrada.bind("<FocusOut>", lambda e: self.campo.configure(border_color=C["borda"], border_width=1))

    def _montar_modo(self):
        self.seg_modo = ctk.CTkSegmentedButton(
            self.corpo,
            values=["Vídeo (MP4)", "Áudio (MP3)"],
            font=self.f_corpo_b,
            height=36,
            corner_radius=9,
            border_width=3,
            fg_color=C["trilha"],
            unselected_color=C["trilha"],
            unselected_hover_color=C["neutro_hover"],
            selected_color=C["seletor_ativo"],
            selected_hover_color=C["seletor_ativo"],
            text_color=C["texto"],
            command=self._selecionar_modo,
        )
        self.seg_modo.set("Vídeo (MP4)")

    def _selecionar_modo(self, valor):
        self.modo = "audio" if valor.startswith("Áudio") else "video"
        self.rotulo_link.configure(text="Link do vídeo")
        self._atualizar_rotulo_pasta()
        self._atualizar_botao()

    def _montar_cartao_video(self):
        self.cartao = self._cartao()
        self.lbl_miniatura = ctk.CTkLabel(self.cartao, text="", width=MINI_W, height=MINI_H,
                                          fg_color="transparent")
        self.lbl_miniatura.grid(row=0, column=0, padx=(12, 14), pady=12, sticky="nw")
        self.cartao.columnconfigure(1, weight=1)
        meta = ctk.CTkFrame(self.cartao, fg_color="transparent")
        meta.grid(row=0, column=1, sticky="nsew", padx=(0, 14), pady=(12, 10))
        self.lbl_fonte = ctk.CTkLabel(meta, text="", font=self.f_fonte, text_color=C["link"],
                                      anchor="w", height=16)
        self.lbl_fonte.pack(anchor="w")
        self.lbl_titulo = ctk.CTkLabel(meta, text="", font=self.f_video, text_color=C["texto"],
                                       anchor="w", justify="left")
        self.lbl_titulo.pack(anchor="w", pady=(2, 8))
        fatos = ctk.CTkFrame(meta, fg_color="transparent")
        fatos.pack(anchor="w")
        # chips: qualidade (destaque), formato e tamanho estimado
        self.chip_qual = ctk.CTkLabel(fatos, text="", font=self.f_chip, height=22, corner_radius=6,
                                      fg_color=C["acento_suave"], text_color=C["acento_suave_texto"])
        self.chip_formato = ctk.CTkLabel(fatos, text="", font=self.f_chip, height=22, corner_radius=6,
                                         fg_color=C["neutro"], text_color=C["texto"])
        self.chip_tamanho = ctk.CTkLabel(fatos, text="", font=self.f_pequeno, height=22,
                                         text_color=C["texto_sec"])
        self._chips = (self.chip_qual, self.chip_formato, self.chip_tamanho)
        self.lbl_qual_legenda = ctk.CTkLabel(meta, text="", font=self.f_pequeno,
                                             text_color=C["texto_sec"], anchor="w", height=16)
        self.lbl_qual_legenda.pack(anchor="w", pady=(6, 0))
        self._mostrar_miniatura(*miniaturas(None, ""))

    def _mostrar_miniatura(self, img_claro, img_escuro):
        self._img_miniatura = ctk.CTkImage(light_image=img_claro, dark_image=img_escuro,
                                           size=(MINI_W, MINI_H))
        self.lbl_miniatura.configure(image=self._img_miniatura)

    def _montar_progresso(self):
        self.progresso = self._cartao()
        interno = ctk.CTkFrame(self.progresso, fg_color="transparent")
        interno.pack(fill="x", padx=18, pady=(16, 16))
        interno.columnconfigure(0, weight=1)
        self.lbl_prog_titulo = ctk.CTkLabel(interno, text="Baixando…", font=self.f_video,
                                            text_color=C["texto"], anchor="sw", height=30)
        self.lbl_prog_titulo.grid(row=0, column=0, sticky="sw")
        self.lbl_pct = ctk.CTkLabel(interno, text="0%", font=self.f_pct, text_color=C["texto"],
                                    anchor="e", width=90, height=30)
        self.lbl_pct.grid(row=0, column=1, sticky="e")
        self.barra = ctk.CTkProgressBar(interno, height=6, corner_radius=3, fg_color=C["trilha"],
                                        progress_color=C["acento"])
        self.barra.set(0)
        self.barra.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 8))
        self.lbl_vel = ctk.CTkLabel(interno, text="", font=self.f_pequeno, text_color=C["texto_sec"],
                                    anchor="w", height=16)
        self.lbl_vel.grid(row=2, column=0, sticky="w")
        self.lbl_eta = ctk.CTkLabel(interno, text="", font=self.f_pequeno, text_color=C["texto_sec"],
                                    anchor="e", height=16)
        self.lbl_eta.grid(row=2, column=1, sticky="e")

        ctk.CTkFrame(self.progresso, height=1, fg_color=C["separador"], corner_radius=0).pack(
            fill="x", padx=1)
        self._montar_etapas(self.progresso)

    def _montar_etapas(self, pai):
        """Indicador de etapas: Informacoes -> Baixando -> Convertendo para MP4."""
        self.etapas = ctk.CTkFrame(pai, fg_color="transparent")
        self.etapas.pack(fill="x", padx=18, pady=(12, 14))
        self._img_et_ok = self._img(icone_check, "ok", lado=18)
        self._img_et_ativa = ctk.CTkImage(
            light_image=icone_etapa_ativa(18, claro("acento"), claro("acento_suave")),
            dark_image=icone_etapa_ativa(18, escuro("acento"), escuro("acento_suave")),
            size=(18, 18),
        )
        self._img_et_pend = self._img(icone_etapa_pendente, "texto_terc", lado=18)
        for c, peso in enumerate((0, 1, 0, 1, 0)):
            self.etapas.columnconfigure(c, weight=peso)
        self.lbl_et1 = ctk.CTkLabel(self.etapas, text=" Informações", compound="left",
                                    font=self.f_pequeno, height=20)
        self.lbl_et2 = ctk.CTkLabel(self.etapas, text=" Baixando", compound="left",
                                    font=self.f_pequeno, height=20)
        self.lbl_et3 = ctk.CTkLabel(self.etapas, text=" Convertendo para MP4", compound="left",
                                    font=self.f_pequeno, height=20)
        self.linha_et1 = ctk.CTkFrame(self.etapas, height=2, corner_radius=1, fg_color=C["borda"])
        self.linha_et2 = ctk.CTkFrame(self.etapas, height=2, corner_radius=1, fg_color=C["borda"])
        self.lbl_et1.grid(row=0, column=0)
        self.linha_et1.grid(row=0, column=1, sticky="ew", padx=10)
        self.lbl_et2.grid(row=0, column=2)
        self.linha_et2.grid(row=0, column=3, sticky="ew", padx=10)
        self.lbl_et3.grid(row=0, column=4)

    def _montar_sucesso(self):
        """Painel de concluido: confirmacao, nome do arquivo e atalhos para abrir."""
        self.sucesso = self._cartao()
        topo = ctk.CTkFrame(self.sucesso, fg_color="transparent")
        topo.pack(fill="x", padx=18, pady=(18, 0))
        topo.columnconfigure(1, weight=1)
        self._img_ok_grande = self._img(icone_check, "ok", lado=40)
        ctk.CTkLabel(topo, text="", image=self._img_ok_grande, width=40).grid(
            row=0, column=0, rowspan=2, sticky="n", padx=(0, 14))
        self.lbl_suc_titulo = ctk.CTkLabel(topo, text="Download concluído", font=self.f_video,
                                           text_color=C["texto"], anchor="w", height=22)
        self.lbl_suc_titulo.grid(row=0, column=1, sticky="w")
        self.lbl_arquivo = ctk.CTkLabel(topo, text="", font=self.f_pequeno, text_color=C["texto_sec"],
                                        anchor="w", justify="left")
        self.lbl_arquivo.grid(row=1, column=1, sticky="w", pady=(2, 0))

        botoes = ctk.CTkFrame(self.sucesso, fg_color="transparent")
        botoes.pack(fill="x", padx=18, pady=(16, 18))
        botoes.columnconfigure((0, 1), weight=1, uniform="b")
        self.btn_abrir_arquivo = ctk.CTkButton(
            botoes, text="Abrir arquivo", height=38, corner_radius=10, font=self.f_botao_p,
            fg_color=C["acento_suave"], hover_color=C["acento_suave_hover"],
            text_color=C["acento_suave_texto"], command=self._abrir_arquivo,
        )
        self.btn_abrir_arquivo.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.btn_mostrar_pasta = ctk.CTkButton(
            botoes, text="Mostrar na pasta", height=38, corner_radius=10, font=self.f_botao_p,
            fg_color=C["neutro"], hover_color=C["neutro_hover"], text_color=C["texto"],
            command=self._mostrar_na_pasta,
        )
        self.btn_mostrar_pasta.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _montar_destino(self):
        self.destino = self._cartao(height=62)
        self.destino.pack_propagate(False)
        self._img_pasta = ctk.CTkImage(
            light_image=icone_pasta(18, claro("acento")), dark_image=icone_pasta(18, escuro("link")),
            size=(18, 18),
        )
        ctk.CTkLabel(self.destino, text="", image=self._img_pasta, width=36, height=36,
                     fg_color=C["acento_suave"], corner_radius=9).pack(side="left", padx=(12, 12))
        textos = ctk.CTkFrame(self.destino, fg_color="transparent")
        textos.pack(side="left", fill="y", pady=10)
        ctk.CTkLabel(textos, text="Salvar em", font=self.f_pequeno, text_color=C["texto_sec"],
                     anchor="w", height=16).pack(anchor="w")
        self.lbl_pasta = ctk.CTkLabel(textos, text="", font=self.f_corpo_b, text_color=C["texto"],
                                      anchor="w", height=20)
        self.lbl_pasta.pack(anchor="w")
        for texto, comando in (("Trocar", self._trocar_pasta), ("Abrir", self._abrir_pasta)):
            ctk.CTkButton(
                self.destino, text=texto, width=64, height=32, corner_radius=8, font=self.f_corpo_b,
                fg_color="transparent", hover_color=C["acento_suave"], text_color=C["link"],
                command=comando,
            ).pack(side="right", padx=(0, 4 if texto == "Abrir" else 10))
        self._atualizar_rotulo_pasta()

    def _montar_botoes(self):
        self.btn = ctk.CTkButton(
            self.corpo, text="Buscar vídeo", height=48, corner_radius=RAIO, font=self.f_botao,
            fg_color=C["acento"], hover_color=C["acento_hover"], text_color="#FFFFFF",
            text_color_disabled=C["acento_texto_desab"], command=self._acao_principal,
        )
        self._spinner = [ctk.CTkImage(light_image=q, size=(18, 18)) for q in quadros_spinner(18)]
        self.btn_cancelar = ctk.CTkButton(
            self.corpo, text="Cancelar download", height=48, corner_radius=RAIO, font=self.f_botao,
            fg_color=C["neutro"], hover_color=C["neutro_hover"], text_color=C["texto"],
            text_color_disabled=C["texto_sec"], command=self._cancelar,
        )
        self.dica = ctk.CTkLabel(
            self.corpo, text=f"Dica: copie o link e clique em Colar, ou pressione {ATALHO_COLAR}.",
            font=self.f_pequeno, text_color=C["texto_sec"],
        )

    # ----- estados da tela -----
    def _mostrar(self, estado):
        self.estado = estado
        for w in (self.aviso_frame, self.rotulo_link, self.campo, self.seg_modo, self.cartao,
                  self.progresso, self.sucesso, self.destino, self.btn, self.btn_cancelar, self.dica):
            w.pack_forget()

        ordem = {
            "inicio": [self.rotulo_link, self.campo, self.seg_modo, self.destino, self.btn],
            "encontrado": [self.rotulo_link, self.campo, self.cartao, self.destino, self.btn],
            "baixando": [self.cartao, self.progresso, self.destino, self.btn_cancelar],
            "concluido": [self.cartao, self.sucesso, self.destino, self.btn],
        }[estado]
        if self.aviso:
            ordem = [self.aviso_frame] + ordem
        if estado == "inicio":
            ordem.append(self.dica)
        for w in ordem:
            if w is self.rotulo_link:
                w.pack(fill="x", pady=(0, 8))
            elif w is self.dica:
                w.pack(pady=(14, 0))
            elif w in (self.btn, self.btn_cancelar):
                w.pack(fill="x", pady=(4, 0))
            else:
                w.pack(fill="x", pady=(0, ESPACO))
        self._atualizar_botao()
        self._ajustar_janela()

    def _ajustar_janela(self):
        """A janela acompanha a altura do conteudo de cada tela."""
        self.update_idletasks()
        escala = self._get_window_scaling()
        altura = math.ceil(self.corpo.winfo_reqheight() / escala) + 2 * PAD_Y
        self.geometry(f"{LARGURA}x{max(altura, ALTURA_MIN)}")

    def _atualizar_botao(self):
        if self.estado == "baixando":
            if self.convertendo:
                self.btn_cancelar.configure(text="Finalizando…", state="disabled")
            elif self.cancelar_evento.is_set():
                self.btn_cancelar.configure(text="Cancelando…", state="disabled")
            else:
                self.btn_cancelar.configure(text="Cancelar download", state="normal")
            return
        rotulo = "áudio" if self.modo == "audio" else "vídeo"
        buscando = False
        if self.estado == "inicio":
            buscando = self.ocupado
            habilitado = bool(self.entrada.get().strip()) and not self.ocupado
            texto = "  Buscando…" if buscando else "Buscar vídeo"
        elif self.estado == "concluido":
            habilitado = True
            texto = f"Baixar outro {rotulo}"
        else:
            habilitado = not self.ocupado
            texto = f"Baixar {rotulo}"
        self.btn.configure(
            text=texto,
            state="normal" if habilitado else "disabled",
            fg_color=C["acento"] if (habilitado or buscando) else C["acento_desab"],
            text_color_disabled="#FFFFFF" if buscando else C["acento_texto_desab"],
        )
        if buscando:
            self._girar_spinner()
        else:
            self.btn.configure(image=None)

    def _girar_spinner(self):
        if not (self.ocupado and self.estado == "inicio"):
            return
        self._quadro_spinner = (self._quadro_spinner + 1) % len(self._spinner)
        self.btn.configure(image=self._spinner[self._quadro_spinner])
        if getattr(self, "_spinner_ativo", None) is None:
            self._spinner_ativo = self.after(70, self._passo_spinner)

    def _passo_spinner(self):
        self._spinner_ativo = None
        self._girar_spinner()

    def _texto_mudou(self):
        if self.ocupado:
            return
        if self.estado == "encontrado" and self.info and self.entrada.get().strip() != self.info["url"]:
            self.info = None
            self.aviso = None
            self._mostrar("inicio")
        else:
            self._atualizar_botao()

    # ----- avisos dentro da janela -----
    def _mostrar_aviso(self, tipo, titulo, texto, detalhe="", acao=None, rotulo_acao="Tentar de novo"):
        """tipo: erro | info. `acao` e chamada pelo botao do banner (ex.: tentar de novo)."""
        self.aviso = {"tipo": tipo, "acao": acao}
        if tipo == "erro":
            self.aviso_frame.configure(fg_color=C["erro_fundo"], border_color=C["erro_borda"])
            self.aviso_icone.configure(image=self._img_alerta)
        else:
            self.aviso_frame.configure(fg_color=C["info_fundo"], border_color=C["borda"])
            self.aviso_icone.configure(image=self._img_info)
        self.aviso_titulo.configure(text=titulo)
        self.aviso_texto.configure(text=texto)
        self.aviso_texto.grid() if texto else self.aviso_texto.grid_remove()
        if detalhe:
            curto = limitar_linhas(f"Detalhe técnico: {detalhe}", self.f_pequeno, 400, 2)
            self.aviso_detalhe.configure(text=curto)
            self.aviso_detalhe.grid()
        else:
            self.aviso_detalhe.grid_remove()
        if acao:
            self.aviso_acao.configure(text=rotulo_acao)
            self.aviso_acao.grid()
        else:
            self.aviso_acao.grid_remove()
        self._mostrar(self.estado)

    def _fechar_aviso(self):
        self.aviso = None
        self._mostrar(self.estado)

    def _acao_do_aviso(self):
        acao = (self.aviso or {}).get("acao")
        self.aviso = None
        if acao:
            acao()
        else:
            self._mostrar(self.estado)

    def _tecla_esc(self, _evento=None):
        if self.estado == "baixando":
            self._cancelar()
        elif self.aviso:
            self._fechar_aviso()

    # ----- acoes de botao -----
    def _colar(self):
        if self.ocupado or self.estado == "baixando":
            return
        if self.estado == "concluido":
            self._novo_download()
        try:
            texto = self.clipboard_get().strip()
        except tk.TclError:
            return
        if texto:
            self.entrada.delete(0, "end")
            self.entrada.insert(0, texto)
            self._texto_mudou()

    def _ctrl_v_global(self, evento):
        # com o foco no campo o proprio campo ja cola; fora dele, Ctrl+V tambem cola
        if self.focus_get() is not getattr(self.entrada, "_entry", None):
            self._colar()

    @property
    def pasta(self):
        """Pasta de destino: uma para video, outra para audio — cada modo
        guarda a sua, trocada automaticamente no alternador Video/Audio."""
        return self.pasta_audio if self.modo == "audio" else self.pasta_video

    @pasta.setter
    def pasta(self, valor):
        if self.modo == "audio":
            self.pasta_audio = valor
        else:
            self.pasta_video = valor

    def _trocar_pasta(self):
        rotulo = "áudios" if self.modo == "audio" else "vídeos"
        escolhida = filedialog.askdirectory(
            title=f"Escolha a pasta para salvar os {rotulo}",
            initialdir=self.pasta if os.path.isdir(self.pasta) else None,
        )
        if escolhida:
            self.pasta = os.path.normpath(escolhida)
            self._atualizar_rotulo_pasta()

    def _abrir_pasta(self):
        try:
            abrir_no_sistema(self.pasta)
        except Exception as e:
            self._mostrar_aviso("erro", "Não foi possível abrir a pasta", str(e).strip()[:200])

    def _abrir_arquivo(self):
        try:
            abrir_no_sistema(self.arquivo_final)
        except Exception as e:
            self._mostrar_aviso("erro", "Não foi possível abrir o arquivo", str(e).strip()[:200])

    def _mostrar_na_pasta(self):
        try:
            mostrar_na_pasta(self.arquivo_final)
        except Exception as e:
            self._mostrar_aviso("erro", "Não foi possível mostrar o arquivo", str(e).strip()[:200])

    def _atualizar_rotulo_pasta(self):
        nome = os.path.basename(os.path.normpath(self.pasta)) or self.pasta
        if len(nome) > 26:
            nome = nome[:25].rstrip() + "…"
        self.lbl_pasta.configure(text=nome)

    def _acao_principal(self):
        if self.ocupado or str(self.btn.cget("state")) == "disabled":
            return
        if self.estado == "inicio":
            self._buscar()
        elif self.estado == "encontrado":
            self._baixar()
        elif self.estado == "concluido":
            self._novo_download()

    def _buscar(self):
        url = self.entrada.get().strip()
        if not url:
            return
        self.ocupado = True
        self.aviso = None
        self.busca_id += 1
        self.entrada.configure(state="disabled")
        self.btn_colar.configure(state="disabled")
        self.seg_modo.configure(state="disabled")
        self._mostrar("inicio")
        threading.Thread(
            target=buscar_info, args=(url, self.busca_id, self.msg_queue, self.modo), daemon=True
        ).start()

    def _liberar_campo(self):
        self.entrada.configure(state="normal")
        self.btn_colar.configure(state="normal")
        self.seg_modo.configure(state="normal")

    def _baixar(self):
        if not self.info:
            return
        self.ocupado = True
        self.convertendo = False
        self.aviso = None
        self.cancelar_evento = threading.Event()
        self._fluxos = {}
        self.barra.set(0)
        self.lbl_prog_titulo.configure(text="Baixando…")
        self.lbl_pct.configure(text="0%")
        self.lbl_vel.configure(text="Iniciando…")
        self.lbl_eta.configure(text="")
        self._pintar_etapa("baixando")
        self._mostrar("baixando")
        threading.Thread(
            target=baixar,
            args=(self.info["url"], self.pasta, self.msg_queue, self.modo, self.cancelar_evento),
            daemon=True,
        ).start()

    def _cancelar(self):
        if self.estado != "baixando" or self.convertendo or self.cancelar_evento.is_set():
            return
        self.cancelar_evento.set()
        self.lbl_prog_titulo.configure(text="Cancelando…")
        self._atualizar_botao()

    # ----- cartao e progresso -----
    def _preencher_cartao(self, d):
        self.lbl_fonte.configure(text=nome_da_fonte(d["fonte"]))
        titulo = limitar_linhas(d["titulo"], self.f_video, 276, 2)
        self.lbl_titulo.configure(text=titulo, wraplength=300, height=20 * (titulo.count("\n") + 1))
        duracao = formatar_duracao(d["duracao"])
        if d["modo"] == "audio":
            qual = f"{int(d['abr'])} kbps" if d["abr"] else ""
            formato = "MP3"
        else:
            qual = f"{d['altura']}p" if d["altura"] else ""
            formato = "MP4"
        tamanho = formatar_tamanho(d["tamanho"])
        for chip in self._chips:
            chip.pack_forget()
        if qual:
            self.chip_qual.configure(text=f"  {qual}  ")
            self.chip_qual.pack(side="left", padx=(0, 6))
        self.chip_formato.configure(text=f"  {formato}  ")
        self.chip_formato.pack(side="left", padx=(0, 8))
        if tamanho:
            self.chip_tamanho.configure(text=f"≈ {tamanho}")
            self.chip_tamanho.pack(side="left")
        partes = []
        if duracao:
            partes.append(duracao)
        if qual:
            partes.append("melhor qualidade disponível")
        self.lbl_qual_legenda.configure(text=" · ".join(partes))
        self._mostrar_miniatura(*miniaturas(None, duracao))

    def _pintar_etapa(self, etapa):
        """etapa: baixando | convertendo | pronto"""
        rotulo = "Convertendo para MP3" if self.modo == "audio" else "Convertendo para MP4"
        ok = dict(image=self._img_et_ok, text_color=C["texto"])
        ativa = dict(image=self._img_et_ativa, text_color=C["texto"])
        pend = dict(image=self._img_et_pend, text_color=C["texto_sec"])
        self.lbl_et1.configure(text=" Informações", **ok)
        self.linha_et1.configure(fg_color=C["ok"])
        if etapa == "baixando":
            self.lbl_et2.configure(text=" Baixando", **ativa)
            self.linha_et2.configure(fg_color=C["borda"])
            self.lbl_et3.configure(text=f" {rotulo}", **pend)
        elif etapa == "convertendo":
            self.lbl_et2.configure(text=" Baixando", **ok)
            self.linha_et2.configure(fg_color=C["ok"])
            self.lbl_et3.configure(text=f" {rotulo}", **ativa)
        else:
            self.lbl_et2.configure(text=" Baixando", **ok)
            self.linha_et2.configure(fg_color=C["ok"])
            self.lbl_et3.configure(text=f" {rotulo}", **ok)

    def _atualizar_bytes(self, d):
        """Soma video + audio: sao dois arquivos baixados em sequencia."""
        if self.cancelar_evento.is_set():
            return
        self._fluxos[d["fluxo"]] = (d["baixado"], d["total"])
        baixado = sum(b for b, _ in self._fluxos.values())
        vistos = sum(t for _, t in self._fluxos.values())
        total = max((self.info or {}).get("tamanho") or 0, vistos)
        fracao = min(baixado / total, 1.0) if total else 0.0
        self.barra.set(fracao)
        self.lbl_pct.configure(text=f"{int(fracao * 100)}%")
        vel = formatar_velocidade(d["velocidade"])
        tam = formatar_tamanho(total)
        self.lbl_vel.configure(text=f"{formatar_tamanho(baixado) or '0 KB'} de {tam}  ·  {vel}" if tam and vel
                               else vel)
        if d["velocidade"] and total:
            restante = max(total - baixado, 0) / d["velocidade"]
        else:
            restante = d["eta"]
        self.lbl_eta.configure(text=f"faltam {formatar_duracao(restante) or '0:00'}" if restante is not None else "")

    # ----- ponte thread -> janela -----
    def _ler_fila(self):
        try:
            while True:
                tipo, dado = self.msg_queue.get_nowait()
                if tipo == "info":
                    self._ao_receber_info(dado)
                elif tipo == "miniatura":
                    self._ao_receber_miniatura(*dado)
                elif tipo == "erro_busca":
                    self._fim_erro_busca(*dado)
                elif tipo == "bytes":
                    if self.estado == "baixando":
                        self._atualizar_bytes(dado)
                elif tipo == "convertendo":
                    self._ao_converter()
                elif tipo == "concluido":
                    self._fim_ok(dado)
                elif tipo == "cancelado":
                    self._fim_cancelado()
                elif tipo == "erro":
                    self._fim_erro(dado)
                # "progresso" e "status" continuam sendo enviados por baixar(),
                # mas a janela usa "bytes" (soma video + audio)
        except queue.Empty:
            pass
        self.after(100, self._ler_fila)

    def _ao_receber_info(self, dados):
        if dados["id"] != self.busca_id:
            return
        self.info = dados
        self.ocupado = False
        self._liberar_campo()
        self._preencher_cartao(dados)
        self._mostrar("encontrado")

    def _ao_receber_miniatura(self, busca_id, imagens):
        if busca_id != self.busca_id or self.info is None:
            return
        self._mostrar_miniatura(*imagens)

    def _ao_converter(self):
        if self.estado != "baixando" or self.cancelar_evento.is_set():
            return
        self.convertendo = True
        texto = "Convertendo para MP3…" if self.modo == "audio" else "Convertendo para MP4…"
        self.lbl_prog_titulo.configure(text=texto)
        self.barra.set(1.0)
        self.lbl_pct.configure(text="100%")
        self.lbl_vel.configure(text="Quase pronto")
        self.lbl_eta.configure(text="")
        self._pintar_etapa("convertendo")
        self._atualizar_botao()

    def _fim_ok(self, caminho):
        self.ocupado = False
        self.convertendo = False
        self.arquivo_final = caminho
        self.barra.set(1.0)
        self.lbl_pct.configure(text="100%")
        self._pintar_etapa("pronto")
        self.lbl_prog_titulo.configure(text="Concluído")
        self.lbl_vel.configure(text="")
        self.lbl_eta.configure(text="")
        nome = os.path.basename(caminho)
        pasta = os.path.basename(os.path.dirname(caminho)) or os.path.dirname(caminho)
        self.lbl_arquivo.configure(
            text=limitar_linhas(nome, self.f_pequeno, 400, 2) + f"\nSalvo em {pasta}")
        self._mostrar("concluido")

    def _novo_download(self):
        self.info = None
        self.arquivo_final = None
        self.aviso = None
        self.lbl_prog_titulo.configure(text="Baixando…")
        self.entrada.delete(0, "end")
        self._mostrar("inicio")
        self.entrada.focus_set()

    def _fim_cancelado(self):
        self.ocupado = False
        self.convertendo = False
        self.lbl_prog_titulo.configure(text="Baixando…")
        self.estado = "encontrado"
        self._mostrar_aviso("info", "Download cancelado",
                            "Os arquivos incompletos foram apagados. Você pode baixar de novo quando quiser.")

    def _fim_erro(self, mensagem):
        self.ocupado = False
        self.convertendo = False
        self.lbl_prog_titulo.configure(text="Baixando…")
        titulo, texto, detalhe = explicar_erro(mensagem, "download")
        self.estado = "encontrado"
        self._mostrar_aviso("erro", titulo, texto, detalhe, acao=self._baixar)

    def _fim_erro_busca(self, busca_id, mensagem):
        if busca_id != self.busca_id:
            return
        self.ocupado = False
        self._liberar_campo()
        titulo, texto, detalhe = explicar_erro(mensagem, "busca")
        self.estado = "inicio"
        self._mostrar_aviso("erro", titulo, texto, detalhe, acao=self._buscar)

    def _centralizar(self):
        self.update_idletasks()
        escala = self._get_window_scaling()
        altura = math.ceil(self.corpo.winfo_reqheight() / escala) + 2 * PAD_Y
        w, h = int(LARGURA * escala), int(max(altura, ALTURA_MIN) * escala)
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"{LARGURA}x{max(altura, ALTURA_MIN)}+{x}+{y}")


if __name__ == "__main__":
    ctk.set_appearance_mode("system")   # claro por padrao; segue o tema do sistema
    App().mainloop()
