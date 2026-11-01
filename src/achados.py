"""🛍️ Carrossel de Achados — vários produtos num post só, personalizável e escalável.

Slides (1080x1350):
1) Capa de produto em destaque (+X ACHADOS)
2) a N) Produtos numerados para engajamento ("QUERO 1", "QUERO 2", etc.)
Último) Chamada para comentar e seguir.

Quem comenta "QUERO 2" recebe o link do 2º; só "QUERO" recebe a lista com todos.

Uso:
  python -m src.achados preparar   → escolhe os produtos e gera os slides em site/midia/achados/
  python -m src.achados publicar   → publica o carrossel (precisa do PAGES_URL) e marca as ofertas como postadas
  python -m src.achados previa     → só gera os slides em data/relatorios/achados/
"""
import json
import os
import random
import shutil
import subprocess
import sys
import time
from datetime import timedelta

from PIL import Image, ImageDraw

from . import achados_artes as artes, aliexpress, config, imagem, instagram, marcas, numeros, vitrine
from .garimpar import FMT, agora, carregar_fila, salvar_fila

QTD = max(3, min(5, int(os.getenv("ACHADOS_QTD", "4") or 4)))
MINIMO = max(2, int(os.getenv("ACHADOS_MINIMO", "3") or 3))
L, A = 1080, 1350
PASTA_SITE = config.RAIZ / "site"
ARQ_PROXIMO = config.PASTA_PERFIL / "achados_proximo.json"
ARQ_ESTADO = config.PASTA_PERFIL / "achados.json"
ARQ_TOP = config.PASTA_PERFIL / "top.json"
NUM = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]


def _saida(chave, valor):
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"{chave}={valor}\n")


# ---------------------------------------------------------------- o que entra
def escolher(fila, conferir=True):
    """QTD ofertas de tipos diferentes, com foto e preço conferidos."""
    from . import postar, precos, variedade
    lista = [o for o in postar.candidatos_ordenados(fila) if not o.get("video_manual") and not o.get("pedido")]
    itens, familias, categorias, ids = [], set(), set(), set()
    shark = False
    vagas_ae = aliexpress.vagas_hoje(fila, "postado_em", config.ALIEXPRESS_POR_DIA_INSTAGRAM, agora().strftime("%Y-%m-%d"))

    def tentar(o, so_categoria_nova):
        nonlocal shark, vagas_ae
        fam = variedade.familia(o)
        if o["id"] in ids or fam in familias or (marcas.eh_marca(o) and shark):
            return
        if o.get("plataforma") == "aliexpress" and vagas_ae <= 0:
            return
        if so_categoria_nova and o.get("categoria") in categorias:
            return
        if conferir:
            situacao = precos.conferir(o)
            if situacao in ("sumiu", "subiu"):
                o["status"] = "descartado"
                o["motivo"] = "produto fora do ar" if situacao == "sumiu" else "preço subiu desde o garimpo"
                print(f"🗑️  {o.get('titulo')}: {o['motivo']} — pulando.")
                ids.add(o["id"])
                return
        try:
            foto = imagem._baixar_foto(o["imagem"])
        except Exception as e:
            print(f"⚠️  Foto de {o['id']} não baixou ({e}); tentando outra oferta.")
            ids.add(o["id"])
            return
        itens.append({"oferta": o, "foto": foto})
        ids.add(o["id"])
        familias.add(fam)
        categorias.add(o.get("categoria"))
        shark = shark or marcas.eh_marca(o)
        vagas_ae -= o.get("plataforma") == "aliexpress"
        print(f"🛍️  {len(itens)}. {o['titulo'][:60]} — R$ {o['preco_fmt']} ({o.get('categoria')})")

    for so_categoria_nova in (True, False):
        for o in lista:
            if len(itens) >= QTD:
                break
            tentar(o, so_categoria_nova)
    return itens


