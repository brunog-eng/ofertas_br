"""Servidor Webhook para resposta instantânea no Instagram (Meta Graph API).
Responde no Direct em 1 a 3 segundos assim que o seguidor comenta 'QUERO'.

Para rodar localmente ou no Render:
  python -m src.webhook
"""
import html
import json
import os
import sys
import time
import requests
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from . import config, instagram, marcas, responder, vendas

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = FastAPI(title="BA Home - Instagram Webhook", version="1.0.0")

BRT = timezone(timedelta(hours=-3))
FMT = "%Y-%m-%d %H:%M:%S"
VERIFY_TOKEN_PADRAO = "bahome_secret_token_2026"

# Cache em memória para evitar responder comentários duplicados caso a Meta reenvie o webhook
CACHE_RESPONDIDOS = OrderedDict()
MAX_CACHE = 1000

# Buffer de logs recentes para depuração em tempo real (/debug)
ULTIMOS_LOGS = []
MAX_LOGS = 50


def log_debug(msg: str):
    ts = agora().strftime("%H:%M:%S")
    linha = f"[{ts}] {msg}"
    print(linha)
    ULTIMOS_LOGS.append(linha)
    if len(ULTIMOS_LOGS) > MAX_LOGS:
        ULTIMOS_LOGS.pop(0)


def agora():
    return datetime.now(BRT)


def _marcar_respondido(cid: str):
    CACHE_RESPONDIDOS[cid] = time.time()
    if len(CACHE_RESPONDIDOS) > MAX_CACHE:
        CACHE_RESPONDIDOS.popitem(last=False)


def _ja_respondido(cid: str) -> bool:
    if cid in CACHE_RESPONDIDOS:
        return True
    try:
        arq = config.PASTA_PERFIL / "respondidos.json"
        if arq.exists():
            dados = json.loads(arq.read_text(encoding="utf-8"))
            if cid in dados:
                CACHE_RESPONDIDOS[cid] = time.time()
                return True
    except Exception:
        pass
    return False


def carregar_tops():
    arq = config.PASTA_PERFIL / "top.json"
    if arq.exists():
        try:
            return json.loads(arq.read_text(encoding="utf-8")).get("posts", {})
        except Exception as e:
            log_debug(f"Aviso ao ler top.json: {e}")
    return {}


def carregar_fila():
    if config.ARQ_FILA.exists():
        try:
            return json.loads(config.ARQ_FILA.read_text(encoding="utf-8")).get("ofertas", {})
        except Exception as e:
            log_debug(f"Aviso ao ler fila.json: {e}")
    return {}


def salvar_registro_respondido(cid: str, reg: dict):
    try:
        arq = config.PASTA_PERFIL / "respondidos.json"
        dados = {}
        if arq.exists():
            dados = json.loads(arq.read_text(encoding="utf-8"))
        dados[cid] = reg
        arq.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log_debug(f"::warning::Erro ao salvar respondidos.json: {e}")


def inscrever_pagina():
    """Inscreve a página do Facebook / Instagram no webhook do app na Meta."""
    if not instagram.tem_token():
        return "IG_ACCESS_TOKEN ausente."
    try:
        info = instagram.obter_info_pagina()
        page_id = info.get("page_id")
        page_token = info.get("page_token") or instagram.token()
        if not page_id:
            # Tenta pegar page_id via me/accounts
            r = requests.get(f"{instagram.API}/me/accounts", headers={"Authorization": f"Bearer {page_token}"}, timeout=10)
            contas = r.json().get("data", [])
            if contas:
                page_id = contas[0].get("id")
                page_token = contas[0].get("access_token") or page_token

        if not page_id:
            return "Página do Facebook não encontrada na conta."

        # Inscreve no campo feed e comments
        r_sub = requests.post(f"{instagram.API}/{page_id}/subscribed_apps",
                              params={"subscribed_fields": "feed,comments,messages"},
                              headers={"Authorization": f"Bearer {page_token}"},
                              timeout=15)
        res = r_sub.json()
        log_debug(f"Assinatura da página {page_id} no Webhook: {res}")
        return f"Página {page_id} inscrita: {res}"
    except Exception as e:
        log_debug(f"Erro ao inscrever página: {e}")
        return f"Erro: {e}"


