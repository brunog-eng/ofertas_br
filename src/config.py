"""Configurações gerais do Robô de Ofertas da Shopee.
Customizável via variáveis de ambiente para qualquer marca ou nicho.
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
FONTE = RAIZ / "assets" / "Montserrat.ttf"

# --- Credenciais (Secrets do GitHub) ---
SHOPEE_APP_ID = (os.getenv("SHOPEE_APP_ID") or "").strip()
SHOPEE_APP_SECRET = (os.getenv("SHOPEE_APP_SECRET") or "").strip()
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()

SHOPEE_API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
GROQ_URL = "https://api.groq.com/openai/v1"
GROQ_MODELOS = [m.strip() for m in os.getenv(
    "GROQ_MODELOS", "openai/gpt-oss-120b,openai/gpt-oss-20b,qwen/qwen3.8-27b,llama-3.3-70b-versatile").split(",") if m.strip()]

# --- Identidade da Marca (Customizável por Variáveis de Ambiente) ---
BRAND_NAME = os.getenv("BRAND_NAME", "BA Home & Living")
BRAND_HANDLE = os.getenv("BRAND_HANDLE", "@ba.homeliving")
BRAND_HASHTAG = os.getenv("BRAND_HASHTAG", "#BAHomeLiving")
BRAND_TONE = os.getenv("BRAND_TONE", "Tom acolhedor, moderno e elegante, focado em achadinhos úteis para transformar o lar.")
BRAND_AUDIENCE = os.getenv("BRAND_AUDIENCE", "Pessoas que buscam praticidade, decoração e organização para casa.")

# --- Nichos de Busca (Categorias e Palavras-chave) ---
NICHOS = {
    "casa_e_decoracao": [
        "organizador acrílico", "luminária decorativa", "espelho decorativo",
        "organizador closet", "potes herméticos", "luminária nuvem",
        "tapete banheiro", "utilidades domésticas criativas", "porta joias",
        "caneca criativa", "fita led quarto", "copo térmico", "organizador cozinha",
        "mop giratório", "almofada decorativa", "mini seladora"
    ],
    "utilidades_praticas": [
        "aspirador portátil", "dispenser automático", "umidificador de ar",
        "cortador multifuncional", "air fryer acessórios", "organizador multifuncional",
        "luminária sensor de presença", "difusor de aromas", "massageador elétrico",
        "mini impressora térmica", "suporte organizador"
    ],
    "eletronicos_e_gadgets": [
        "fone bluetooth", "smartwatch", "carregador turbo", "power bank",
        "lâmpada inteligente", "câmera wifi", "mini projetor portátil",
        "suporte celular articulado", "mini ventilador portátil", "tomada inteligente"
    ]
}

# --- Filtros de Qualidade ---
MIN_VENDAS = int(os.getenv("MIN_VENDAS", "100"))
MIN_COMISSAO_RS = float(os.getenv("MIN_COMISSAO_RS", "4.0"))
MIN_COMISSAO_PCT = float(os.getenv("MIN_COMISSAO_PCT", "6.0"))
NOTA_MINIMA = float(os.getenv("NOTA_MINIMA", "4.6"))
PRECO_MAXIMO = float(os.getenv("PRECO_MAXIMO", "500.0"))

NIVEIS = {
    "ouro": {"vendas": MIN_VENDAS, "comissao_rs": MIN_COMISSAO_RS, "comissao_pct": MIN_COMISSAO_PCT, "uau": 7},
    "prata": {"vendas": max(50, MIN_VENDAS // 2), "comissao_rs": max(2.0, MIN_COMISSAO_RS - 1.0), "comissao_pct": MIN_COMISSAO_PCT, "uau": 6},
}

NIVEL_ACHADO = {"vendas_min": 30, "nota": 4.8, "uau": 8, "comissao_rs": 3.0, "comissao_pct": 6.0}
ACHADOS_POR_DIA = int(os.getenv("ACHADOS_POR_DIA", "4"))
UAU_SEM_IA = 6
SIMILARIDADE_MAX = 0.55

PALAVRAS_PROIBIDAS = [
    "réplica", "replica", "vape", "cigarro", "arma", "faca tática", "sex", "erótic",
    "lingerie", "remédio", "emagrecedor", "suplemento", "maconha",
]

# --- Ritmo e Volume de Busca ---
OFERTAS_POR_GARIMPO = int(os.getenv("OFERTAS_POR_GARIMPO", "15"))
PALAVRAS_POR_GARIMPO = int(os.getenv("PALAVRAS_POR_GARIMPO", "20"))
PALAVRAS_IA_POR_GARIMPO = int(os.getenv("PALAVRAS_IA_POR_GARIMPO", "8"))
PALAVRAS_MEMORIA_POR_GARIMPO = int(os.getenv("PALAVRAS_MEMORIA_POR_GARIMPO", "4"))
PALAVRAS_VIRAIS_POR_GARIMPO = int(os.getenv("PALAVRAS_VIRAIS_POR_GARIMPO", "4"))
VIRAIS_NA_FRENTE_POR_DIA = int(os.getenv("VIRAIS_NA_FRENTE_POR_DIA", "2"))
PROFUNDIDADE = int(os.getenv("PROFUNDIDADE", "10"))

def _pags(ate, ordem, *extra, de=1):
    return tuple((p, ordem, *extra) for p in range(de, ate + 1))

PAGINAS_FIXAS = _pags(PROFUNDIDADE, 2) + _pags(3, 1) + _pags(2, 5) + _pags(3, 2, "ams")
PAGINAS_PROFUNDAS = PAGINAS_FIXAS
LOJAS_POR_GARIMPO = int(os.getenv("LOJAS_POR_GARIMPO", "3"))
PAGINAS_LOJA = int(os.getenv("PAGINAS_LOJA", "3"))
CATEGORIAS_POR_GARIMPO = int(os.getenv("CATEGORIAS_POR_GARIMPO", "4"))
PAGINAS_CATEGORIA = _pags(PROFUNDIDADE, 2, de=2) + _pags(2, 1) + _pags(2, 2, "ams")
IA_MAX_POR_GARIMPO = int(os.getenv("IA_MAX_POR_GARIMPO", "300"))
MAX_POR_LOJA_NA_FILA = int(os.getenv("MAX_POR_LOJA_NA_FILA", "4"))
DIAS_SEM_REPETIR = int(os.getenv("DIAS_SEM_REPETIR", "30"))
DIAS_SEM_REPETIR_TELEGRAM = int(os.getenv("DIAS_SEM_REPETIR_TELEGRAM", "14"))
DIAS_APAGAR_POSTS = int(os.getenv("DIAS_APAGAR_POSTS", "15"))
DIAS_VALIDADE_PENDENTE = int(os.getenv("DIAS_VALIDADE_PENDENTE", "3"))
HORAS_ENTRE_FAMILIA = int(os.getenv("HORAS_ENTRE_FAMILIA", "24"))
HORAS_ENTRE_FAMILIA_TELEGRAM = int(os.getenv("HORAS_ENTRE_FAMILIA_TELEGRAM", "12"))
PAGINAS_EM_ALTA = int(os.getenv("PAGINAS_EM_ALTA", "8"))
UAU_MINIMO_POSTAR = int(os.getenv("UAU_MINIMO_POSTAR", "6"))
MAX_PENDENTES_POR_FAMILIA = int(os.getenv("MAX_PENDENTES_POR_FAMILIA", "2"))

# --- Marcas da Awin (opcional) ---
AWIN_FEED_URL = (os.getenv("AWIN_FEED_URL") or "").strip()
AWIN_ATIVO = os.getenv("AWIN_ATIVO", "0") == "1"
AWIN_COMISSAO_PCT = float(os.getenv("AWIN_COMISSAO_PCT", "8"))
SHARK_POR_GARIMPO = int(os.getenv("SHARK_POR_GARIMPO", "2"))
SHARK_UAU = 8
SHARK_PONTOS = int(os.getenv("SHARK_PONTOS", "70"))
SHARK_POR_DIA_INSTAGRAM = int(os.getenv("SHARK_POR_DIA_INSTAGRAM", "1"))
SHARK_POR_DIA_TELEGRAM = int(os.getenv("SHARK_POR_DIA_TELEGRAM", "2"))

# --- AliExpress (opcional) ---
ALIEXPRESS_POR_DIA_INSTAGRAM = int(os.getenv("ALIEXPRESS_POR_DIA_INSTAGRAM", "1"))
ALIEXPRESS_POR_DIA_TELEGRAM = int(os.getenv("ALIEXPRESS_POR_DIA_TELEGRAM", "2"))
COMISSAO_PCT_ALIEXPRESS = 7.0

# --- Perfis da Aplicação ---
PERFIS = {
    "default": {
        "nicho": NICHOS,
        "marca": BRAND_NAME,
        "nome": BRAND_NAME,
        "arroba": BRAND_HANDLE,
        "hashtag": BRAND_HASHTAG,
        "pasta_dados": PASTA_DADOS,
        "logo": RAIZ / "assets" / "logo.png",
        "telegram": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "tom": BRAND_TONE,
        "publico": BRAND_AUDIENCE,
        "cores": {
            "fundo": os.getenv("COR_FUNDO", "#FFF8F4"),
            "escuro": os.getenv("COR_ESCURO", "#2C221E"),
            "destaque": os.getenv("COR_DESTAQUE", "#C5A880"),
            "destaque_claro": os.getenv("COR_DESTAQUE_CLARO", "#E8D8C3"),
            "preco": os.getenv("COR_PRECO", "#2C221E"),
            "cinza": os.getenv("COR_CINZA", "#7A706A"),
            "sombra": os.getenv("COR_SOMBRA", "#EFE7DF")
        },
    }
}
# Aliases para compatibilidade total
PERFIS["ba_home"] = PERFIS["default"]
PERFIS["ana"] = PERFIS["default"]
PERFIS["garimpo"] = PERFIS["default"]

PERFIL = (os.getenv("PERFIL") or "default").strip().lower()
if PERFIL not in PERFIS:
    _P = PERFIS["default"]
else:
    _P = PERFIS[PERFIL]

NICHO = _P["nicho"]
MARCA, NOME_MARCA, ARROBA, HASHTAG_MARCA = _P["marca"], _P["nome"], _P["arroba"], _P["hashtag"]

PAGINA_BIO = (os.getenv("PAGINA_BIO") or "").strip()
ARROBA_TIKTOK = (os.getenv("ARROBA_TIKTOK") or "").strip()
LEMBRETE_BIO = f"🔗 Todos os achados de hoje num lugar só: {PAGINA_BIO} (link na bio)" if PAGINA_BIO else ""
LOGO = _P["logo"]
CORES = _P["cores"]
TOM, PUBLICO = _P["tom"], _P["publico"]
TELEGRAM_ATIVO = _P["telegram"]
PALAVRAS_PROIBIDAS = PALAVRAS_PROIBIDAS + _P.get("proibidas", [])
PASTA_PERFIL = _P["pasta_dados"]
ARQ_FILA = PASTA_PERFIL / "fila.json"
ARQ_PALAVRAS = PASTA_PERFIL / "palavras.json"

VALE_A_PENA_ATIVO = os.getenv("VALE_A_PENA_ATIVO", "0") == "1"
RAIO_X_ATIVO = os.getenv("RAIO_X_ATIVO", "0") == "1"