# ---------------------------------------------------------------- slides dos produtos
def slide_produto(oferta, foto, pos, destino, v=0, tiktok=False):
    """Arte do produto com o número para 'QUERO N'."""
    artes.produto_garimpo(v % artes.N_PRODUTO, oferta, foto, pos, destino, tiktok=tiktok)


def slide_final(n, v, frase=None):
    return artes.final_garimpo(v, n, v, frase=frase)


def _carregar_estado():
    if ARQ_ESTADO.exists():
        try:
            return json.loads(ARQ_ESTADO.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"videos": {}, "n": 0}


def variante():
    forcada = os.getenv("ACHADOS_VARIANTE")
    if forcada not in (None, ""):
        return int(forcada)
    return int(_carregar_estado().get("n", 0))


# ---------------------------------------------------------------- legenda
def legenda(itens):
    n = len(itens)
    linhas = [
        f"✨ {n} Achadinhos incríveis que você precisa conhecer hoje!",
        "",
        f"Seleção especial da {config.NOME_MARCA} com as melhores avaliações e descontos:",
        ""
    ]
    for i, it in enumerate(itens, 1):
        o = it["oferta"]
        linhas.append(f"{NUM[i - 1]} {_curto(o['titulo'])} — R$ {o['preco_fmt']}")

    linhas += [
        "",
        "👇 Comente QUERO + o número (ex.: QUERO 1 ou QUERO 2) que enviamos o link direto no seu chat!",
        "🔎 Procurando algo diferente? Comente aqui que buscamos as melhores ofertas para você!"
    ]
    if config.PAGINA_BIO:
        linhas.append(f"🔗 Links completos também disponíveis em: {config.PAGINA_BIO}")
    linhas += [
        "",
        "Preços conferidos na postagem — podem sofrer alterações pela loja. Links de afiliado oficial.",
        "",
        f"#achadinhos #shopee #achadosshopee #casadecor #utilidades #achados {config.HASHTAG_MARCA}".strip()
    ]
    return "\n".join(linhas)


def _curto(nome, n=55):
    nome = " ".join(str(nome).split())
    return nome if len(nome) <= n else nome[:n].rsplit(" ", 1)[0] + "…"


# ---------------------------------------------------------------- gerar / preparar / publicar
def gerar(itens, pasta):
    v = variante()
    pasta.mkdir(parents=True, exist_ok=True)
    marca = int(time.time())
    arqs = []

    # Slide 1: Capa com produto em destaque
    nome_capa = f"achados-{marca}-capa.jpg"
    artes.capa_produto(itens[0]["oferta"], itens[0]["foto"], len(itens) - 1, ("aponta", "joia")[v % 2],
                       pasta / nome_capa)
    arqs.append(nome_capa)

    # Slides 2 a N: Produtos numerados
    for i, it in enumerate(itens[1:], 2):
        nome_prod = f"achados-{marca}-{i}.jpg"
        slide_produto(it["oferta"], it["foto"], i, pasta / nome_prod, v)
        arqs.append(nome_prod)

    # Slide final com CTA
    nome_fim = f"achados-{marca}-{len(itens) + 1}.jpg"
    frase = artes.frase_compartilhar([it["oferta"] for it in itens], v)
    slide_final(len(itens), v, frase).save(pasta / nome_fim, quality=92)
    arqs.append(nome_fim)

    return {
        "arquivos": arqs,
        "clipe": "",
        "story": None,
        "short": None,
        "tiktok": [],
        "legenda_tiktok": "",
        "itens": [{k: it["oferta"].get(k) for k in ("id", "nome", "titulo", "preco_fmt", "link_afiliado", "plataforma", "imagem", "num")}
                  for it in itens]
    }


