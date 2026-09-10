#!/usr/bin/env python3
"""
app_baixar_video.pyw

Aplicativo de janela para baixar videos do YouTube (e outros sites suportados
pelo yt-dlp). Basta colar o link e clicar em "Baixar video". O video e salvo
em MP4 na pasta escolhida.

Empacotado como .exe com PyInstaller (ver build_exe.py). O ffmpeg vai junto
dentro do executavel, entao nao precisa de nada instalado na maquina.
"""

import os
import sys
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import yt_dlp

APP_TITLE = "Baixar Video"
DEFAULT_DIR = r"C:\Users\Pedro\Videos"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def resource_path(rel):
    """Caminho de um recurso, funcionando tanto rodando o .py quanto o .exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def ffmpeg_dir():
    """Pasta com o ffmpeg embarcado no .exe. Se nao houver, retorna None e o
    yt-dlp tenta achar o ffmpeg no PATH do sistema."""
    cand = resource_path("ffmpeg")
    if os.path.isfile(os.path.join(cand, "ffmpeg.exe")):
        return cand
    return None


def abrir_pasta(caminho):
    try:
        os.makedirs(caminho, exist_ok=True)
        os.startfile(caminho)  # type: ignore[attr-defined]  (Windows)
    except Exception as e:
        messagebox.showwarning(APP_TITLE, f"Nao foi possivel abrir a pasta:\n{e}")


# ---------------------------------------------------------------------------
# Download (roda numa thread separada para nao travar a janela)
# ---------------------------------------------------------------------------
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
        elif status == "finished":
            msg_queue.put(("progresso", 100))
            msg_queue.put(("status", "Convertendo para MP4..."))

    opcoes = {
        # melhor video+audio em MP4; cai para o melhor arquivo unico se preciso
        "format": "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(
            pasta_saida, "%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s"
        ),
        "progress_hooks": [hook],
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
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.resizable(False, False)
        self.configure(padx=18, pady=16)

        try:
            self.iconbitmap(resource_path("icone.ico"))
        except Exception:
            pass

        self.pasta = tk.StringVar(value=DEFAULT_DIR)
        self.url = tk.StringVar()
        self.msg_queue = queue.Queue()
        self.baixando = False

        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        # ----- Link -----
        ttk.Label(self, text="Cole o link do video:").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        self.entrada = ttk.Entry(self, textvariable=self.url, width=52)
        self.entrada.grid(row=1, column=0, columnspan=2, sticky="we", pady=(2, 0))
        ttk.Button(self, text="Colar", width=8, command=self._colar).grid(
            row=1, column=2, sticky="e", padx=(8, 0), pady=(2, 0)
        )

        # ----- Pasta de destino -----
        ttk.Label(self, text="Salvar em:").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(12, 0)
        )
        self.lbl_pasta = ttk.Entry(self, textvariable=self.pasta, state="readonly")
        self.lbl_pasta.grid(row=3, column=0, sticky="we", pady=(2, 0))
        ttk.Button(self, text="Trocar...", width=9, command=self._trocar_pasta).grid(
            row=3, column=1, sticky="e", padx=(8, 0), pady=(2, 0)
        )
        ttk.Button(self, text="Abrir pasta", width=11, command=self._abrir_pasta).grid(
            row=3, column=2, sticky="e", padx=(8, 0), pady=(2, 0)
        )

        # ----- Botao principal -----
        self.btn = ttk.Button(self, text="Baixar video", command=self._iniciar)
        self.btn.grid(row=4, column=0, columnspan=3, sticky="we", pady=(16, 4), ipady=6)

        # ----- Progresso -----
        self.barra = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.barra.grid(row=5, column=0, columnspan=3, sticky="we", pady=(6, 2))
        self.status = ttk.Label(self, text="Pronto.", foreground="#555")
        self.status.grid(row=6, column=0, columnspan=3, sticky="w")

        self.columnconfigure(0, weight=1)
        self.entrada.focus_set()
        self._centralizar()
        self.after(100, self._ler_fila)

    # ----- acoes de botao -----
    def _colar(self):
        try:
            texto = self.clipboard_get().strip()
            if texto:
                self.url.set(texto)
        except tk.TclError:
            pass

    def _trocar_pasta(self):
        escolhida = filedialog.askdirectory(
            title="Escolha a pasta para salvar os videos",
            initialdir=self.pasta.get() if os.path.isdir(self.pasta.get()) else None,
        )
        if escolhida:
            self.pasta.set(os.path.normpath(escolhida))

    def _abrir_pasta(self):
        abrir_pasta(self.pasta.get())

    def _iniciar(self):
        if self.baixando:
            return
        url = self.url.get().strip()
        if not url:
            messagebox.showinfo(APP_TITLE, "Cole o link do video primeiro.")
            return

        self.baixando = True
        self.btn.config(state="disabled", text="Baixando...")
        self.barra.config(value=0)
        self.status.config(text="Iniciando...", foreground="#555")

        threading.Thread(
            target=baixar, args=(url, self.pasta.get(), self.msg_queue), daemon=True
        ).start()

    # ----- ponte thread -> janela -----
    def _ler_fila(self):
        try:
            while True:
                tipo, dado = self.msg_queue.get_nowait()
                if tipo == "progresso":
                    self.barra.config(value=dado)
                elif tipo == "status":
                    self.status.config(text=dado, foreground="#555")
                elif tipo == "concluido":
                    self._fim_ok(dado)
                elif tipo == "erro":
                    self._fim_erro(dado)
        except queue.Empty:
            pass
        self.after(100, self._ler_fila)

    def _fim_ok(self, caminho):
        self.baixando = False
        self.btn.config(state="normal", text="Baixar video")
        self.barra.config(value=100)
        nome = os.path.basename(caminho)
        self.status.config(text=f"Concluido: {nome}", foreground="#1a7f37")
        if messagebox.askyesno(
            APP_TITLE, f"Download concluido!\n\n{nome}\n\nAbrir a pasta agora?"
        ):
            abrir_pasta(os.path.dirname(caminho) or self.pasta.get())
        self.url.set("")

    def _fim_erro(self, mensagem):
        self.baixando = False
        self.btn.config(state="normal", text="Baixar video")
        self.barra.config(value=0)
        self.status.config(text="Falhou.", foreground="#b3261e")
        curta = mensagem.strip().splitlines()[-1] if mensagem.strip() else mensagem
        messagebox.showerror(
            APP_TITLE,
            "Nao consegui baixar esse video.\n\n"
            f"Detalhe: {curta}\n\n"
            "Verifique se o link esta correto e se ha conexao com a internet.",
        )

    def _centralizar(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"+{x}+{y}")


if __name__ == "__main__":
    App().mainloop()
