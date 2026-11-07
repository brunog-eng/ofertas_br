"""Artes do carrossel de achados (src/achados.py): visual elegante, moderno e padronizado
alinhado com a identidade da marca BA Home & Living (paleta em linho, dourado suave e café/carvão do logo).
"""
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import config, imagem, lojas_arte, marcas

L, A = 1080, 1350

# Paleta oficial alinhada ao logo e ao último slide
FUNDO = (250, 247, 242)          # Linho / off-white suave (#FAF7F2)
BORDA1 = (220, 195, 155)         # Champagne / dourado areia (#DCC39B)
BORDA2 = (240, 228, 210)         # Bege bem clarinho (#F0E4D2)
CARD_FUNDO = (255, 255, 255)     # Branco puro para valorizar o produto
CARD_BORDA = (230, 218, 202)     # Contorno sutil do card
CARD_SOMBRA = (235, 226, 215)    # Sombra suave sob o card
ESCURO = (44, 34, 30)            # Café / carvão quente do logo (#2C221E)
DOURADO = (197, 168, 128)        # Dourado suave (#C5A880)
DOURADO_TEXTO = (180, 130, 60)   # Dourado caramelo para destaques (#B4823C)
CINZA_TEXTO = (100, 90, 85)      # Texto secundário (#645A55)
BRANCO = (255, 255, 255)
VERMELHO_DESC = (195, 60, 45)    # Vermelho refinado para selo de desconto

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


def _fonte(tam, peso="Bold"):
    return imagem._fonte(tam, peso)


def _brl_linha(o):
    return f"R$ {o['preco_fmt']}"


def _limpar_titulo(t):
    t = " ".join(str(t or "").split())
    for c in ["\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212"]:
        t = t.replace(c, "-")
    return t


