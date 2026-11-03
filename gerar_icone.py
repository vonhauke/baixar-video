#!/usr/bin/env python3
"""
Gera o icone do aplicativo (seta de download creme descendo numa bandeja,
sobre squircle laranja terracota - paleta do design system "Argila"):
  - icone.ico   -> Windows (16 a 256 px)
  - icone.icns  -> Mac (16 a 1024 px, com a margem e a sombra da grade do macOS)
  - icone.png   -> 1024 px, para usos gerais
  - ui/icone.png -> 256 px, logo no cabecalho do app

Uso:
    python gerar_icone.py      (precisa do pillow: pip install pillow)
"""

from PIL import Image, ImageDraw, ImageFilter

TOPO = (224, 133, 101)   # laranja terracota claro
BASE = (193, 92, 58)     # laranja terracota profundo
CREME = (250, 249, 245, 255)
S = 4                    # supersampling para bordas suaves


def _linha_redonda(d, pts, largura, cor):
    """Polilinha com pontas e juncoes redondas."""
    d.line(pts, fill=cor, width=int(largura), joint="curve")
    r = largura / 2
    for x, y in pts:
        d.ellipse([x - r, y - r, x + r, y + r], fill=cor)


def desenhar(tam):
    """Icone quadrado ocupando a area toda (padrao do Windows)."""
    n = tam * S
    k = n / 1024  # escala a partir do desenho em 1024
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))

    grad = Image.new("RGBA", (n, n))
    g = ImageDraw.Draw(grad)
    for y in range(n):
        t = y / (n - 1)
        cor = tuple(int(TOPO[i] + (BASE[i] - TOPO[i]) * t) for i in range(3)) + (255,)
        g.line([(0, y), (n, y)], fill=cor)
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, n - 1, n - 1], radius=int(230 * k), fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    traco = 84 * k
    _linha_redonda(d, [(512 * k, 214 * k), (512 * k, 590 * k)], traco, CREME)                           # haste
    _linha_redonda(d, [(352 * k, 440 * k), (512 * k, 600 * k), (672 * k, 440 * k)], traco, CREME)       # ponta
    _linha_redonda(d, [(262 * k, 640 * k), (262 * k, 790 * k), (762 * k, 790 * k), (762 * k, 640 * k)],
                   traco, CREME)                                                                       # bandeja
    return img.resize((tam, tam), Image.LANCZOS)


def desenhar_mac(tam):
    """Mesma arte dentro da grade do macOS: corpo de 824/1024 centrado, com sombra."""
    corpo = desenhar(round(tam * 824 / 1024))
    tela = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    off = (tam - corpo.width) // 2
    sombra = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    alfa = corpo.split()[3].point(lambda a: int(a * 0.35))
    sombra.paste((0, 0, 0, 255), (off, off + max(1, tam // 100)), alfa)
    sombra = sombra.filter(ImageFilter.GaussianBlur(max(1, tam // 85)))
    tela.alpha_composite(sombra)
    tela.alpha_composite(corpo, (off, off))
    return tela


if __name__ == "__main__":
    win = [desenhar(t) for t in (16, 24, 32, 48, 64, 128, 256)]
    win[-1].save("icone.ico", sizes=[(i.width, i.height) for i in win], append_images=win[:-1])

    mac = {t: desenhar_mac(t) for t in (16, 32, 64, 128, 256, 512, 1024)}
    mac[1024].save("icone.icns", append_images=[mac[t] for t in (16, 32, 64, 128, 256, 512)])

    desenhar(1024).save("icone.png")
    desenhar(256).save("ui/icone.png")
    print("icone.ico, icone.icns, icone.png e ui/icone.png gerados")
