#!/usr/bin/env python3
"""
app_baixar_video.pyw

SnapYou: aplicativo de janela para baixar videos do YouTube (e outros sites
suportados pelo yt-dlp). Cole o link, busque o video para ver a miniatura, o
titulo, a duracao e a melhor qualidade, e depois baixe. Pode escolher entre
baixar o video (MP4) ou so o audio (MP3), sempre na melhor qualidade disponivel.

Interface: HTML/CSS em ui/ (design system "Argila", em ui/ds/), mostrada numa
janela nativa pelo pywebview (Edge WebView2 no Windows, WebKit no Mac). Este
arquivo cuida do resto: busca e download com o yt-dlp, conversao com o ffmpeg
e a ponte com a interface (classe Api, chamada pelo JavaScript).

Empacotado como .exe/.app com PyInstaller (build_exe.py / mac/build_mac.py).
O ffmpeg vai junto, entao nao precisa de nada instalado na maquina.
"""

import base64
import os
import queue
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.request

import yt_dlp

import argila

APP_TITLE = "SnapYou"
if sys.platform == "win32":
    DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Videos")
elif sys.platform == "darwin":
    DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Movies")
else:
    DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Videos")
DEFAULT_DIR_AUDIO = os.path.join(os.path.expanduser("~"), "Music")

# nomes em portugues das pastas padrao do sistema (como o Explorer/Finder mostram)
NOMES_PASTAS = {"Videos": "Vídeos", "Movies": "Filmes", "Music": "Música",
                "Downloads": "Downloads", "Desktop": "Mesa", "Documents": "Documentos"}

LARGURA, ALTURA = 640, 660          # tamanho inicial da janela (redimensionavel)
ALTURA_MIN, LARGURA_MIN = 560, 500



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
resource_path = argila.recurso


def ffmpeg_dir():
    """Pasta com o ffmpeg embarcado no executavel. Se nao houver, retorna None
    e o yt-dlp tenta achar o ffmpeg no PATH do sistema."""
    cand = resource_path("ffmpeg")
    nome = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    if os.path.isfile(os.path.join(cand, nome)):
        return cand
    return None


def abrir_no_sistema(caminho):
    """Abre um arquivo ou pasta (criando a pasta se ainda nao existir)."""
    if os.path.isdir(caminho) or not os.path.splitext(caminho)[1]:
        os.makedirs(caminho, exist_ok=True)
    argila.abrir_no_sistema(caminho)


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


def baixar_miniatura(url):
    """Baixa a miniatura do video e devolve como data URI (para o <img> da
    interface), ou None se falhar."""
    if not url or not url.lower().startswith(("http://", "https://")):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            dados = resp.read(5_000_000)
            tipo = (resp.headers.get_content_type() or "").lower()
        if not tipo.startswith("image/"):
            tipo = "image/webp" if dados[8:12] == b"WEBP" else "image/png" if dados[:4] == b"\x89PNG" else "image/jpeg"
        return f"data:{tipo};base64,{base64.b64encode(dados).decode('ascii')}"
    except Exception:
        return None



