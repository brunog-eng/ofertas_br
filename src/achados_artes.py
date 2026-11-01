"""Artes do carrossel de achados (src/achados.py): várias versões de cada slide, para os posts não ficarem todos
iguais no feed. A cada carrossel o robô usa uma versão diferente (o contador fica em data/<perfil>/achados.json).
"""
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import config, imagem, lojas_arte, marcas

L, A = 1080, 1350
NOMES_LOJA = {"shopee": "SHOPEE", "aliexpress": "ALIEXPRESS", **{p: m["nome"].upper() for p, m in marcas.MARCAS.items()}}

TITULOS = [
    ("ACHADINHOS IMPERDÍVEIS", "arrasta pro lado"),
    (f"ACHADOS {config.NOME_MARCA.upper()[:16]}", "arrasta e confere"),
    ("OLHA O QUE ENCONTRAMOS", "arrasta pro lado"),
]
TITULOS_GARIMPO = TITULOS
TITULOS_ANA = TITULOS
FINAIS = ["Gostou de algum achadinho?", "Qual é o seu favorito?", "Qual você levaria pra casa?"]
FINAIS_GARIMPO = FINAIS
FINAIS_ANA = FINAIS
N_PRODUTO, N_FINAL_GARIMPO, N_FINAL_ANA, N_TITULO = 3, 2, 3, 3


def _brl_linha(o):
    return f"R$ {o['preco_fmt']}"


def _info(o):
    if marcas.eh_marca(o):
        return marcas.texto_oficial(o)
    vendas = f"{o.get('vendas', 0):,}".replace(",", ".")
    if o.get("avaliacao_pct"):
        return f"{o['avaliacao_pct']:.0f}% aprovação  •  {vendas}+ vendidos"
    return f"nota {str(o.get('nota', '')).replace('.', ',')}  •  {vendas}+ vendidos"


def _loja(o):
    return NOMES_LOJA.get(o.get("plataforma") or "shopee", "SHOPEE")


def _loja_nome(o):
    """Nome da loja como se escreve: Shopee, AliExpress, Shark Ninja..."""
    return marcas.nome(o) if marcas.eh_marca(o) else {"ALIEXPRESS": "AliExpress"}.get(_loja(o), _loja(o).title())


def _degrade(topo, base):
    img = Image.new("RGB", (L, A))
    d = ImageDraw.Draw(img)
    for y in range(A):
        k = y / (A - 1)
        d.line([(0, y), (L, y)], fill=tuple(int(c1 + (c2 - c1) * k) for c1, c2 in zip(topo, base)))
    return img


def _centro(d, y, texto, fonte, cor, stroke=0, cor_stroke=(0, 0, 0)):
    d.text(((L - d.textlength(texto, font=fonte)) / 2, y), texto, font=fonte, fill=cor,
           stroke_width=stroke, stroke_fill=cor_stroke)


def _ajustar(d, texto, fabrica, tam, largura, minimo=44):
    """Fonte do maior tamanho (até `tam`) em que o texto cabe na largura."""
    while tam > minimo:
        f = fabrica(tam)
        if d.textlength(texto, font=f) <= largura:
            return f
        tam -= 4
    return fabrica(minimo)


def _barra_quero(d, pos, y, num=None):
    """Faixa do QUERO N."""
    fc = imagem._fonte(46, "ExtraBold")
    partes = [("COMENTE ", imagem.BRANCO), (f"QUERO {pos}", imagem.DOURADO_CLARO), (" E RECEBA O LINK", imagem.BRANCO)]
    if num:
        partes = [("DIGITE ", imagem.BRANCO), (f"#{num}", imagem.DOURADO_CLARO), (" NO LINK DA BIO", imagem.BRANCO)]
    x = (L - sum(d.textlength(t, font=fc) for t, _ in partes)) / 2
    for t, cor in partes:
        d.text((x, y), t, font=fc, fill=cor)
        x += d.textlength(t, font=fc)


