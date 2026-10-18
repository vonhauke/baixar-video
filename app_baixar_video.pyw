#!/usr/bin/env python3
"""
app_baixar_video.pyw

SnapYou: aplicativo de janela para baixar videos do YouTube (e outros sites
suportados pelo yt-dlp). Cole o link, clique em "Buscar video" para ver a
miniatura, o titulo, a duracao e a melhor qualidade, e depois em "Baixar
video". O video e salvo em MP4 na pasta escolhida.

Empacotado como .exe com PyInstaller (ver build_exe.py). O ffmpeg vai junto
dentro do executavel, entao nao precisa de nada instalado na maquina.

Visual: CustomTkinter, seguindo maquete_baixar_video.png (tema escuro).
"""

import functools
import io
import math
import os
import sys
import queue
import threading
import subprocess
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox
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

# ---------------------------------------------------------------------------
# Medidas e cores (copiadas de maquete_baixar_video.html)
# ---------------------------------------------------------------------------
LARGURA, ALTURA = 520, 528          # area util da janela (sem a barra de titulo)
PAD_X, PAD_Y = 28, 24
ESC = 3                             # imagens desenhadas em 3x para telas HiDPI

COR_FUNDO = "#14171c"
COR_CARTAO = "#1c2027"
COR_BORDA = "#343a45"
COR_BORDA_FOCO = "#4a5160"
COR_TEXTO = "#ece6d8"
COR_TEXTO_SEC = "#8b919b"
COR_TEXTO_FRACO = "#5f656f"
COR_TEXTO_PASTA = "#b8b2a5"
COR_ACENTO = "#d4a24c"
COR_ACENTO_HOVER = "#e0b262"
COR_ACENTO_TEXTO = "#1a1408"
COR_ACENTO_DESAB = "#6a5632"        # acento a 45% sobre o fundo (".dis" da maquete)
COR_ACENTO_TEXTO_DESAB = "#171513"
COR_COLAR = "#262b34"
COR_COLAR_HOVER = "#2f3540"
COR_TRILHA = "#2a2f38"
COR_OK = "#7fb38a"

# melhor video+audio em MP4; cai para o melhor arquivo unico se preciso.
# Usado na busca de informacoes e no download, para que a qualidade mostrada
# no cartao seja a que sera de fato baixada.
FORMATO = "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b"


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


def abrir_pasta(caminho):
    try:
        os.makedirs(caminho, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(caminho)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", caminho], check=True)
        else:
            subprocess.run(["xdg-open", caminho], check=True)
    except Exception as e:
        messagebox.showwarning(APP_TITLE, f"Nao foi possivel abrir a pasta:\n{e}")


def formatar_duracao(segundos):
    """12:47 ou 1:02:03."""
    if not segundos:
        return ""
    segundos = int(segundos)
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def formatar_velocidade(bytes_por_s):
    """4,8 MB/s (decimal, virgula) como na maquete."""
    if not bytes_por_s:
        return ""
    mb = bytes_por_s / 1_000_000
    if mb >= 1:
        return f"{mb:.1f}".replace(".", ",") + " MB/s"
    return f"{bytes_por_s / 1000:.0f} KB/s"


# ---------------------------------------------------------------------------
# Imagens desenhadas com Pillow (icones e miniatura)
# ---------------------------------------------------------------------------
def _fonte_pil(tamanho_px, negrito=False):
    nomes = ("segoeuib.ttf", "arialbd.ttf") if negrito else ("segoeui.ttf", "arial.ttf")
    for nome in nomes + ("DejaVuSans.ttf",):
        try:
            return ImageFont.truetype(nome, int(tamanho_px))
        except OSError:
            continue
    return ImageFont.load_default(size=int(tamanho_px))


def _hex(cor, alfa=255):
    cor = cor.lstrip("#")
    return (int(cor[0:2], 16), int(cor[2:4], 16), int(cor[4:6], 16), alfa)


def icone_app(lado=34):
    """Icone do cabecalho (placa escura com seta dourada), igual ao SVG da maquete."""
    n = lado * ESC * 4
    s = n / 1024
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))

    grad = Image.new("RGBA", (n, n))
    gd = ImageDraw.Draw(grad)
    for y in range(n):
        t = y / (n - 1)
        cor = tuple(int(a + (b - a) * t) for a, b in zip(_hex("#2a2f38")[:3], _hex("#14171c")[:3]))
        gd.line([(0, y), (n, y)], fill=cor + (255,))
    mascara = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, n - 1, n - 1], radius=228 * s, fill=255)
    img.paste(grad, (0, 0), mascara)

    borda = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(borda).rounded_rectangle(
        [0, 0, n - 1, n - 1], radius=228 * s, outline=(255, 255, 255, 34), width=max(1, int(8 * s))
    )
    img = Image.alpha_composite(img, borda)

    d = ImageDraw.Draw(img)
    ouro = _hex(COR_ACENTO)
    d.rounded_rectangle([452 * s, 210 * s, 572 * s, 540 * s], radius=18 * s, fill=ouro)
    d.polygon([(300 * s, 470 * s), (724 * s, 470 * s), (512 * s, 700 * s)], fill=ouro)
    d.rounded_rectangle([290 * s, 760 * s, 734 * s, 830 * s], radius=35 * s, fill=_hex(COR_TEXTO))
    return img.resize((lado * ESC, lado * ESC), Image.LANCZOS)