# ---------------------------------------------------------------------------
# Busca de informacoes e download (rodam em threads; o andamento vai por uma fila)
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

    msg_queue.put(("miniatura", (busca_id, baixar_miniatura(info.get("thumbnail")))))


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
    # No modo audio o arquivo baixado e so um intermediario: o ffmpeg extrai o
    # MP3 e o yt-dlp apaga o original. Se ele fosse baixado direto na pasta de
    # destino, um video ja existente com o mesmo nome (ex.: "Titulo.mp4" baixado
    # antes no modo Video) seria tomado como "ja baixado" e apagado no fim.
    # Por isso o audio e montado numa pasta temporaria propria e so o MP3
    # final e movido para a pasta escolhida.
    pasta_trabalho = tempfile.mkdtemp(prefix="snapyou-") if modo == "audio" else pasta_saida
    opcoes.update({
        "outtmpl": os.path.join(pasta_trabalho, "%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s"),
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
        if not os.path.exists(final):
            final = nome
        if modo == "audio":
            final = mover_para_pasta(final, pasta_saida)
        msg_queue.put(("concluido", final))
    except Exception as e:
        if cancelar.is_set() or isinstance(e, yt_dlp.utils.DownloadCancelled):
            limpar_parciais()
            msg_queue.put(("cancelado", None))
        else:
            msg_queue.put(("erro", str(e)))
    finally:
        if pasta_trabalho != pasta_saida:
            shutil.rmtree(pasta_trabalho, ignore_errors=True)


def mover_para_pasta(arquivo, pasta):
    """Move `arquivo` para `pasta`, substituindo um arquivo de mesmo nome
    (o mesmo comportamento de baixar de novo direto na pasta). Devolve o novo caminho."""
    destino = os.path.join(pasta, os.path.basename(arquivo))
    if os.path.isfile(destino):
        os.remove(destino)
    shutil.move(arquivo, destino)
    return destino


def nome_da_pasta(caminho):
    """Nome curto da pasta para mostrar na interface (Videos -> Vídeos)."""
    nome = os.path.basename(os.path.normpath(caminho)) or caminho
    return NOMES_PASTAS.get(nome, nome)


# ---------------------------------------------------------------------------
# Ponte com a interface (o JavaScript chama os metodos de Api)
# ---------------------------------------------------------------------------
class Api:
    """Metodos chamados pela interface (window.pywebview.api.<metodo>).
    Atributos com _ ficam escondidos do JavaScript."""

    def __init__(self):
        self._janela = None
        self._emissor = argila.Emissor("SnapYou")
        self._fila = queue.Queue()
        self._cancelar = threading.Event()
        self._pastas = {"video": DEFAULT_DIR, "audio": DEFAULT_DIR_AUDIO}
        threading.Thread(target=self._repassar_eventos, daemon=True).start()

    # ----- eventos do motor -> interface -----
    def _emitir(self, evento):
        self._emissor.janela = self._janela
        self._emissor(evento)

    def _repassar_eventos(self):
        """Le a fila do motor (buscar_info/baixar) e repassa para a interface.
        O andamento ("bytes") e limitado a ~8 atualizacoes por segundo."""
        ultimo_bytes = 0.0
        pendente = None
        while True:
            try:
                tipo, dado = self._fila.get(timeout=0.15)
            except queue.Empty:
                if pendente:
                    self._emitir(pendente)
                    pendente = None
                continue
            if tipo in ("progresso", "status"):
                continue   # a interface calcula tudo a partir de "bytes"
            if tipo == "bytes":
                pendente = dict(dado, tipo="bytes")
                if time.monotonic() - ultimo_bytes >= 0.12:
                    self._emitir(pendente)
                    pendente = None
                    ultimo_bytes = time.monotonic()
                continue
            if pendente:
                self._emitir(pendente)
                pendente = None
            if tipo == "info":
                self._emitir(dict(dado, tipo="info", fonte=nome_da_fonte(dado["fonte"])))
            elif tipo == "miniatura":
                busca_id, imagem = dado
                self._emitir({"tipo": "miniatura", "id": busca_id, "imagem": imagem})
            elif tipo == "erro_busca":
                busca_id, mensagem = dado
                titulo, texto, detalhe = explicar_erro(mensagem, "busca")
                self._emitir({"tipo": "erro_busca", "id": busca_id, "titulo": titulo,
                              "texto": texto, "detalhe": detalhe})
            elif tipo == "convertendo":
                self._emitir({"tipo": "convertendo"})
            elif tipo == "concluido":
                self._emitir({"tipo": "concluido", "caminho": dado, "nome": os.path.basename(dado),
                              "pasta": nome_da_pasta(os.path.dirname(dado))})
            elif tipo == "cancelado":
                self._emitir({"tipo": "cancelado"})
            elif tipo == "erro":
                titulo, texto, detalhe = explicar_erro(dado, "download")
                self._emitir({"tipo": "erro", "titulo": titulo, "texto": texto, "detalhe": detalhe})

    def _pasta_info(self, modo):
        caminho = self._pastas[modo]
        return {"nome": nome_da_pasta(caminho), "caminho": caminho}

    # ----- chamados pelo JavaScript -----
    def estado_inicial(self):
        return {"pastas": {m: self._pasta_info(m) for m in ("video", "audio")},
                "mac": sys.platform == "darwin"}

    def colar(self):
        return argila.ler_area_de_transferencia().strip()

    def buscar(self, url, modo, busca_id):
        threading.Thread(target=buscar_info, args=(url, busca_id, self._fila, modo), daemon=True).start()

    def baixar(self, url, modo):
        self._cancelar = threading.Event()
        threading.Thread(target=baixar, args=(url, self._pastas[modo], self._fila, modo, self._cancelar),
                         daemon=True).start()

    def cancelar(self):
        self._cancelar.set()

    def trocar_pasta(self, modo):
        atual = self._pastas[modo]
        escolha = self._janela.create_file_dialog(
            argila.TIPO_PASTA, directory=atual if os.path.isdir(atual) else "")
        if not escolha:
            return None
        pasta = escolha[0] if isinstance(escolha, (list, tuple)) else escolha
        self._pastas[modo] = os.path.normpath(pasta)
        return self._pasta_info(modo)

    def abrir_pasta(self, modo):
        try:
            abrir_no_sistema(self._pastas[modo])
        except Exception as e:
            return str(e).strip()[:200] or "Erro desconhecido"

    def abrir_arquivo(self, caminho):
        try:
            abrir_no_sistema(caminho)
        except Exception as e:
            return str(e).strip()[:200] or "Erro desconhecido"

    def mostrar_na_pasta(self, caminho):
        try:
            argila.mostrar_na_pasta(caminho)
        except Exception as e:
            return str(e).strip()[:200] or "Erro desconhecido"


def main():
    api = Api()
    janela = argila.criar_janela(APP_TITLE, api, LARGURA, ALTURA, LARGURA_MIN, ALTURA_MIN)
    api._janela = janela
    argila.iniciar(icone="icone.png", debug_env="SNAPYOU_DEBUG", titulo=APP_TITLE)


if __name__ == "__main__":
    main()