# ================================================================== PRODUTO
def produto_garimpo(v, oferta, foto, pos, destino, tiktok=False):
    num = oferta.get("num") if tiktok else None
    if v == 1:
        img = _mina(oferta, foto, pos, num)
    elif v == 2:
        img = _ouro(oferta, foto, pos, num)
    else:   # 0: o cartão do feed com o selo do número
        imagem.gerar(oferta, destino, foto=foto, moldura=False)
        img = Image.open(destino).convert("RGB")
        d = ImageDraw.Draw(img)
        _selo_numero(d, 74, 74, 56, imagem.DOURADO, imagem.ESCURO, imagem._fonte(76, "Black"), pos, imagem.ESCURO)
        d.rectangle([0, A - 118, L, A], fill=imagem.ESCURO)
        _barra_quero(d, pos, A - 84, num)
    img = lojas_arte.moldura_oficial(img, oferta)
    img.save(destino, "JPEG", quality=90, optimize=True)


# ================================================================== CAPA COM PRODUTO
def capa_produto(oferta, foto, n_mais, pose, destino):
    """Capa do carrossel: o 1º produto em destaque num cartão limpo e elegante,
    selo da loja e "+X ACHADOS" no topo, faixa com nome/nota/preço e chamada para arrastar.
    Vale como o slide do produto 1 ("QUERO 1")."""
    img = Image.new("RGB", (L, A), imagem.FUNDO)
    d = ImageDraw.Draw(img)
    cx0, cy0, cx1, cy1 = 44, 44, L - 44, 1000
    d.rounded_rectangle([cx0 + 6, cy0 + 10, cx1 + 6, cy1 + 10], 44, fill=imagem.SOMBRA)
    d.rounded_rectangle([cx0, cy0, cx1, cy1], 44, fill=imagem.BRANCO)
    if foto is not None:
        f = ImageOps.contain(foto.convert("RGB"), (cx1 - cx0 - 60, cy1 - cy0 - 140), Image.LANCZOS)
        img.paste(f, (cx0 + (cx1 - cx0 - f.width) // 2, cy0 + 120 + (cy1 - cy0 - 150 - f.height) // 2))
    _selo_numero(d, cx0 + 66, cy0 + 62, 44, imagem.DOURADO, imagem.ESCURO, imagem._fonte(60, "Black"), 1,
                 imagem.ESCURO)
    fim_selo = cx0 + 126 + imagem.selo_loja(d, oferta, cx0 + 126, cy0 + 30)
    t = f"+{n_mais} ACHADOS  ›"
    f_a = imagem._fonte(30, "ExtraBold")
    w = d.textlength(t, font=f_a)
    if fim_selo + 20 < cx1 - w - 70:
        d.rounded_rectangle([cx1 - w - 70, cy0 + 30, cx1 - 30, cy0 + 94], 32, fill=imagem.DOURADO)
        d.text((cx1 - w - 50, cy0 + 45), t, font=f_a, fill=imagem.BRANCO)

    # Faixa inferior com título, avaliação e preço
    d.rectangle([0, 1040, L, A], fill=imagem.ESCURO)
    x0, y = 60, 1062
    f_tit = imagem._fonte(48, "ExtraBold")
    for ln in imagem._quebrar(d, oferta["titulo"], f_tit, L - 140, max_linhas=2):
        d.text((x0, y), ln, font=f_tit, fill=imagem.BRANCO)
        y += 56
    y += 6
    f_info = imagem._fonte(32, "SemiBold")
    if marcas.eh_marca(oferta):
        d.text((x0, y), marcas.texto_oficial(oferta), font=f_info, fill=imagem.DOURADO_CLARO)
    else:
        imagem._estrela(d, x0 + 18, y + 21, 20, imagem.DOURADO_CLARO)
        d.text((x0 + 46, y), _info(oferta).removeprefix("nota "), font=f_info, fill=imagem.DOURADO_CLARO)
    d.text((x0, y + 50), _brl_linha(oferta), font=imagem._fonte(64, "Black"), fill=imagem.BRANCO)

    # Selo elegante no canto inferior direito ("ARRASTE ››")
    cta_txt = "ARRASTE ››"
    f_cta = imagem._fonte(34, "ExtraBold")
    w_cta = d.textlength(cta_txt, font=f_cta)
    d.rounded_rectangle([L - w_cta - 80, A - 95, L - 40, A - 35], 30, fill=imagem.DOURADO)
    d.text((L - w_cta - 60, A - 85), cta_txt, font=f_cta, fill=imagem.ESCURO)

    img = lojas_arte.moldura_oficial(img, oferta)
    img.save(destino, "JPEG", quality=90, optimize=True)


def _selo_numero(d, cx, cy, r, fundo, contorno, fonte, pos, cor):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fundo, outline=contorno, width=6)
    d.text((cx, cy + 2), str(pos), font=fonte, fill=cor, anchor="mm")


def _mina(o, foto, pos, num=None):
    from . import top
    f = top._f
    im = Image.new("RGB", (L, A))
    d = ImageDraw.Draw(im)
    for y in range(A):
        k = y / A
        d.line([(0, y), (L, y)], fill=(int(80 - 36 * k), int(38 - 18 * k), int(10 - 5 * k)))
    borda = (45, 20, 5)
    d.ellipse((50, 40, 190, 180), fill=top.AM)
    d.text((120, 112), str(pos), font=f(96), fill=borda, anchor="mm")
    d.text((220, 58), f"ACHADO {config.NOME_MARCA.upper()[:16]}", font=f(32), fill=top.AM)
    d.text((220, 98), f"oferta {_loja_nome(o)}", font=f(52), fill=top.BR)
    d.rounded_rectangle((60, 220, L - 60, 900), 36, fill=top.CARD)
    fo = foto.copy()
    fo.thumbnail((L - 180, 620), Image.LANCZOS)
    im.paste(fo, ((L - fo.width) // 2, 250 + (620 - fo.height) // 2))
    imagem.selo_loja(d, o, 90, 900 - 30 - 58, escala=0.9)
    if o.get("desconto"):
        t = f"-{o['desconto']}%"
        ft = f(36)
        w = d.textlength(t, font=ft)
        d.rounded_rectangle((L - 90 - w - 40, 250, L - 90, 312), 30, fill=top.VERMELHO)
        d.text((L - 90 - w - 20, 258), t, font=ft, fill=top.BR)
    y = 930
    for ln in top._quebrar(d, o["titulo"], f(40), L - 140):
        top._ctext(d, y, ln, f(40), top.BR)
        y += 52
    variacoes = o.get("preco_max") and o["preco_max"] > o["preco"] * 1.02
    top._ctext(d, y + 12, "a partir de" if variacoes else "por", f(30), top.BEGE)
    top._ctext(d, y + 44, _brl_linha(o), f(80), top.AM, 4, borda)
    top._ctext(d, y + 150, _info(o), f(32), top.BR)
    t = f"Digite #{num} no link da bio" if num else f"Comente QUERO {pos} que enviamos o link no direct"
    ft = f(34)
    w = d.textlength(t, font=ft)
    d.rounded_rectangle(((L - w) / 2 - 30, A - 112, (L + w) / 2 + 30, A - 44), 34, fill=top.VERDE)
    top._ctext(d, A - 104, t, ft, top.BR)
    return im


def _ouro(o, foto, pos, num=None):
    im = Image.new("RGB", (L, A), (226, 178, 54))
    d = ImageDraw.Draw(im)
    d.ellipse((-260, -260, 640, 640), fill=(238, 200, 98))
    d.ellipse((520, 760, 1380, 1620), fill=(212, 162, 38))
    d.ellipse((120, 150, 960, 990), fill=imagem.BRANCO)
    fo = ImageOps.contain(foto, (620, 620), Image.LANCZOS)
    im.paste(fo, (540 - fo.width // 2, 570 - fo.height // 2))
    _selo_numero(d, 100, 100, 62, imagem.ESCURO, imagem.BRANCO, imagem._fonte(78, "Black"), pos, (238, 200, 98))
    rascunho = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    imagem.selo_loja(d, o, L - 70 - imagem.selo_loja(rascunho, o, 0, 0), 62)
    if o.get("desconto"):
        cx, cy, r = 880, 920, 92
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(205, 48, 36), outline=imagem.BRANCO, width=6)
        d.text((cx, cy - 12), f"-{o['desconto']}%", font=imagem._fonte(50, "Black"), fill=imagem.BRANCO, anchor="mm")
        d.text((cx, cy + 34), "OFF", font=imagem._fonte(32, "ExtraBold"), fill=imagem.BRANCO, anchor="mm")
    y = 965
    ft = imagem._fonte(44, "ExtraBold")
    for ln in imagem._quebrar(d, o["titulo"], ft, L - 150, max_linhas=2):
        _centro(d, y, ln, ft, imagem.ESCURO)
        y += 54
    _centro(d, y + 6, _brl_linha(o), imagem._fonte(104, "Black"), imagem.ESCURO)
    _centro(d, y + 128, _info(o), imagem._fonte(32, "SemiBold"), (92, 58, 12))
    d.rectangle([0, A - 118, L, A], fill=imagem.ESCURO)
    _barra_quero(d, pos, A - 84, num)
    return im


def produto_ana(v, oferta, foto, pos, destino):
    produto_garimpo(v, oferta, foto, pos, destino)


QUEM_CATEGORIA = {
    "casa_decor": "que ama decorar e organizar a casa",
    "cozinha": "que adora coisas práticas pra cozinha",
    "utilidades": "que ama praticidade no dia a dia",
    "pet": "que tem pet em casa",
    "lar": "que tá montando ou renovando a casa",
    "eletronicos": "que adora novidades de tecnologia",
    "beleza": "que ama cuidados pessoais",
}


def frase_compartilhar(ofertas, v):
    com_cat = [(i, o) for i, o in enumerate(ofertas, 1) if o.get("categoria") in QUEM_CATEGORIA]
    if not com_cat:
        return "Lembrou de alguém especial? Compartilhe esse post!"
    i, o = com_cat[v % len(com_cat)]
    return f"Conhece alguém {QUEM_CATEGORIA[o['categoria']]}? Mande o {i} pra ela!"


def fim_de_mes(hoje=None):
    from .garimpar import agora
    dia = (hoje or agora()).day
    return dia >= 25 or dia <= 5


def final_garimpo(v, n, n_variante, youtube=False, frase=None, tiktok=False):
    im = Image.new("RGB", (L, A), (250, 247, 242))
    d = ImageDraw.Draw(im)

    # Borda elegante sutil
    d.rounded_rectangle((35, 35, L - 35, A - 35), radius=32, outline=(220, 195, 155), width=2)
    d.rounded_rectangle((42, 42, L - 42, A - 42), radius=28, outline=(240, 228, 210), width=1)

    # Logo grande e em destaque na parte superior
    if config.LOGO.exists():
        try:
            logo = Image.open(config.LOGO).convert("RGBA")
            tam = 530
            logo = logo.resize((tam, tam), Image.Resampling.LANCZOS)
            im.paste(logo, ((L - tam) // 2, 80), logo)
        except Exception:
            pass

    # Titulo / Pergunta
    f_tit = imagem._fonte(52, "Bold")
    tit = FINAIS[n_variante % len(FINAIS)]
    d.text(((L - d.textlength(tit, font=f_tit)) / 2, 650), tit, font=f_tit, fill=(44, 34, 30))

    # Card com as instrucoes de como receber o link
    d.rounded_rectangle((80, 730, L - 80, 1030), radius=28, fill=(255, 255, 255), outline=(230, 218, 202), width=2)

    if tiktok:
        f1 = imagem._fonte(36, "Medium")
        t1 = "Para receber o link com desconto:"
        d.text(((L - d.textlength(t1, font=f1)) / 2, 770), t1, font=f1, fill=(90, 80, 75))

        f_dest = imagem._fonte(46, "ExtraBold")
        t2 = f"Digite o número (1 a {n})"
        d.text(((L - d.textlength(t2, font=f_dest)) / 2, 830), t2, font=f_dest, fill=(180, 130, 60))

        f_ex = imagem._fonte(32, "SemiBold")
        t_ex = "no link da bio para abrir direto na loja!"
        d.text(((L - d.textlength(t_ex, font=f_ex)) / 2, 895), t_ex, font=f_ex, fill=(120, 110, 105))

        f3 = imagem._fonte(34, "Bold")
        t3 = "Link direto com desconto exclusivo!"
        d.text(((L - d.textlength(t3, font=f3)) / 2, 955), t3, font=f3, fill=(44, 34, 30))
    else:
        f1 = imagem._fonte(36, "Medium")
        t1 = "Para receber o link com desconto:"
        d.text(((L - d.textlength(t1, font=f1)) / 2, 770), t1, font=f1, fill=(90, 80, 75))

        f_dest = imagem._fonte(46, "ExtraBold")
        t2 = "Comente  QUERO + NÚMERO"
        d.text(((L - d.textlength(t2, font=f_dest)) / 2, 830), t2, font=f_dest, fill=(180, 130, 60))

        f_ex = imagem._fonte(32, "SemiBold")
        t_ex = f"(exemplo: QUERO 1 a QUERO {n})" if n > 2 else "(exemplo: QUERO 1 ou QUERO 2)"
        d.text(((L - d.textlength(t_ex, font=f_ex)) / 2, 895), t_ex, font=f_ex, fill=(120, 110, 105))

        f3 = imagem._fonte(34, "Bold")
        t3 = "Enviamos o link aqui nos comentários!" if youtube else "Enviamos o link na hora no seu Direct!"
        d.text(((L - d.textlength(t3, font=f3)) / 2, 955), t3, font=f3, fill=(44, 34, 30))

    # Dica / Salvar / Compartilhar
    f_dica = imagem._fonte(30, "Medium")
    t_dica = frase if frase else "Salve esse post para não perder as ofertas!"
    if d.textlength(t_dica, font=f_dica) > L - 160:
        f_dica = _ajustar(d, t_dica, lambda t: imagem._fonte(t, "Medium"), 30, L - 160, minimo=22)
    d.text(((L - d.textlength(t_dica, font=f_dica)) / 2, 1075), t_dica, font=f_dica, fill=(100, 90, 85))

    # Botao de chamada para seguir
    f_btn = imagem._fonte(32, "Bold")
    arroba = config.ARROBA or "@ba.homeliving"
    t_btn = f"Siga {arroba} para mais achados"
    bw = d.textlength(t_btn, font=f_btn) + 80
    bx0 = (L - bw) / 2
    d.rounded_rectangle((bx0, 1150, bx0 + bw, 1230), radius=40, fill=(197, 168, 128))
    d.text(((L - d.textlength(t_btn, font=f_btn)) / 2, 1172), t_btn, font=f_btn, fill=(255, 255, 255))

    return im


def final_ana(v, n):
    return final_garimpo(v, n, v)


def faixa_titulo(destino_png, v, dias_bf=None):
    img = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    titulo, sub = TITULOS[v % N_TITULO]
    f = _ajustar(d, titulo, lambda t: imagem._fonte(t, "Black"), 86, L - 200)
    fs = imagem._fonte(38, "SemiBold")
    fundo, cor, cor_sub = (45, 28, 12, 215), imagem.DOURADO_CLARO, imagem.BRANCO
    tw = d.textlength(sub, font=fs) + 70
    w = max(d.textlength(titulo, font=f), tw) + 90
    x0 = (L - w) / 2
    em_cima = v % 2 == 0
    y0 = 56 if em_cima else A - 290
    d.rounded_rectangle((x0, y0, x0 + w, y0 + 194), 44, fill=fundo)
    d.text(((L - d.textlength(titulo, font=f)) / 2, y0 + 22), titulo, font=f, fill=cor)
    xs = (L - tw) / 2
    d.text((xs, y0 + 122), sub, font=fs, fill=cor_sub)
    img.save(destino_png)
