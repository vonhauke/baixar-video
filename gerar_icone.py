#!/usr/bin/env python3
"""
Gera o icone do aplicativo (seta de download branca sobre squircle azul,
no estilo dos icones do macOS / Windows 11):
  - icone.ico   -> Windows (16 a 256 px)
  - icone.icns  -> Mac (16 a 1024 px, com a margem e a sombra da grade do macOS)
  - icone.png   -> 1024 px, para usos gerais (e icone da janela no Mac/Linux)

E a mesma arte de desenhar_marca() no app_baixar_video.pyw.

Uso:
    python gerar_icone.py      (precisa do pillow: pip install pillow)
"""

from PIL import Image, ImageDraw, ImageFilter

TOPO = (64, 156, 255)    # azul claro
BASE = (0, 98, 214)      # azul profundo
BRANCO = (255, 255, 255, 255)
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
    _linha_redonda(d, [(512 * k, 232 * k), (512 * k, 640 * k)], 96 * k, BRANCO)                         # haste
    _linha_redonda(d, [(330 * k, 470 * k), (512 * k, 652 * k), (694 * k, 470 * k)], 96 * k, BRANCO)     # ponta
    d.rounded_rectangle([284 * k, 764 * k, 740 * k, 852 * k], radius=44 * k, fill=(255, 255, 255, 235))  # bandeja
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
    print("icone.ico, icone.icns e icone.png gerados")
