"""Teste rapido usado pela automacao do GitHub (gerar-exe.yml): abre a janela
do SnapYou, passa por todas as telas com dados de exemplo nos temas claro e
escuro e fecha. Falha (codigo de saida 1) se qualquer tela der erro."""

import importlib.machinery
import importlib.util
import os
import sys
import threading
import traceback

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
loader = importlib.machinery.SourceFileLoader("app", os.path.join(RAIZ, "app_baixar_video.pyw"))
spec = importlib.util.spec_from_loader("app", loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)
import customtkinter as ctk  # noqa: E402

erros = []
DADOS = {"id": 1, "url": "https://www.youtube.com/watch?v=exemplo", "modo": "video",
         "titulo": "Vídeo de exemplo com um título comprido para testar a quebra em duas linhas",
         "duracao": 767, "fonte": "YOUTUBE", "altura": 1080, "abr": None, "tamanho": 486_000_000}


def passo(nome, func):
    try:
        func()
        print(f"ok  {nome}")
    except Exception:
        erros.append(nome)
        print(f"ERRO {nome}")
        traceback.print_exc()


def roteiro(a, tema):
    print(f"--- tema {tema}: fontes {app.escolher_fontes(a)}")
    passo("inicio", lambda: a._mostrar("inicio"))
    passo("colar", lambda: (a.clipboard_clear(), a.clipboard_append(DADOS["url"]), a._colar()))
    passo("buscando", lambda: (setattr(a, "ocupado", True), a._mostrar("inicio")))
    passo("erro de busca", lambda: (setattr(a, "ocupado", False),
                                    a._fim_erro_busca(a.busca_id, "ERROR: Video unavailable")))
    passo("encontrado", lambda: (setattr(a, "busca_id", 1), a._ao_receber_info(DADOS)))
    passo("miniatura", lambda: a._ao_receber_miniatura(1, app.miniaturas(None, "12:47")))
    passo("baixando", lambda: (setattr(a, "ocupado", True), setattr(a, "cancelar_evento", threading.Event()),
                               a._pintar_etapa("baixando"), a._mostrar("baixando"),
                               a._atualizar_bytes({"fluxo": "v", "baixado": 3e8, "total": 4.86e8,
                                                   "velocidade": 6.4e6, "eta": 28})))
    passo("convertendo", a._ao_converter)
    passo("concluido", lambda: a._fim_ok(os.path.join(a.pasta, "2024-03-18 - Exemplo.mp4")))
    passo("baixar outro", a._acao_principal)
    passo("modo audio", lambda: (a.seg_modo.set("Áudio (MP3)"), a._selecionar_modo("Áudio (MP3)")))
    passo("cancelado", lambda: (a._ao_receber_info(dict(DADOS, modo="audio", abr=160)), a._fim_cancelado()))
    passo("fechar aviso", a._fechar_aviso)
    a.after(300, a.destroy)


for tema in ("light", "dark"):
    ctk.set_appearance_mode(tema)
    janela = app.App()
    janela.after(800, lambda j=janela, t=tema: roteiro(j, t))
    janela.mainloop()

if erros:
    print(f"\nFalhou em: {', '.join(erros)}")
    sys.exit(1)
print("\nTodas as telas abriram sem erro.")
