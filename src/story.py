"""Arte vertical de story (1080x1920) a partir da arte do feed (1080x1350)."""
from PIL import Image, ImageDraw, ImageOps

from . import config
from .imagem import BRANCO, DOURADO, DOURADO_CLARO, ESCURO, FUNDO, _fonte

L, A = 1080, 1920


def _arredondar(img, raio):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, img.width - 1, img.height - 1], raio, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), m)
    return out


def gerar(arte_feed, destino, t1="ACHADO NOVO ", t2="NO FEED"):
    img = Image.new("RGB", (L, A), ESCURO)
    d = ImageDraw.Draw(img)
    f1 = _fonte(56, "Black")
    x = (L - d.textlength(t1 + t2, font=f1)) / 2
    d.text((x, 110), t1, font=f1, fill=BRANCO)
    d.text((x + d.textlength(t1, font=f1), 110), t2, font=f1, fill=DOURADO_CLARO)
    arte = Image.open(arte_feed).convert("RGB")
    arte = ImageOps.contain(arte, (940, 1175), Image.LANCZOS)
    arte = _arredondar(arte, 36)
    x0, y0 = (L - arte.width) // 2, 230
    d.rounded_rectangle([x0 - 8, y0 - 8, x0 + arte.width + 8, y0 + arte.height + 8], 42, fill=DOURADO)
    img.paste(arte, (x0, y0), arte)
    y = y0 + arte.height + 60
    d.rounded_rectangle([90, y, L - 90, y + 270], 48, fill=FUNDO)
    linhas = [("VAI NO ÚLTIMO POST E", _fonte(34, "SemiBold"), ESCURO, 34),
              ("COMENTA QUERO", _fonte(64, "Black"), DOURADO, 82),
              ("que o link chega no seu direct!", _fonte(34, "SemiBold"), ESCURO, 0)]
    yy = y + 36
    for t, f, cor, passo in linhas:
        d.text(((L - d.textlength(t, font=f)) / 2, yy), t, font=f, fill=cor)
        yy += passo + 18
    f4 = _fonte(34, "SemiBold")
    d.text(((L - d.textlength(config.ARROBA, font=f4)) / 2, A - 110), config.ARROBA, font=f4, fill=DOURADO_CLARO)
    img.save(destino, "JPEG", quality=90)
    return destino


def _quebrar(draw, texto, fonte, largura, max_linhas=2):
    linhas, atual = [], ""
    for p in texto.split():
        teste = f"{atual} {p}".strip()
        if draw.textlength(teste, font=fonte) <= largura:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas[:max_linhas]


def gerar_story_produto(oferta, foto, destino, pos=1):
    """Gera um story vertical (1080x1920) focado exclusivamente no produto."""
    im = Image.new("RGB", (L, A), (250, 247, 242))
    d = ImageDraw.Draw(im)

    # Borda sutil elegante
    d.rounded_rectangle((35, 35, L - 35, A - 35), radius=36, outline=(220, 195, 155), width=2)

    # Logo no topo
    if config.LOGO.exists():
        try:
            logo = Image.open(config.LOGO).convert("RGBA")
            logo = logo.resize((220, 220), Image.Resampling.LANCZOS)
            im.paste(logo, ((L - 220) // 2, 60), logo)
        except Exception:
            pass

    # Selo / Badge do Produto
    plataforma = (oferta.get("plataforma") or "shopee").upper()
    badge = f"ACHADINHO #{pos} • {plataforma}"
    f_badge = _fonte(28, "Bold")
    bw = d.textlength(badge, font=f_badge) + 44
    bx0 = (L - bw) // 2
    d.rounded_rectangle((bx0, 310, bx0 + bw, 362), radius=22, fill=(197, 168, 128))
    d.text(((L - d.textlength(badge, font=f_badge)) // 2, 324), badge, font=f_badge, fill=(255, 255, 255))

    # Card da foto do produto
    card_x0, card_y0 = 80, 395
    card_w, card_h = L - 160, 840
    d.rounded_rectangle((card_x0, card_y0, card_x0 + card_w, card_y0 + card_h), radius=32, fill=(255, 255, 255), outline=(230, 218, 202), width=2)

    if foto:
        foto_fit = ImageOps.contain(foto.convert("RGB"), (card_w - 30, card_h - 30), Image.Resampling.LANCZOS)
        foto_fit = _arredondar(foto_fit, 24)
        fx = card_x0 + (card_w - foto_fit.width) // 2
        fy = card_y0 + (card_h - foto_fit.height) // 2
        im.paste(foto_fit, (fx, fy), foto_fit)

    # Titulo do produto
    titulo = oferta.get("titulo") or oferta.get("nome", "Achadinho Especial")
    f_tit = _fonte(38, "Bold")
    linhas = _quebrar(d, titulo, f_tit, L - 180, 2)
    y_tit = card_y0 + card_h + 35
    for ln in linhas:
        d.text(((L - d.textlength(ln, font=f_tit)) // 2, y_tit), ln, font=f_tit, fill=(44, 34, 30))
        y_tit += 48

    # Preco
    preco_val = oferta.get("preco_fmt")
    preco = f"R$ {preco_val}" if preco_val else ""
    y_preco = y_tit + 15
    if preco:
        f_preco = _fonte(64, "ExtraBold")
        d.text(((L - d.textlength(preco, font=f_preco)) // 2, y_preco), preco, font=f_preco, fill=(180, 130, 60))

    # Balao de Acao
    y_cta = y_preco + 95
    d.rounded_rectangle((80, y_cta, L - 80, y_cta + 195), radius=28, fill=(44, 34, 30))

    f_cta1 = _fonte(30, "Medium")
    t1 = "Quer o link com desconto?"
    d.text(((L - d.textlength(t1, font=f_cta1)) // 2, y_cta + 30), t1, font=f_cta1, fill=(220, 200, 175))

    f_cta2 = _fonte(46, "ExtraBold")
    t2 = "Responda  QUERO"
    d.text(((L - d.textlength(t2, font=f_cta2)) // 2, y_cta + 75), t2, font=f_cta2, fill=(255, 255, 255))

    f_cta3 = _fonte(28, "Medium")
    t3 = "Enviamos o link na hora no seu direct!"
    d.text(((L - d.textlength(t3, font=f_cta3)) // 2, y_cta + 140), t3, font=f_cta3, fill=(200, 190, 185))

    # Rodapé
    f_arr = _fonte(28, "SemiBold")
    arroba = config.ARROBA or "@ba.homeliving"
    d.text(((L - d.textlength(arroba, font=f_arr)) // 2, A - 85), arroba, font=f_arr, fill=(160, 145, 135))

    im.save(destino, "JPEG", quality=92, optimize=True)
    return destino
