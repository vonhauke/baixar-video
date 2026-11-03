"""Teste de ponta a ponta do SnapYou, usado pela automacao do GitHub (Windows e
Mac) e para testar localmente.

Abre a janela real (pywebview) e usa o app como uma pessoa: cola o link, busca,
baixa o video, baixa o audio, cancela um download no meio e provoca um erro,
conferindo a tela e os arquivos no disco. O "site" e um servidor local com um
video gerado pelo ffmpeg, entao o teste nao depende do YouTube.

uso: python .github/teste_e2e.py        (precisa do ffmpeg no PATH ou em FFMPEG_DIR)
Sai com codigo 1 se algo falhar.
"""

import functools
import http.server
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # o console do Windows usa cp1252
sys.path.insert(0, RAIZ)
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"
# o yt-dlp procura o ffmpeg no PATH (no .exe/.app ele vai embutido)
if os.environ.get("FFMPEG_DIR"):
    os.environ["PATH"] = os.environ["FFMPEG_DIR"] + os.pathsep + os.environ["PATH"]

loader = importlib.machinery.SourceFileLoader("app", os.path.join(RAIZ, "app_baixar_video.pyw"))
spec = importlib.util.spec_from_loader("app", loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)
import argila  # noqa: E402
import webview  # noqa: E402

TMP = tempfile.mkdtemp(prefix="snapyou-teste-")
SITE = os.path.join(TMP, "site")
os.makedirs(SITE)
CAPTURAS = os.environ.get("SNAPYOU_CAPTURAS")
falhas = []


def ffmpeg():
    pasta = os.environ.get("FFMPEG_DIR")
    if pasta:
        return os.path.join(pasta, "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    return shutil.which("ffmpeg") or "ffmpeg"


def gerar_video():
    destino = os.path.join(SITE, "via-lactea.mp4")
    subprocess.run([ffmpeg(), "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                    "-t", "30", "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "3M",
                    "-c:a", "aac", "-shortest", destino], check=True)
    return os.path.getsize(destino)


class Servidor(http.server.SimpleHTTPRequestHandler):
    """Serve a pasta SITE; ?lento limita a 300 KB/s (para dar tempo de cancelar)."""

    def copyfile(self, origem, destino):
        taxa = 300_000 if "lento" in self.path else 4_000_000
        while True:
            bloco = origem.read(64 * 1024)
            if not bloco:
                break
            try:
                destino.write(bloco)
            except OSError:
                break
            time.sleep(len(bloco) / taxa)

    def translate_path(self, path):
        return super().translate_path(path.split("?")[0])

    def log_message(self, *args):
        pass


def iniciar_servidor():
    servidor = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Servidor, directory=SITE))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{servidor.server_address[1]}"


def verificar(cond, mensagem):
    print(("ok   " if cond else "FALHA ") + mensagem, flush=True)
    if not cond:
        falhas.append(mensagem)