def _caminho_arredondado(vertices, passos=8):
    """Polilinha fechada a partir de (x, y, raio); raio 0 = quina viva."""
    pts = []
    n = len(vertices)
    for i, (x, y, r) in enumerate(vertices):
        if r == 0:
            pts.append((x, y))
            continue
        px, py, _ = vertices[i - 1]
        nx, ny, _ = vertices[(i + 1) % n]

        def unit(ax, ay):
            dx, dy = ax - x, ay - y
            comp = math.hypot(dx, dy)
            return dx / comp, dy / comp

        ux, uy = unit(px, py)
        vx, vy = unit(nx, ny)
        p0 = (x + ux * r, y + uy * r)
        p2 = (x + vx * r, y + vy * r)
        for k in range(passos + 1):
            t = k / passos
            pts.append((
                (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * x + t ** 2 * p2[0],
                (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * y + t ** 2 * p2[1],
            ))
    return pts + [pts[0]]


def icone_prancheta(lado=16, cor=COR_TEXTO):
    n = lado * ESC * 4
    s = n / 24
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    traco = int(2 * s)
    d.rounded_rectangle([4 * s, 5 * s, 20 * s, 21 * s], radius=2 * s, outline=_hex(cor), width=traco)
    d.rectangle([7 * s, 2 * s, 17 * s, 8 * s], fill=(0, 0, 0, 0))       # abre a borda de cima
    d.rounded_rectangle([8 * s, 3 * s, 16 * s, 7 * s], radius=1 * s, outline=_hex(cor), width=traco)
    return img.resize((lado * ESC, lado * ESC), Image.LANCZOS)


def icone_pasta(lado=18, cor=COR_TEXTO_SEC):
    n = lado * ESC * 4
    s = n / 24
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = _caminho_arredondado(
        [(3, 5, 2), (9, 5, 0), (11, 7, 0), (21, 7, 2), (21, 19, 2), (3, 19, 2)]
    )
    pts = [(x * s, y * s) for x, y in pts]
    d.line(pts, fill=_hex(cor), width=int(2 * s), joint="curve")
    return img.resize((lado * ESC, lado * ESC), Image.LANCZOS)


@functools.lru_cache(maxsize=1)
def _gradiente_miniatura(w, h):
    """Degrade de 135 graus da maquete (#3a3326 -> #22262e a 60% -> #2b3240),
    usado enquanto a miniatura real nao chega. Calculado uma vez so."""
    base = Image.new("RGBA", (w, h))
    px = base.load()
    pontos = [(0.0, _hex("#3a3326")), (0.6, _hex("#22262e")), (1.0, _hex("#2b3240"))]
    for y in range(h):
        for x in range(w):
            t = (x / w + y / h) / 2
            for (t0, c0), (t1, c1) in zip(pontos, pontos[1:]):
                if t <= t1:
                    k = (t - t0) / (t1 - t0)
                    px[x, y] = tuple(int(a + (b - a) * k) for a, b in zip(c0, c1))
                    break
    return base


def montar_miniatura(foto, duracao_texto):
    """Miniatura 150x84 como na maquete: cantos de 8px, botao de play e a
    duracao no canto. `foto` e uma PIL.Image (ou None para o degrade padrao)."""
    w, h = 150 * ESC, 84 * ESC

    if foto is not None:
        base = ImageOps.fit(foto.convert("RGB"), (w, h), Image.LANCZOS).convert("RGBA")
    else:
        base = _gradiente_miniatura(w, h).copy()

    ss = 4  # sobreamostragem do que e desenhado por cima
    cam = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    u = ESC * ss  # 1 px da maquete
    cx, cy = w * ss / 2, h * ss / 2
    k = 34 / 24  # o SVG do play tem 34px num quadro de 24
    ox, oy = cx - 17 * u, cy - 17 * u
    d.ellipse([ox + (12 - 11) * k * u, oy + (12 - 11) * k * u,
               ox + (12 + 11) * k * u, oy + (12 + 11) * k * u], fill=(0, 0, 0, 0x66))
    d.polygon([(ox + 10 * k * u, oy + 8 * k * u), (ox + 16 * k * u, oy + 12 * k * u),
               (ox + 10 * k * u, oy + 16 * k * u)], fill=_hex(COR_TEXTO))

    if duracao_texto:
        fonte = _fonte_pil(11 * u)
        caixa = d.textbbox((0, 0), duracao_texto, font=fonte)
        tw, th = caixa[2] - caixa[0], caixa[3] - caixa[1]
        bw, bh = tw + 10 * u, th + 6 * u
        x1, y1 = w * ss - 6 * u, h * ss - 5 * u
        d.rounded_rectangle([x1 - bw, y1 - bh, x1, y1], radius=4 * u, fill=(0, 0, 0, 0xaa))
        d.text((x1 - bw + 5 * u - caixa[0], y1 - bh + 3 * u - caixa[1]), duracao_texto,
               font=fonte, fill=_hex(COR_TEXTO))

    cam = cam.resize((w, h), Image.LANCZOS)
    base = Image.alpha_composite(base, cam)

    mascara = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        [0, 0, w * ss - 1, h * ss - 1], radius=8 * ESC * ss, fill=255
    )
    mascara = mascara.resize((w, h), Image.LANCZOS)
    saida = Image.new("RGB", (w, h), COR_CARTAO)
    saida.paste(base, (0, 0), mascara)
    return saida


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
def buscar_info(url, busca_id, msg_queue):
    """Busca so os metadados (sem baixar), manda o resultado e depois a miniatura."""
    opcoes = {
        "format": FORMATO,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
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
        "titulo": info.get("title") or "Sem titulo",
        "duracao": info.get("duration"),
        "fonte": (info.get("extractor_key") or info.get("extractor") or "").upper(),
        "altura": max((f.get("height") or 0 for f in formatos), default=0) or None,
        "tamanho": sum(f.get("filesize") or f.get("filesize_approx") or 0 for f in formatos) or None,
    }
    msg_queue.put(("info", dados))

    foto = baixar_foto(info.get("thumbnail"))
    msg_queue.put(("miniatura", (busca_id, montar_miniatura(foto, formatar_duracao(dados["duracao"])))))


def baixar(url, pasta_saida, msg_queue):
    """Baixa o video e envia o andamento pela fila msg_queue."""

    def hook(d):
        status = d.get("status")
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
            msg_queue.put(("status", "Convertendo para MP4..."))

    def hook_pos(d):
        # a juncao de video e audio (ffmpeg) e a etapa "Convertendo para MP4"
        nome = d.get("postprocessor") or ""
        if d.get("status") == "started" and any(k in nome for k in ("Merger", "Convertor", "Remuxer")):
            msg_queue.put(("convertendo", None))

    opcoes = {
        "format": FORMATO,
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(
            pasta_saida, "%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s"
        ),
        "progress_hooks": [hook],
        "postprocessor_hooks": [hook_pos],
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
    }
    ff = ffmpeg_dir()
    if ff:
        opcoes["ffmpeg_location"] = ff

    try:
        os.makedirs(pasta_saida, exist_ok=True)
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(url, download=True)
            nome = ydl.prepare_filename(info)
        base, _ = os.path.splitext(nome)
        final = base + ".mp4"
        msg_queue.put(("concluido", final if os.path.exists(final) else nome))
    except Exception as e:
        msg_queue.put(("erro", str(e)))


# ---------------------------------------------------------------------------
# Janela
# ---------------------------------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=COR_FUNDO)
        self.title(APP_TITLE)
        self.resizable(False, False)

        # o CustomTkinter troca o icone da janela uns 200 ms depois de abrir
        self.after(250, self._definir_icone)

        self.pasta = DEFAULT_DIR
        self.msg_queue = queue.Queue()
        self.estado = "inicio"          # inicio | encontrado | baixando
        self.ocupado = False            # buscando informacoes ou baixando
        self.busca_id = 0
        self.info = None
        self._fluxos = {}
        self._imagens = []              # mantem as imagens vivas

        familia = tkfont.nametofont("TkDefaultFont").actual("family")
        self.f_titulo = ctk.CTkFont(family=familia, size=20, weight="bold")
        self.f_sub = ctk.CTkFont(family=familia, size=13)
        self.f_rotulo = ctk.CTkFont(family=familia, size=12)
        self.f_campo = ctk.CTkFont(family=familia, size=14)
        self.f_pequeno = ctk.CTkFont(family=familia, size=13)
        self.f_negrito = ctk.CTkFont(family=familia, size=13, weight="bold")
        self.f_botao = ctk.CTkFont(family=familia, size=14, weight="bold")
        self.f_fonte = ctk.CTkFont(family=familia, size=11, weight="bold")
        self.f_video = ctk.CTkFont(family=familia, size=14, weight="bold")
        self.f_fatos = ctk.CTkFont(family=familia, size=12)
        self.f_fatos_b = ctk.CTkFont(family=familia, size=12, weight="bold")
        self.f_pct = ctk.CTkFont(family=familia, size=22, weight="bold")
        self.f_dica = ctk.CTkFont(family=familia, size=12)

        self.corpo = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.corpo.pack(fill="both", expand=True, padx=PAD_X, pady=(PAD_Y, 0))

        self._montar_cabecalho()
        self._montar_campo_link()
        self._montar_cartao_video()
        self._montar_progresso()
        self._montar_etapas()
        self._montar_destino()
        self.btn = ctk.CTkButton(
            self.corpo, text="Buscar vídeo", height=44, corner_radius=10, font=self.f_botao,
            fg_color=COR_ACENTO, hover_color=COR_ACENTO_HOVER, text_color=COR_ACENTO_TEXTO,
            text_color_disabled=COR_ACENTO_TEXTO_DESAB, command=self._acao_principal,
        )
        self.dica = ctk.CTkLabel(
            self.corpo, text="Dica: copie o link e clique em Colar.",
            font=self.f_dica, text_color=COR_TEXTO_FRACO,
        )

        self.bind("<Return>", lambda e: self._acao_principal())
        self.bind("<Control-v>", self._ctrl_v_global)
        self._mostrar("inicio")
        self._centralizar()
        self.after(100, self._ler_fila)

    # ----- construcao -----
    def _definir_icone(self):
        try:
            self.iconbitmap(resource_path("icone.ico"))
        except Exception:
            pass

    def _montar_cabecalho(self):
        self.cabecalho = ctk.CTkFrame(self.corpo, fg_color="transparent")
        self._img_app = ctk.CTkImage(light_image=icone_app(34), size=(34, 34))
        ctk.CTkLabel(self.cabecalho, text="", image=self._img_app).pack(side="left", padx=(0, 12))
        textos = ctk.CTkFrame(self.cabecalho, fg_color="transparent")
        textos.pack(side="left")
        ctk.CTkLabel(textos, text="SnapYou", font=self.f_titulo, text_color=COR_TEXTO,
                     anchor="w", height=26).pack(anchor="w")
        ctk.CTkLabel(textos, text="YouTube, Instagram, X e outros sites", font=self.f_sub,
                     text_color=COR_TEXTO_SEC, anchor="w", height=18).pack(anchor="w")
        self.cabecalho.pack(fill="x", pady=(0, 20))

    def _montar_campo_link(self):
        self.rotulo_link = ctk.CTkLabel(self.corpo, text="LINK DO VÍDEO", font=self.f_rotulo,
                                        text_color=COR_TEXTO_SEC, anchor="w", height=16)
        self.campo = ctk.CTkFrame(self.corpo, height=46, corner_radius=10, border_width=1,
                                  border_color=COR_BORDA, fg_color=COR_CARTAO)
        self.campo.pack_propagate(False)
        self._img_colar = ctk.CTkImage(light_image=icone_prancheta(16), size=(16, 16))
        self.btn_colar = ctk.CTkButton(
            self.campo, text=" Colar", image=self._img_colar, compound="left", width=84, height=32,
            corner_radius=7, font=self.f_pequeno, fg_color=COR_COLAR, hover_color=COR_COLAR_HOVER,
            text_color=COR_TEXTO, command=self._colar,
        )
        self.btn_colar.pack(side="right", padx=(0, 6))
        self.entrada = ctk.CTkEntry(
            self.campo, border_width=0, fg_color="transparent", text_color=COR_TEXTO,
            placeholder_text="Cole aqui o link…", placeholder_text_color=COR_TEXTO_FRACO,
            font=self.f_campo, height=40,
        )
        self.entrada.pack(side="left", fill="x", expand=True, padx=(8, 4))
        self.entrada.bind("<KeyRelease>", lambda e: self._texto_mudou())
        self.entrada.bind("<FocusIn>", lambda e: self.campo.configure(border_color=COR_BORDA_FOCO))
        self.entrada.bind("<FocusOut>", lambda e: self.campo.configure(border_color=COR_BORDA))

    def _montar_cartao_video(self):
        self.cartao = ctk.CTkFrame(self.corpo, fg_color=COR_CARTAO, corner_radius=12)
        self.lbl_miniatura = ctk.CTkLabel(self.cartao, text="", width=150, height=84,
                                          fg_color="transparent")
        self.lbl_miniatura.pack(side="left", padx=12, pady=12)
        meta = ctk.CTkFrame(self.cartao, fg_color="transparent")
        meta.pack(side="left", fill="both", expand=True, padx=(2, 12), pady=12)
        self.lbl_fonte = ctk.CTkLabel(meta, text="", font=self.f_fonte, text_color=COR_ACENTO,
                                      anchor="w", height=14)
        self.lbl_fonte.pack(anchor="w")
        self.lbl_titulo = ctk.CTkLabel(meta, text="", font=self.f_video, text_color=COR_TEXTO,
                                       anchor="w", justify="left")
        self.lbl_titulo.pack(anchor="w", pady=(3, 6))
        fatos = ctk.CTkFrame(meta, fg_color="transparent")
        fatos.pack(anchor="w")
        self.lbl_fatos1 = ctk.CTkLabel(fatos, text="", font=self.f_fatos, text_color=COR_TEXTO_SEC,
                                       height=16)
        self.lbl_fatos2 = ctk.CTkLabel(fatos, text="", font=self.f_fatos_b, text_color=COR_TEXTO,
                                       height=16)
        self.lbl_fatos3 = ctk.CTkLabel(fatos, text="", font=self.f_fatos, text_color=COR_TEXTO_SEC,
                                       height=16)
        for lbl in (self.lbl_fatos1, self.lbl_fatos2, self.lbl_fatos3):
            lbl.pack(side="left")
        self._img_miniatura = ctk.CTkImage(light_image=montar_miniatura(None, ""), size=(150, 84))
        self.lbl_miniatura.configure(image=self._img_miniatura)

    def _montar_progresso(self):
        self.progresso = ctk.CTkFrame(self.corpo, fg_color=COR_CARTAO, corner_radius=12)
        interno = ctk.CTkFrame(self.progresso, fg_color="transparent")
        interno.pack(fill="x", padx=16, pady=16)
        interno.columnconfigure(0, weight=1)
        self.lbl_prog_titulo = ctk.CTkLabel(interno, text="Baixando…", font=self.f_video,
                                            text_color=COR_TEXTO, anchor="w", height=20)
        self.lbl_prog_titulo.grid(row=0, column=0, sticky="w")
        self.lbl_pct = ctk.CTkLabel(interno, text="0%", font=self.f_pct, text_color=COR_ACENTO)
        self.lbl_pct.grid(row=0, column=1, sticky="e")
        self.barra = ctk.CTkProgressBar(interno, height=8, corner_radius=4, fg_color=COR_TRILHA,
                                        progress_color=COR_ACENTO)
        self.barra.set(0)
        self.barra.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 8))
        self.lbl_vel = ctk.CTkLabel(interno, text="", font=self.f_fatos, text_color=COR_TEXTO_SEC,
                                    anchor="w", height=16)
        self.lbl_vel.grid(row=2, column=0, sticky="w")
        self.lbl_eta = ctk.CTkLabel(interno, text="", font=self.f_fatos, text_color=COR_TEXTO_SEC,
                                    anchor="e", height=16)
        self.lbl_eta.grid(row=2, column=1, sticky="e")

    def _montar_etapas(self):
        self.etapas = ctk.CTkFrame(self.corpo, fg_color="transparent")
        for c in range(3):
            self.etapas.columnconfigure(c, weight=1, uniform="etapa")
        self.lbl_et1 = ctk.CTkLabel(self.etapas, text="✓ Informações", font=self.f_fatos,
                                    text_color=COR_OK, anchor="w", height=16)
        self.lbl_et2 = ctk.CTkLabel(self.etapas, text="● Baixando", font=self.f_fatos,
                                    text_color=COR_TEXTO, anchor="center", height=16)
        self.lbl_et3 = ctk.CTkLabel(self.etapas, text="○ Convertendo para MP4", font=self.f_fatos,
                                    text_color=COR_TEXTO_FRACO, anchor="e", height=16)
        self.lbl_et1.grid(row=0, column=0, sticky="w", padx=4)
        self.lbl_et2.grid(row=0, column=1)
        self.lbl_et3.grid(row=0, column=2, sticky="e", padx=4)

    def _montar_destino(self):
        self.destino = ctk.CTkFrame(self.corpo, height=48, corner_radius=10, fg_color=COR_CARTAO)
        self.destino.pack_propagate(False)
        self._img_pasta = ctk.CTkImage(light_image=icone_pasta(18), size=(18, 18))
        ctk.CTkLabel(self.destino, text="", image=self._img_pasta).pack(side="left", padx=(14, 10))
        ctk.CTkLabel(self.destino, text="Salvar em", font=self.f_pequeno,
                     text_color=COR_TEXTO_PASTA).pack(side="left")
        self.lbl_pasta = ctk.CTkLabel(self.destino, text="", font=self.f_negrito,
                                      text_color=COR_TEXTO)
        self.lbl_pasta.pack(side="left", padx=(5, 0))
        for texto, comando in (("Abrir", self._abrir_pasta), ("Trocar", self._trocar_pasta)):
            ctk.CTkButton(
                self.destino, text=texto, width=50, height=28, corner_radius=6, font=self.f_negrito,
                fg_color="transparent", hover_color=COR_COLAR, text_color=COR_ACENTO, command=comando,
            ).pack(side="right", padx=(0, 6))
        self._atualizar_rotulo_pasta()

    # ----- estados da tela -----
    def _mostrar(self, estado):
        self.estado = estado
        for w in (self.rotulo_link, self.campo, self.cartao, self.progresso, self.etapas,
                  self.destino, self.btn, self.dica):
            w.pack_forget()

        ordem = {
            "inicio": [self.rotulo_link, self.campo, self.destino, self.btn],
            "encontrado": [self.rotulo_link, self.campo, self.cartao, self.destino, self.btn],
            "baixando": [self.cartao, self.progresso, self.etapas, self.destino],
            "concluido": [self.cartao, self.progresso, self.etapas, self.destino, self.btn],
        }[estado]
        for w in ordem:
            if w is self.rotulo_link:
                w.pack(fill="x", pady=(0, 8))
            elif w is self.btn:
                w.pack(fill="x")
            else:
                w.pack(fill="x", pady=(0, 14))
        if estado == "inicio":
            self.dica.pack(side="bottom", pady=(0, 16))
        self._atualizar_botao()

    def _atualizar_botao(self):
        if self.estado == "baixando":
            return
        if self.estado == "inicio":
            habilitado = bool(self.entrada.get().strip()) and not self.ocupado
            texto = "Buscando…" if self.ocupado else "Buscar vídeo"
        elif self.estado == "concluido":
            habilitado = True
            texto = "Baixar outro vídeo"
        else:
            habilitado = not self.ocupado
            texto = "Baixar vídeo"
        self.btn.configure(
            text=texto,
            state="normal" if habilitado else "disabled",
            fg_color=COR_ACENTO if habilitado else COR_ACENTO_DESAB,
        )

    def _texto_mudou(self):
        if self.ocupado:
            return
        if self.estado == "encontrado" and self.info and self.entrada.get().strip() != self.info["url"]:
            self.info = None
            self._mostrar("inicio")
        else:
            self._atualizar_botao()

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

    def _trocar_pasta(self):
        escolhida = filedialog.askdirectory(
            title="Escolha a pasta para salvar os videos",
            initialdir=self.pasta if os.path.isdir(self.pasta) else None,
        )
        if escolhida:
            self.pasta = os.path.normpath(escolhida)
            self._atualizar_rotulo_pasta()

    def _abrir_pasta(self):
        abrir_pasta(self.pasta)

    def _atualizar_rotulo_pasta(self):
        nome = os.path.basename(os.path.normpath(self.pasta)) or self.pasta
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
        self.busca_id += 1
        self.entrada.configure(state="disabled")
        self._atualizar_botao()
        threading.Thread(
            target=buscar_info, args=(url, self.busca_id, self.msg_queue), daemon=True
        ).start()

    def _baixar(self):
        self.ocupado = True
        self._fluxos = {}
        self.barra.set(0)
        self.lbl_pct.configure(text="0%")
        self.lbl_vel.configure(text="")
        self.lbl_eta.configure(text="")
        self._pintar_etapa("baixando")
        self._mostrar("baixando")
        threading.Thread(
            target=baixar, args=(self.info["url"], self.pasta, self.msg_queue), daemon=True
        ).start()

    # ----- cartao e progresso -----
    def _preencher_cartao(self, d):
        self.lbl_fonte.configure(text=d["fonte"] or "VÍDEO")
        titulo = limitar_linhas(d["titulo"], self.f_video, 270, 2)
        self.lbl_titulo.configure(text=titulo, wraplength=290, height=19 * (titulo.count("\n") + 1))
        duracao = formatar_duracao(d["duracao"])
        p1 = (f"{duracao} · " if duracao else "") + ("melhor qualidade: " if d["altura"] else "")
        p2 = f"{d['altura']}p" if d["altura"] else ""
        p3 = (" · " if (duracao or d["altura"]) else "") + "MP4"
        self.lbl_fatos1.configure(text=p1)
        self.lbl_fatos2.configure(text=p2)
        self.lbl_fatos3.configure(text=p3)
        self._img_miniatura = ctk.CTkImage(
            light_image=montar_miniatura(None, duracao), size=(150, 84)
        )
        self.lbl_miniatura.configure(image=self._img_miniatura)

    def _pintar_etapa(self, etapa):
        """etapa: baixando | convertendo | pronto"""
        self.lbl_et1.configure(text="✓ Informações", text_color=COR_OK)
        if etapa == "baixando":
            self.lbl_et2.configure(text="● Baixando", text_color=COR_TEXTO)
            self.lbl_et3.configure(text="○ Convertendo para MP4", text_color=COR_TEXTO_FRACO)
        elif etapa == "convertendo":
            self.lbl_et2.configure(text="✓ Baixando", text_color=COR_OK)
            self.lbl_et3.configure(text="● Convertendo para MP4", text_color=COR_TEXTO)
        else:
            self.lbl_et2.configure(text="✓ Baixando", text_color=COR_OK)
            self.lbl_et3.configure(text="✓ Convertendo para MP4", text_color=COR_OK)

    def _atualizar_bytes(self, d):
        """Soma video + audio: sao dois arquivos baixados em sequencia."""
        self._fluxos[d["fluxo"]] = (d["baixado"], d["total"])
        baixado = sum(b for b, _ in self._fluxos.values())
        vistos = sum(t for _, t in self._fluxos.values())
        total = max((self.info or {}).get("tamanho") or 0, vistos)
        fracao = min(baixado / total, 1.0) if total else 0.0
        self.barra.set(fracao)
        self.lbl_pct.configure(text=f"{int(fracao * 100)}%")
        self.lbl_vel.configure(text=formatar_velocidade(d["velocidade"]))
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
        self.entrada.configure(state="normal")
        self._preencher_cartao(dados)
        self._mostrar("encontrado")

    def _ao_receber_miniatura(self, busca_id, imagem):
        if busca_id != self.busca_id or self.info is None:
            return
        self._img_miniatura = ctk.CTkImage(light_image=imagem, size=(150, 84))
        self.lbl_miniatura.configure(image=self._img_miniatura)

    def _ao_converter(self):
        if self.estado != "baixando":
            return
        self.lbl_prog_titulo.configure(text="Convertendo para MP4…")
        self.barra.set(1.0)
        self.lbl_pct.configure(text="100%")
        self.lbl_vel.configure(text="")
        self.lbl_eta.configure(text="")
        self._pintar_etapa("convertendo")

    def _fim_ok(self, caminho):
        self.ocupado = False
        self.barra.set(1.0)
        self.lbl_pct.configure(text="100%")
        self._pintar_etapa("pronto")
        self.lbl_prog_titulo.configure(text="Concluído")
        self.lbl_vel.configure(text="")
        self.lbl_eta.configure(text="")
        self._mostrar("concluido")

    def _novo_download(self):
        self.info = None
        self.lbl_prog_titulo.configure(text="Baixando…")
        self.entrada.delete(0, "end")
        self._mostrar("inicio")

    def _fim_erro(self, mensagem):
        self.ocupado = False
        self.lbl_prog_titulo.configure(text="Baixando…")
        curta = mensagem.strip().splitlines()[-1] if mensagem.strip() else mensagem
        messagebox.showerror(
            APP_TITLE,
            "Nao consegui baixar esse video.\n\n"
            f"Detalhe: {curta}\n\n"
            "Verifique se o link esta correto e se ha conexao com a internet.",
        )
        self._mostrar("encontrado")

    def _fim_erro_busca(self, busca_id, mensagem):
        if busca_id != self.busca_id:
            return
        self.ocupado = False
        self.entrada.configure(state="normal")
        curta = mensagem.strip().splitlines()[-1] if mensagem.strip() else mensagem
        messagebox.showerror(
            APP_TITLE,
            "Nao consegui encontrar esse video.\n\n"
            f"Detalhe: {curta}\n\n"
            "Verifique se o link esta correto e se ha conexao com a internet.",
        )
        self._mostrar("inicio")

    def _centralizar(self):
        self.update_idletasks()
        escala = self._get_window_scaling()
        w, h = int(LARGURA * escala), int(ALTURA * escala)
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"{LARGURA}x{ALTURA}+{x}+{y}")


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    App().mainloop()