def _logo_topo(im, y=48, max_h=120, max_w=320):
    """Insere o logo da loja centralizado no topo com corte de margens transparentes."""
    if config.LOGO.exists():
        try:
            logo = Image.open(config.LOGO).convert("RGBA")
            bbox = logo.getbbox()
            if bbox:
                logo = logo.crop(bbox)
            ratio = min(max_w / logo.width, max_h / logo.height)
            nw, nh = int(logo.width * ratio), int(logo.height * ratio)
            logo = logo.resize((nw, nh), Image.Resampling.LANCZOS)
            im.paste(logo, ((L - nw) // 2, y + (max_h - nh) // 2), logo)
            return True
        except Exception:
            pass
    return False


def _selo_numero(d, cx, cy, r, pos):
    """Selo elegante com o número do produto (1, 2, 3...)."""
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ESCURO, outline=BORDA1, width=4)
    f = _fonte(int(r * 1.15), "Black")
    d.text((cx, cy + 2), str(pos), font=f, fill=DOURADO, anchor="mm")


def _avaliacao(d, o, y):
    """Estrela vetorial e texto com nota e quantidade de vendas."""
    vendas = f"{o.get('vendas', 0):,}".replace(",", ".")
    nota = str(o.get('nota', '5.0')).replace('.', ',')
    texto = f"{nota}  •  {vendas}+ vendidos"
    if marcas.eh_marca(o):
        texto = marcas.texto_oficial(o)
    f_inf = _fonte(30, "SemiBold")
    w_txt = d.textlength(texto, font=f_inf)
    r_star = 16
    gap = 12
    w_tot = (2 * r_star) + gap + w_txt
    x0 = (L - w_tot) / 2
    cx_star = x0 + r_star
    cy_star = y + 16
    imagem._estrela(d, cx_star, cy_star, r_star, DOURADO_TEXTO)
    d.text((x0 + 2 * r_star + gap, y), texto, font=f_inf, fill=CINZA_TEXTO)


# ================================================================== CAPA DO CARROSSEL (SLIDE 1)
def capa_produto(oferta, foto, n_mais, pose, destino):
    """Capa do carrossel: o 1º produto em destaque com logo centralizado,
    selo #1 no topo esquerdo, badge '+X ACHADOS ›', foto no card branco e chamada 'ARRASTE PARA O LADO ››'.
    """
    im = Image.new("RGB", (L, A), FUNDO)
    d = ImageDraw.Draw(im)

    # Bordas duplas refinadas
    d.rounded_rectangle((35, 35, L - 35, A - 35), radius=32, outline=BORDA1, width=2)
    d.rounded_rectangle((42, 42, L - 42, A - 42), radius=28, outline=BORDA2, width=1)

    # Topo: Logo da marca centralizado
    _logo_topo(im, y=48, max_h=120, max_w=320)

    # Topo Esquerda: Selo #1
    _selo_numero(d, 105, 105, 42, 1)

    # Topo Direita: +X ACHADOS ›
    t_mais = f"+{n_mais} ACHADOS  ›"
    f_mais = _fonte(26, "ExtraBold")
    w_mais = d.textlength(t_mais, font=f_mais)
    d.rounded_rectangle([L - w_mais - 110, 80, L - 65, 132], 26, fill=ESCURO, outline=BORDA1, width=2)
    d.text((L - w_mais - 88, 92), t_mais, font=f_mais, fill=DOURADO)

    # Card da Foto do Produto
    cx0, cy0, cx1, cy1 = 65, 180, L - 65, 930
    d.rounded_rectangle((cx0 + 4, cy0 + 6, cx1 + 4, cy1 + 6), radius=32, fill=CARD_SOMBRA)
    d.rounded_rectangle((cx0, cy0, cx1, cy1), radius=32, fill=CARD_FUNDO, outline=CARD_BORDA, width=2)

    # Foto
    if foto is not None:
        fo = ImageOps.contain(foto.convert("RGB"), (cx1 - cx0 - 60, cy1 - cy0 - 60), Image.Resampling.LANCZOS)
        im.paste(fo, (cx0 + (cx1 - cx0 - fo.width) // 2, cy0 + (cy1 - cy0 - fo.height) // 2))

    # Selo da Loja dentro do card (canto superior direito)
    rascunho = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    w_selo = imagem.selo_loja(rascunho, oferta, 0, 0, escala=0.85)
    imagem.selo_loja(d, oferta, cx1 - w_selo - 20, cy0 + 20, escala=0.85)

    # Selo de Desconto
    if oferta.get("desconto"):
        desc = oferta["desconto"]
        r = 65
        sx, sy = cx1 - 50, cy1 - 50
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=VERMELHO_DESC, outline=BRANCO, width=5)
        d.text((sx, sy - 12), f"-{desc}%", font=_fonte(38, "Black"), fill=BRANCO, anchor="mm")
        d.text((sx, sy + 22), "OFF", font=_fonte(22, "Bold"), fill=BRANCO, anchor="mm")

    # Informações abaixo da foto
    y = 960
    f_tit = _fonte(44, "ExtraBold")
    titulo = _limpar_titulo(oferta.get("titulo", ""))
    for ln in imagem._quebrar(d, titulo, f_tit, L - 140, max_linhas=2):
        d.text(((L - d.textlength(ln, font=f_tit)) / 2, y), ln, font=f_tit, fill=ESCURO)
        y += 52

    preco_str = _brl_linha(oferta)
    f_pr = _fonte(92, "Black")
    d.text(((L - d.textlength(preco_str, font=f_pr)) / 2, y + 8), preco_str, font=f_pr, fill=ESCURO)

    _avaliacao(d, oferta, y + 115)

    # Barra Inferior
    d.rectangle([0, A - 95, L, A], fill=ESCURO)
    f_cta = _fonte(36, "Bold")
    f_cta_b = _fonte(36, "Black")
    p1 = "ARRASTE PARA O LADO "
    p2 = "››"
    w_tot = d.textlength(p1, font=f_cta) + d.textlength(p2, font=f_cta_b)
    x_cta = (L - w_tot) / 2
    d.text((x_cta, A - 68), p1, font=f_cta, fill=BRANCO)
    d.text((x_cta + d.textlength(p1, font=f_cta), A - 68), p2, font=f_cta_b, fill=DOURADO)

    im = lojas_arte.moldura_oficial(im, oferta)
    im.save(destino, "JPEG", quality=92, optimize=True)


# ================================================================== PRODUTOS (SLIDES 2 A N)
def produto_garimpo(v, oferta, foto, pos, destino, tiktok=False):
    """Arte do produto com o número para 'QUERO N', logo da loja e estética alinhada."""
    num = oferta.get("num") if tiktok else None
    im = Image.new("RGB", (L, A), FUNDO)
    d = ImageDraw.Draw(im)

    # Bordas duplas refinadas
    d.rounded_rectangle((35, 35, L - 35, A - 35), radius=32, outline=BORDA1, width=2)
    d.rounded_rectangle((42, 42, L - 42, A - 42), radius=28, outline=BORDA2, width=1)

    # Topo: Logo da marca centralizado
    _logo_topo(im, y=48, max_h=120, max_w=320)

    # Topo Esquerda: Selo do Número (2, 3, 4...)
    _selo_numero(d, 105, 105, 42, pos)

    # Topo Direita: Selo da Loja
    rascunho = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    w_selo = imagem.selo_loja(rascunho, oferta, 0, 0, escala=0.85)
    imagem.selo_loja(d, oferta, L - 65 - w_selo, 82, escala=0.85)

    # Card da Foto do Produto
    cx0, cy0, cx1, cy1 = 65, 180, L - 65, 930
    d.rounded_rectangle((cx0 + 4, cy0 + 6, cx1 + 4, cy1 + 6), radius=32, fill=CARD_SOMBRA)
    d.rounded_rectangle((cx0, cy0, cx1, cy1), radius=32, fill=CARD_FUNDO, outline=CARD_BORDA, width=2)

    # Foto
    if foto is not None:
        fo = ImageOps.contain(foto.convert("RGB"), (cx1 - cx0 - 60, cy1 - cy0 - 60), Image.Resampling.LANCZOS)
        im.paste(fo, (cx0 + (cx1 - cx0 - fo.width) // 2, cy0 + (cy1 - cy0 - fo.height) // 2))

    # Selo de Desconto se houver
    if oferta.get("desconto"):
        desc = oferta["desconto"]
        r = 65
        sx, sy = cx1 - 50, cy1 - 50
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=VERMELHO_DESC, outline=BRANCO, width=5)
        d.text((sx, sy - 12), f"-{desc}%", font=_fonte(38, "Black"), fill=BRANCO, anchor="mm")
        d.text((sx, sy + 22), "OFF", font=_fonte(22, "Bold"), fill=BRANCO, anchor="mm")

    # Informações abaixo da foto
    y = 960
    f_tit = _fonte(44, "ExtraBold")
    titulo = _limpar_titulo(oferta.get("titulo", ""))
    for ln in imagem._quebrar(d, titulo, f_tit, L - 140, max_linhas=2):
        d.text(((L - d.textlength(ln, font=f_tit)) / 2, y), ln, font=f_tit, fill=ESCURO)
        y += 52

    preco_str = _brl_linha(oferta)
    f_pr = _fonte(92, "Black")
    d.text(((L - d.textlength(preco_str, font=f_pr)) / 2, y + 8), preco_str, font=f_pr, fill=ESCURO)

    _avaliacao(d, oferta, y + 115)

    # Barra Inferior com chamada QUERO {pos}
    d.rectangle([0, A - 95, L, A], fill=ESCURO)
    fc = _fonte(36, "Bold")
    fc_d = _fonte(38, "Black")
    if num:
        partes = [("DIGITE ", BRANCO, fc), (f"#{num}", DOURADO, fc_d), (" NO LINK DA BIO", BRANCO, fc)]
    else:
        partes = [("COMENTE ", BRANCO, fc), (f"QUERO {pos}", DOURADO, fc_d), (" E RECEBA O LINK", BRANCO, fc)]
    w_tot = sum(d.textlength(t, font=f) for t, _, f in partes)
    x = (L - w_tot) / 2
    for t, cor, f in partes:
        d.text((x, A - 68), t, font=f, fill=cor)
        x += d.textlength(t, font=f)

    im = lojas_arte.moldura_oficial(im, oferta)
    im.save(destino, "JPEG", quality=92, optimize=True)


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


# ================================================================== SLIDE FINAL
def final_garimpo(v, n, n_variante, youtube=False, frase=None, tiktok=False):
    im = Image.new("RGB", (L, A), FUNDO)
    d = ImageDraw.Draw(im)

    # Borda elegante sutil
    d.rounded_rectangle((35, 35, L - 35, A - 35), radius=32, outline=BORDA1, width=2)
    d.rounded_rectangle((42, 42, L - 42, A - 42), radius=28, outline=BORDA2, width=1)

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
    f_tit = _fonte(52, "Bold")
    tit = FINAIS[n_variante % len(FINAIS)]
    d.text(((L - d.textlength(tit, font=f_tit)) / 2, 650), tit, font=f_tit, fill=ESCURO)

    # Card com as instrucoes de como receber o link
    d.rounded_rectangle((80, 730, L - 80, 1030), radius=28, fill=CARD_FUNDO, outline=CARD_BORDA, width=2)

    if tiktok:
        f1 = _fonte(36, "Medium")
        t1 = "Para receber o link com desconto:"
        d.text(((L - d.textlength(t1, font=f1)) / 2, 770), t1, font=f1, fill=(90, 80, 75))

        f_dest = _fonte(46, "ExtraBold")
        t2 = f"Digite o número (1 a {n})"
        d.text(((L - d.textlength(t2, font=f_dest)) / 2, 830), t2, font=f_dest, fill=DOURADO_TEXTO)

        f_ex = _fonte(32, "SemiBold")
        t_ex = "no link da bio para abrir direto na loja!"
        d.text(((L - d.textlength(t_ex, font=f_ex)) / 2, 895), t_ex, font=f_ex, fill=(120, 110, 105))

        f3 = _fonte(34, "Bold")
        t3 = "Link direto com desconto exclusivo!"
        d.text(((L - d.textlength(t3, font=f3)) / 2, 955), t3, font=f3, fill=ESCURO)
    else:
        f1 = _fonte(36, "Medium")
        t1 = "Para receber o link com desconto:"
        d.text(((L - d.textlength(t1, font=f1)) / 2, 770), t1, font=f1, fill=(90, 80, 75))

        f_dest = _fonte(46, "ExtraBold")
        t2 = "Comente  QUERO + NÚMERO"
        d.text(((L - d.textlength(t2, font=f_dest)) / 2, 830), t2, font=f_dest, fill=DOURADO_TEXTO)

        f_ex = _fonte(32, "SemiBold")
        t_ex = f"(exemplo: QUERO 1 a QUERO {n})" if n > 2 else "(exemplo: QUERO 1 ou QUERO 2)"
        d.text(((L - d.textlength(t_ex, font=f_ex)) / 2, 895), t_ex, font=f_ex, fill=(120, 110, 105))

        f3 = _fonte(34, "Bold")
        t3 = "Enviamos o link aqui nos comentários!" if youtube else "Enviamos o link na hora no seu Direct!"
        d.text(((L - d.textlength(t3, font=f3)) / 2, 955), t3, font=f3, fill=ESCURO)

    # Dica / Salvar / Compartilhar
    f_dica = _fonte(30, "Medium")
    t_dica = frase if frase else "Salve esse post para não perder as ofertas!"
    if d.textlength(t_dica, font=f_dica) > L - 160:
        f_dica = imagem._quebrar(d, t_dica, f_dica, L - 160, max_linhas=1)[0]
    d.text(((L - d.textlength(t_dica, font=f_dica)) / 2, 1075), t_dica, font=f_dica, fill=CINZA_TEXTO)

    # Botao de chamada para seguir
    f_btn = _fonte(32, "Bold")
    arroba = config.ARROBA or "@ba.homeliving"
    t_btn = f"Siga {arroba} para mais achados"
    bw = d.textlength(t_btn, font=f_btn) + 80
    bx0 = (L - bw) / 2
    d.rounded_rectangle((bx0, 1150, bx0 + bw, 1230), radius=40, fill=DOURADO)
    d.text(((L - d.textlength(t_btn, font=f_btn)) / 2, 1172), t_btn, font=f_btn, fill=BRANCO)

    return im


def final_ana(v, n):
    return final_garimpo(v, n, v)
