"""Servidor Webhook para resposta instantânea no Instagram (Meta Graph API).
Responde no Direct em 1 a 3 segundos assim que o seguidor comenta 'QUERO'.

Para rodar localmente ou no Render:
  python -m src.webhook
"""
import html
import json
import os
import sys
import threading
import time
import requests
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

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

        # Inscreve nos campos permitidos pela Meta (feed = comentários/posts, messages = DMs)
        r_sub = requests.post(f"{instagram.API}/{page_id}/subscribed_apps",
                              params={"subscribed_fields": "feed,messages"},
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
@app.get("/webhook")
def verificar_webhook(request: Request):
    """Handshake de verificação da Meta ao cadastrar a URL do Webhook (aceita na raiz e em /webhook)."""
    params = request.query_params
    mode = params.get("hub.mode") or params.get("hub_mode")
    token = params.get("hub.verify_token") or params.get("hub_verify_token")
    challenge = params.get("hub.challenge") or params.get("hub_challenge")

    # Se a Meta estiver validando a assinatura do webhook:
    if challenge:
        token_esperado = os.getenv("WEBHOOK_VERIFY_TOKEN", VERIFY_TOKEN_PADRAO)
        if mode == "subscribe" and token == token_esperado:
            log_debug(f"✅ Webhook verificado com sucesso pela Meta! Challenge: {challenge}")
            return Response(content=str(challenge), media_type="text/plain")
        log_debug(f"::warning::Falha na verificação do webhook: token='{token}' esperado='{token_esperado}'")
        return Response(content="Forbidden", status_code=403)

    # Se for acesso normal de conferência no navegador:
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


@app.get("/checar")
def rota_checar():
    """Força uma verificação manual imediata de comentários recentes."""
    if not instagram.tem_token():
        return {"status": "erro", "motivo": "IG_ACCESS_TOKEN não configurado"}
    try:
        os.environ["RESPOSTA_ESPERA_MAX_S"] = "0"
        responder.ESPERA_MAX_S = 0
        n = responder.responder()
        return {"status": "sucesso", "links_enviados": n, "ultimos_logs": ULTIMOS_LOGS[-10:]}
    except Exception as e:
        return {"status": "erro", "erro": str(e)}


MONITOR_ATIVO = True
INTERVALO_MONITOR_S = int(os.getenv("INTERVALO_MONITOR_S", "25"))


def monitor_loop():
    time.sleep(10)  # Aguarda startup do servidor
    log_debug(f"🚀 Monitor contínuo iniciado! Verificando comentários a cada {INTERVALO_MONITOR_S}s...")
    ciclos = 0
    while MONITOR_ATIVO:
        try:
            ciclos += 1
            if instagram.tem_token():
                os.environ["RESPOSTA_ESPERA_MAX_S"] = "0"
                responder.ESPERA_MAX_S = 0
                n = responder.responder()
                if n and n > 0:
                    log_debug(f"⚡ Monitor contínuo: {n} link(s) enviado(s) no direct com sucesso!")
                elif ciclos % 6 == 0:
                    log_debug(f"💓 Monitor contínuo ativo (ciclo #{ciclos}). Aguardando novos comentários...")
        except Exception as e:
            log_debug(f"Aviso no monitor contínuo: {e}")
        time.sleep(INTERVALO_MONITOR_S)


# Inicia o monitor em segundo plano 24/7
threading.Thread(target=monitor_loop, daemon=True).start()


@app.post("/")
@app.post("/webhook")
async def receber_evento_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recebe as notificações de comentários e mensagens em tempo real da Meta (aceita na raiz e em /webhook)."""
    try:
        dados = await request.json()
    except Exception as e:
        log_debug(f"Erro ao ler JSON recebido: {e}")
        return JSONResponse(status_code=400, content={"error": f"JSON inválido: {e}"})

    obj = dados.get("object")
    log_debug(f"📩 Webhook POST recebido! Objeto: {obj} - Payload: {json.dumps(dados, ensure_ascii=False)[:300]}")

    if obj not in ("instagram", "page"):
        return Response(content="EVENT_RECEIVED", status_code=200)

    for entry in dados.get("entry", []):
        for change in entry.get("changes", []):
            field = change.get("field")
            value = change.get("value", {})
            if field in ("comments", "feed"):
                background_tasks.add_task(responder_comentario_tempo_real, value)

    return Response(content="EVENT_RECEIVED", status_code=200)


@app.get("/privacidade", response_class=HTMLResponse)
@app.get("/privacy", response_class=HTMLResponse)
def pagina_privacidade():
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Política de Privacidade - BA Home & Living</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 20px; color: #2C221E; background: #FAF7F2; }
        h1, h2 { color: #2C221E; }
        .card { background: white; border-radius: 12px; padding: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        .footer { margin-top: 30px; font-size: 0.9em; color: #888; border-top: 1px solid #eee; padding-top: 15px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Política de Privacidade — BA Home & Living</h1>
        <p><strong>Última atualização:</strong> Novembro de 2026</p>
        <p>A <strong>BA Home & Living</strong> (@ba.homeliving) valoriza e respeita a privacidade de todos os seus seguidores e clientes. Esta política descreve como utilizamos as informações nas interações automatizadas do Instagram.</p>
        
        <h2>1. Finalidade do Aplicativo</h2>
        <p>Nosso aplicativo integrado à Meta Graph API realiza a leitura exclusiva de interações públicas (comentários em publicações e mensagens diretas) para o envio imediato e automatizado de links diretos de ofertas de produtos solicitados voluntariamente pelo usuário (ex.: comentários contendo termos como "QUERO" ou pedidos de links).</p>
        
        <h2>2. Não Armazenamento de Dados Pessoais Sensíveis</h2>
        <p>Não coletamos, não vendemos e não repassamos informações pessoais identificáveis a terceiros. Os identificadores de comentários são utilizados unicamente para confirmar a entrega do link solicitado.</p>
        
        <h2>3. Exclusão de Dados</h2>
        <p>A qualquer momento, o usuário pode solicitar a remoção ou revogação de dados de interação entrando em contato direto através da nossa conta oficial no Instagram <strong>@ba.homeliving</strong>.</p>
        
        <h2>4. Contato</h2>
        <p>Em caso de dúvidas sobre nossos termos ou privacidade, entre em contato via Direct: <strong>@ba.homeliving</strong>.</p>
        
        <div class="footer">
            &copy; 2026 BA Home & Living. Todos os direitos reservados.
        </div>
    </div>
</body>
</html>"""


@app.get("/termos", response_class=HTMLResponse)
@app.get("/terms", response_class=HTMLResponse)
def pagina_termos():
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Termos de Serviço - BA Home & Living</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 20px; color: #2C221E; background: #FAF7F2; }
        .card { background: white; border-radius: 12px; padding: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    </style>
</head>
<body>
    <div class="card">
        <h1>Termos de Serviço — BA Home & Living</h1>
        <p>Ao interagir com as publicações da <strong>@ba.homeliving</strong> no Instagram, o usuário concorda em receber mensagens diretas contendo links informativos e de afiliados dos produtos apresentados.</p>
        <p>Os preços e estoques dos produtos divulgados são de responsabilidade das lojas parceiras e podem sofrer alterações a qualquer momento.</p>
    </div>
</body>
</html>"""


@app.get("/exclusao", response_class=HTMLResponse)
def pagina_exclusao():
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Instruções de Exclusão de Dados - BA Home & Living</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 20px; }
    </style>
</head>
<body>
    <h1>Instruções para Exclusão de Dados de Usuário</h1>
    <p>Conforme as diretrizes da Meta Platform, você pode solicitar a exclusão de qualquer dado de interação associado à sua conta:</p>
    <ol>
        <li>Acesse o Instagram e abra uma conversa com <strong>@ba.homeliving</strong>.</li>
        <li>Envie uma mensagem solicitando a exclusão dos dados de interação.</li>
        <li>Nossa equipe processará a solicitação e confirmará a remoção em até 48 horas.</li>
    </ol>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    porta = int(os.getenv("PORT", "8000"))
    print(f"🚀 Iniciando Webhook do Instagram na porta {porta}...")
    uvicorn.run("src.webhook:app", host="0.0.0.0", port=porta, reload=False)