def responder_comentario_tempo_real(val: dict):
    """Processa o comentário recebido pelo webhook e envia a DM imediatamente."""
    try:
        cid = val.get("id")
        texto = val.get("text", "").strip()
        media = val.get("media") or {}
        media_id = str(media.get("id", ""))
        autor = val.get("from") or {}
        autor_id = str(autor.get("id", ""))
        username = autor.get("username", "")

        log_debug(f"🔔 Comentário recebido: cid={cid} autor=@{username} (id={autor_id}) post={media_id} texto='{texto}'")

        if not cid or not texto:
            return

        if not instagram.tem_token():
            log_debug("::warning::IG_ACCESS_TOKEN não configurado — impossível responder.")
            return

        # Conta do robô
        minha = instagram.conferir_conta()
        meu_id = str(minha.get("user_id", ""))
        meu_user = str(minha.get("username", "")).lower()

        # Evita responder a si mesmo
        if autor_id == meu_id or (username and username.lower() == meu_user):
            log_debug(f"⏩ Comentário da própria conta (@{username}) — ignorado para não criar loop.")
            return

        # Evita duplicidade
        if _ja_respondido(cid):
            log_debug(f"⏩ Comentário {cid} de @{username} já foi respondido anteriormente.")
            return

        # Confere se pediu link
        tops = carregar_tops()
        info_top = tops.get(media_id)
        itens_top = info_top.get("itens", []) if info_top else []

        num_pedido = responder.numero_pedido(texto, len(itens_top)) if itens_top else None
        if not num_pedido and not responder.pediu_link(texto) and not responder.so_pediu_link(texto):
            log_debug(f"💬 Comentário ignorado (não pediu link): '{texto}' por @{username}")
            return

        log_debug(f"⚡ [TEMPO REAL] Pedido válido detectado no post {media_id} por @{username}: '{texto}'")
        _marcar_respondido(cid)

        reg = {
            "post": media_id,
            "usuario": username,
            "autor": autor_id,
            "em": agora().strftime(FMT),
            "origem": "webhook_instantaneo"
        }

        dm_enviada = False

        # 1. Carrossel / Top
        if info_top and itens_top:
            try:
                if num_pedido:
                    item_escolhido = itens_top[num_pedido - 1]
                    reg["oferta"] = item_escolhido.get("id")
                    reg["top"] = num_pedido
                    reg["formato"] = responder._dm_item_top(instagram, minha, cid, item_escolhido, num_pedido)
                else:
                    item_escolhido = itens_top[0]
                    reg["oferta"] = item_escolhido.get("id")
                    reg["top"] = 1
                    reg["formato"] = responder._dm_item_top(instagram, minha, cid, item_escolhido, 1)

                reg["dm"] = "ok"
                dm_enviada = True
                log_debug(f"💌 Link do carrossel enviado no Direct de @{username}!")
            except Exception as e:
                reg["dm"] = f"erro: {e}"
                log_debug(f"::warning::Erro ao enviar DM do carrossel para @{username}: {e}")

        # 2. Post único
        if not dm_enviada:
            fila = carregar_fila()
            oferta = next((o for o in fila.values() if str(o.get("id_post")) == media_id), None)
            if oferta:
                try:
                    loja = responder.NOME_LOJA.get(oferta.get("plataforma") or "shopee", "loja")
                    link_canal = vendas.do_canal(oferta, "igdm")
                    titulo = (oferta.get("titulo") or oferta.get("nome", ""))[:80]
                    botoes = [("🛒 Ver Oferta", link_canal)]
                    if config.PAGINA_BIO:
                        botoes.append(("🔗 Achados de hoje", f"https://{config.PAGINA_BIO}"))

                    if oferta.get("imagem"):
                        try:
                            instagram.resposta_privada_cartao(
                                minha["user_id"], cid, titulo,
                                f"R$ {oferta.get('preco_fmt')} ({loja}) • Aproveite a oferta!",
                                oferta["imagem"], botoes
                            )
                            reg["formato"] = "cartao"
                        except Exception as e:
                            log_debug(f"Cartão recusado, tentando botão: {e}")
                            instagram.resposta_privada_botao(
                                minha["user_id"], cid,
                                f"Olá! ✨ Aqui está o achado que você pediu: {titulo}\nToque abaixo para ver na {loja}:",
                                link_canal, "🛒 Ver Oferta"
                            )
                            reg["formato"] = "botao"
                    else:
                        instagram.resposta_privada_botao(
                            minha["user_id"], cid,
                            f"Olá! ✨ Aqui está o link da oferta: {titulo}",
                            link_canal, "🛒 Ver Oferta"
                        )
                        reg["formato"] = "botao"

                    reg["oferta"] = oferta.get("id")
                    reg["dm"] = "ok"
                    dm_enviada = True
                    log_debug(f"💌 Link enviado no direct de @{username}!")
                except Exception as e:
                    reg["dm"] = f"erro: {e}"
                    log_debug(f"::warning::Erro ao responder post único: {e}")

        # 3. Curtir comentário
        if dm_enviada:
            try:
                instagram.curtir_comentario(cid, minha.get("user_id"))
                reg["curtida"] = "ok"
                log_debug(f"❤️ Comentário de @{username} curtido!")
            except Exception as e:
                log_debug(f"Aviso ao curtir comentário: {e}")

        # 4. Resposta pública no comentário
        if dm_enviada and responder.RESPOSTA_PUBLICA:
            try:
                msg_pub = responder._publica(username)
                instagram.responder_comentario(cid, msg_pub)
                reg["publica"] = "ok"
                log_debug(f"💬 Resposta pública enviada no comentário de @{username}.")
            except Exception as e:
                log_debug(f"Aviso ao responder publicamente: {e}")

        salvar_registro_respondido(cid, reg)
    except Exception as e:
        log_debug(f"::error::Erro inesperado ao processar comentário: {e}")