def preparar():
    _saida("tem_post", "false")
    if not instagram.tem_token():
        print("⏸️  Token do Instagram ausente — carrossel em espera.")
        return
    fila = carregar_fila()
    itens = escolher(fila)
    if len(itens) >= MINIMO:
        for it in itens:
            numeros.numerar(it["oferta"])
    salvar_fila(fila)
    if len(itens) < MINIMO:
        print(f"⚠️  Só {len(itens)} produtos bons na fila — não vale postar carrossel tão curto.")
        return
    pasta = PASTA_SITE / "midia" / "achados"
    PASTA_SITE.mkdir(parents=True, exist_ok=True)
    (PASTA_SITE / ".nojekyll").write_text("")
    paginas = config.RAIZ / "assets" / "paginas"
    if paginas.exists():
        for fixo in paginas.glob("*.html"):
            (PASTA_SITE / fixo.name).write_text(fixo.read_text(encoding="utf-8"), encoding="utf-8")
    info = gerar(itens, pasta)
    info["legenda"] = legenda(itens)
    ARQ_PROXIMO.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    _saida("tem_post", "true")
    print(f"🛍️  Carrossel de achados preparado com {len(itens)} produtos.")


def publicar():
    from .postar import _esperar_url
    info = json.loads(ARQ_PROXIMO.read_text(encoding="utf-8"))
    base = (os.getenv("PAGES_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("PAGES_URL ausente.")
    urls = [f"{base}/midia/achados/{a}" for a in info["arquivos"]]
    for u in urls:
        _esperar_url(u)
    ig_id = instagram.conferir_conta()["user_id"]
    filhos = [instagram.criar_item_carrossel(ig_id, video_url=u) if u.endswith(".mp4")
              else instagram.criar_item_carrossel(ig_id, imagem_url=u) for u in urls]
    for c in filhos:
        instagram.aguardar_container(c)
    cont = instagram.criar_carrossel(ig_id, filhos, info["legenda"])
    instagram.aguardar_container(cont)
    media_id = instagram.publicar(ig_id, cont)
    permalink = instagram.permalink(media_id)
    agora_s = agora().strftime(FMT)

    # Registro lido pelo responder.py ("QUERO 1", "QUERO 2"...)
    dados = json.loads(ARQ_TOP.read_text(encoding="utf-8")) if ARQ_TOP.exists() else {"posts": {}}
    dados["posts"][media_id] = {
        "tipo": "achados",
        "rotulo": agora().strftime("%d/%m"),
        "itens": info["itens"],
        "postado_em": agora_s,
        "permalink": permalink
    }
    limite = (agora() - timedelta(days=60)).strftime(FMT)
    dados["posts"] = {k: v for k, v in dados["posts"].items() if v.get("postado_em", "") >= limite}
    ARQ_TOP.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    fila = carregar_fila()
    for it in info["itens"]:
        o = fila["ofertas"].get(it["id"])
        if o:
            o.update({"status": "postado", "formato": "achados", "postado_em": agora_s,
                      "postado_ts": time.time(), "achados_post": media_id, "permalink": permalink})
    salvar_fila(fila)
    vitrine.gerar()

    estado = _carregar_estado()
    if info.get("clipe"):
        estado["videos"][info["clipe"]] = agora_s
    estado["n"] = int(estado.get("n", 0)) + 1
    ARQ_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    ARQ_PROXIMO.unlink(missing_ok=True)
    print(f"✅ Carrossel de achados publicado ({config.ARROBA}): {permalink or media_id}")


def previa(tipo=None):
    """Gera os slides na pasta temporária para conferência visual."""
    fila = carregar_fila()
    itens = escolher(fila, conferir=False)
    if not itens:
        print("⚠️ Fila vazia.")
        return
    pasta = config.RAIZ / "data" / "relatorios" / "achados"
    info = gerar(itens, pasta)
    print(f"🖼️ Prévia gerada em {pasta}: {info['arquivos']}")


if __name__ == "__main__":
    cmd = (sys.argv[1:2] or ["preparar"])[0].lower()
    if cmd == "preparar":
        preparar()
    elif cmd == "publicar":
        publicar()
    elif cmd == "previa":
        previa()
    else:
        print(f"Comando '{cmd}' desconhecido. Use: preparar, publicar ou previa.")
