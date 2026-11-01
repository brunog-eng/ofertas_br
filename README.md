# 🛍️ Ofertas BR — Automação de Achados e Afiliados

Sistema 100% automatizado no **GitHub Actions** para garimpo de ofertas de alta conversão (Shopee, AliExpress e marcas oficiais), geração de carrosséis visuais profissionais para o Instagram e envio automático de links de afiliados via Direct Message (DM).

---

## 🚀 Principais Recursos

- **🛍️ Carrossel de Achados:** Gera carrosséis no formato 1080x1350 com capa destacada, selos de desconto, avaliação e chamada para ação (CTA).
- **🤖 Respostas Automáticas no Direct:** Quando alguém comenta `QUERO`, `QUERO 1`, `QUERO 2` ou pede o link, o robô envia o link de afiliado diretamente no Direct da pessoa e confirma com um comentário público.
- **🔍 Garimpo Inteligente:** Busca os produtos mais vendidos, filtra por avaliação (≥ 4.7), volume de vendas e comissão, evitando repetições.
- **⚙️ 100% Escalável e Personalizável:** Totalmente desacoplado de personagens ou contas fixas. Configure qualquer marca ou nicho via variáveis de ambiente.

---

## 🎨 Identidade e Marca Padrão

Por padrão, o projeto vem configurado para a marca **BA Home & Living**:

| Configuração | Padrão | Variável de Ambiente |
|---|---|---|
| Nome da Marca | **BA Home & Living** | `NOME_MARCA` |
| Arroba / Perfil | **@ba.homeliving** | `ARROBA` |
| Hashtag Oficial | `#BAHomeLiving` | `HASHTAG_MARCA` |
| Nicho Principal | Casa, Decoração, Cozinha e Utilidades | `NICHO` |
| ID Instagram Graph | `17841432150685143` | `IG_USER_ID` |

Para personalizar para outra marca ou nicho, basta definir essas variáveis em **Settings → Secrets and variables → Actions → Variables**.

---

## 📦 Workflows Principais (GitHub Actions)

| Workflow | Descrição | Frequência |
|---|---|---|
| **0 - Agenda (Orquestrador)** | Relógio mestre que dispara o garimpo, publicações e respostas nos horários ideais | A cada 30 minutos |
| **Carrossel de Achados** | Seleciona os melhores produtos da fila, gera as artes e publica no feed do Instagram | 09:30 e 18:45 |
| **Garimpo de ofertas** | Busca produtos com alta comissão e avaliações e alimenta a fila | 06:45, 11:45 e 17:45 |
| **Responder Comentários e Direct** | Monitora os comentários dos posts recentes e envia o link no direct | A cada 15-30 min |
| **Renovar token** | Mantém as credenciais de acesso do Instagram válidas | Toda segunda-feira |

---

## 🔑 Configuração de Segredos (GitHub Secrets)

Acesse o repositório no GitHub em:
**Settings → Secrets and variables → Actions → Secrets** e configure:

### 1. Instagram Graph API
- `IG_ACCESS_TOKEN`: Token de acesso de longa duração gerado no Meta for Developers.
- `IG_USER_ID`: ID da sua Conta Comercial do Instagram (ex.: `17841432150685143`).

### 2. Shopee Afiliados
- `SHOPEE_APP_ID`: App ID da API de Afiliados da Shopee.
- `SHOPEE_APP_SECRET`: Secret da API de Afiliados da Shopee.

### 3. Opcionais
- `GROQ_API_KEY`: API Key da Groq para aprimoramento de legendas por IA.
- `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET`, `ALIEXPRESS_TRACKING_ID`: Afiliados AliExpress.
- `AWIN_FEED_URL`: Feed de produtos de marcas oficiais da rede Awin.
- `FB_PAGE_ID`, `FB_PAGE_TOKEN`: Para espelhamento opcional em Página do Facebook.

---

## ⚙️ Estrutura do Código

```text
ofertas_br/
├── .github/workflows/    # Workflows automatizados do GitHub Actions
├── assets/
│   ├── fontes/           # Fontes tipográficas (Poppins, Montserrat)
│   ├── marcas/           # Logos e selos de lojas oficiais
│   └── paginas/          # Templates web para GitHub Pages
├── data/
│   ├── fila.json         # Fila de ofertas ativas
│   ├── top.json          # Registro de carrosséis publicados
│   └── respondidos.json  # Histórico de comentários respondidos
├── src/
│   ├── config.py         # Configuração central e dinâmica por marca
│   ├── instagram.py      # Cliente Meta Graph API v23.0
│   ├── achados.py        # Preparação e publicação de carrosséis
│   ├── achados_artes.py  # Renderização dos slides e cards
│   ├── responder.py      # Motor de respostas automáticas no Direct
│   └── garimpar.py       # Scraper e filtros da Shopee/AliExpress
└── requirements.txt      # Dependências Python
```

---

## 🛠️ Execução Local

```bash
# Instale as dependências
pip install -r requirements.txt

# Garimpar ofertas
python -m src.garimpar

# Gerar prévia do carrossel
python -m src.achados previa

# Responder comentários pendentes
python -m src.responder
```