@app.get("/")
def raiz():
    return {
        "status": "online",
        "marca": config.NOME_MARCA,
        "arroba": config.ARROBA,
        "token_configurado": instagram.tem_token(),
        "servico": "Meta Webhook Instantâneo para Instagram"
    }


@app.get("/debug")
def debug():
    conta_info = None
    if instagram.tem_token():
        try:
            conta_info = instagram.conferir_conta()
        except Exception as e:
            conta_info = f"Erro ao consultar conta: {e}"

    return {
        "horario_servidor": agora().strftime(FMT),
        "tem_token": instagram.tem_token(),
        "conta": conta_info,
        "cache_respondidos_total": len(CACHE_RESPONDIDOS),
        "ultimos_logs": ULTIMOS_LOGS[-30:]
    }


@app.get("/inscrever")
def rota_inscrever():
    res = inscrever_pagina()
    return {"resultado": res}


@app.get("/webhook")
def verificar_webhook(request: Request):
    """Handshake de verificação da Meta ao cadastrar a URL do Webhook."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    token_esperado = os.getenv("WEBHOOK_VERIFY_TOKEN", VERIFY_TOKEN_PADRAO)

    if mode == "subscribe" and token == token_esperado:
        log_debug(f"✅ Webhook verificado com sucesso pela Meta! Challenge: {challenge}")
        return Response(content=str(challenge), media_type="text/plain")

    log_debug(f"::warning::Falha na verificação do webhook: token='{token}' esperado='{token_esperado}'")
    return Response(content="Forbidden", status_code=403)


@app.post("/webhook")
async def receber_evento_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recebe as notificações de comentários e mensagens em tempo real da Meta."""
    try:
        dados = await request.json()
    except Exception as e:
        log_debug(f"Erro ao ler JSON recebido: {e}")
        return JSONResponse(status_code=400, content={"error": f"JSON inválido: {e}"})

    obj = dados.get("object")
    log_debug(f"📩 Webhook POST recebido! Objeto: {obj} - Chaves: {list(dados.keys())}")

    if obj not in ("instagram", "page"):
        return Response(content="EVENT_RECEIVED", status_code=200)

    for entry in dados.get("entry", []):
        for change in entry.get("changes", []):
            field = change.get("field")
            value = change.get("value", {})
            if field in ("comments", "feed"):
                background_tasks.add_task(responder_comentario_tempo_real, value)

    return Response(content="EVENT_RECEIVED", status_code=200)


if __name__ == "__main__":
    import uvicorn
    porta = int(os.getenv("PORT", "8000"))
    print(f"🚀 Iniciando Webhook do Instagram na porta {porta}...")
    uvicorn.run("src.webhook:app", host="0.0.0.0", port=porta, reload=False)