def roteiro(janela, api, base):
    js = janela.evaluate_js

    def estado():
        return js("JSON.stringify({e: SnapYou._s.estado, o: SnapYou._s.ocupado, "
                  "aviso: !document.getElementById('aviso').classList.contains('oculto'), "
                  "titulo: document.getElementById('aviso-titulo').textContent})")

    def esperar(condicao, limite=90, nome=""):
        fim = time.time() + limite
        while time.time() < fim:
            try:
                if js(condicao):
                    return True
            except Exception:
                pass
            time.sleep(0.25)
        verificar(False, f"tempo esgotado esperando: {nome or condicao} (estado {estado()})")
        return False

    def capturar(nome):
        if CAPTURAS and sys.platform.startswith("linux"):
            time.sleep(0.5)
            subprocess.run(["import", "-window", "root", os.path.join(CAPTURAS, nome + ".png")])

    def colar_link(url):
        js(f"(() => {{ const c = document.getElementById('link'); c.value = {json.dumps(url)};"
           "c.dispatchEvent(new Event('input')); })()")

    def clicar(id_):
        js(f"document.getElementById({json.dumps(id_)}).click()")

    try:
        esperar("document.documentElement.classList.contains('pronto')", 90, "interface pronta")
        capturar("01-inicio")

        # 1) video
        colar_link(base + "/via-lactea.mp4")
        clicar("btn-buscar")
        verificar(esperar("SnapYou._s.estado === 'encontrado'", 60, "video encontrado"), "busca encontrou o video")
        capturar("02-encontrado")
        clicar("btn-baixar")
        esperar("SnapYou._s.estado === 'baixando' && parseInt(document.getElementById('prog-pct').textContent) > 0",
                30, "progresso andando")
        capturar("03-baixando")
        verificar(esperar("SnapYou._s.estado === 'concluido'", 120, "download concluido"), "download do video concluido")
        capturar("04-concluido")
        mp4s = [f for f in os.listdir(api._pastas["video"]) if f.endswith(".mp4")]
        verificar(len(mp4s) == 1, f"MP4 salvo na pasta de video ({mp4s})")

        # 2) audio (mesmo link, outra pasta)
        clicar("btn-outro")
        clicar("modo-audio")
        colar_link(base + "/via-lactea.mp4")
        clicar("btn-buscar")
        esperar("SnapYou._s.estado === 'encontrado'", 60, "audio encontrado")
        verificar(js("document.getElementById('btn-baixar-texto').textContent") == "Baixar áudio",
                  "botao mostra 'Baixar áudio'")
        clicar("btn-baixar")
        verificar(esperar("SnapYou._s.estado === 'concluido'", 120, "audio concluido"), "download do audio concluido")
        mp3s = [f for f in os.listdir(api._pastas["audio"]) if f.endswith(".mp3")]
        verificar(len(mp3s) == 1, f"MP3 salvo na pasta de audio ({mp3s})")

        # 3) cancelar no meio
        api._pastas["video"] = os.path.join(TMP, "cancelar")
        clicar("btn-outro")
        clicar("modo-video")
        colar_link(base + "/via-lactea.mp4?lento")
        clicar("btn-buscar")
        esperar("SnapYou._s.estado === 'encontrado'", 60, "encontrado para cancelar")
        clicar("btn-baixar")
        esperar("parseInt(document.getElementById('prog-pct').textContent) >= 3", 60, "progresso antes de cancelar")
        clicar("btn-cancelar")
        verificar(esperar("SnapYou._s.estado === 'encontrado' && !SnapYou._s.ocupado", 60, "cancelado"),
                  "cancelar volta para o cartao do video")
        verificar("cancelado" in (js("document.getElementById('aviso-titulo').textContent") or ""),
                  "aviso 'Download cancelado' aparece")
        capturar("05-cancelado")
        pasta_c = api._pastas["video"]
        sobras = os.listdir(pasta_c) if os.path.isdir(pasta_c) else []
        verificar(not sobras, f"cancelar apaga os arquivos incompletos ({sobras})")

        # 4) erro de busca
        colar_link(base + "/nao-existe.mp4")
        clicar("btn-buscar")
        verificar(esperar("SnapYou._s.estado === 'inicio' && !SnapYou._s.ocupado && "
                          "!document.getElementById('aviso').classList.contains('oculto')", 60, "erro de busca"),
                  "erro de busca aparece dentro da janela")
        capturar("06-erro")

        erros_js = js("JSON.stringify(window.__erros)")
        verificar(erros_js in ("[]", None), f"sem erros de JavaScript ({erros_js})")
    except Exception:
        traceback.print_exc()
        falhas.append("excecao no roteiro")
    finally:
        janela.destroy()


def main():
    tamanho = gerar_video()
    print(f"video de teste: {tamanho / 1e6:.1f} MB", flush=True)
    base = iniciar_servidor()

    api = app.Api()
    api._pastas = {"video": os.path.join(TMP, "Videos"), "audio": os.path.join(TMP, "Music")}
    janela = webview.create_window("SnapYou (teste)", url=app.resource_path(os.path.join("ui", "index.html")),
                                   js_api=api, width=app.LARGURA, height=app.ALTURA)
    api._janela = janela
    # abre pelo mesmo caminho do app de verdade (argila.iniciar, com o ícone)
    argila.iniciar(roteiro, (janela, api, base), icone="icone.png", titulo="SnapYou")

    shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s):\n- " + "\n- ".join(falhas))
        sys.exit(1)
    print("\nTudo certo: o app funcionou de ponta a ponta.")


if __name__ == "__main__":
    main()
