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


def agora():
    return datetime.now(BRT)


def _marcar_respondido(cid: str):
    CACHE_RESPONDIDOS[cid] = time.time()
    if len(CACHE_RESPONDIDOS) > MAX_CACHE:
        CACHE_RESPONDIDOS.popitem(last=False)


def _ja_respondido(cid: str) -> bool:
    if cid in CACHE_RESPONDIDOS:
        return True
    # Confere também no arquivo persistido
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
            print(f"Aviso ao ler top.json: {e}")
    return {}


def carregar_fila():
    if config.ARQ_FILA.exists():
        try:
            return json.loads(config.ARQ_FILA.read_text(encoding="utf-8")).get("ofertas", {})
        except Exception as e:
            print(f"Aviso ao ler fila.json: {e}")
    return {}


def salvar_registro_respondido(cid: str, reg: dict):
    try:
        arq = config.PASTA_PERFIL / "respondidos.json"
        dados = {}
        if arq.exists():
            dados = json.loads(arq.read_text(encoding="utf-8"))
        dados[cid] = reg
        # Mantém histórico limpo (últimos 30 dias)
        arq.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"::warning::Erro ao salvar respondidos.json: {e}")


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

        if not cid or not texto:
            return

        if not instagram.tem_token():
            print("::warning::IG_ACCESS_TOKEN não configurado — impossível responder comentário.")
            return

        # Evita responder a si mesmo
        minha = instagram.conferir_conta()
        if autor_id == str(minha.get("user_id")) or username.lower() == str(minha.get("username", "")).lower():
            return

        # Evita duplicidade
        if _ja_respondido(cid):
            print(f"⏩ Comentário {cid} de @{username} já foi respondido anteriormente.")
            return

        # Confere se pediu link
        tops = carregar_tops()
        info_top = tops.get(media_id)
        itens_top = info_top.get("itens", []) if info_top else []

        num_pedido = responder.numero_pedido(texto, len(itens_top)) if itens_top else None
        if not num_pedido and not responder.pediu_link(texto) and not responder.so_pediu_link(texto):
            print(f"💬 Comentário ignorado (não pediu link): '{texto}' por @{username}")
            return

        print(f"\n⚡ [TEMPO REAL] Pedido detectado no post {media_id} por @{username}: '{texto}'")
        _marcar_respondido(cid)

        reg = {
            "post": media_id,
            "usuario": username,
            "autor": autor_id,
            "em": agora().strftime(FMT),
            "origem": "webhook_instantaneo"
        }

        # 1. Tenta encontrar no Carrossel / Top
        dm_enviada = False
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
                print(f"💌 Link do produto enviado com sucesso no Direct para @{username}!")
            except Exception as e:
                reg["dm"] = f"erro: {e}"
                print(f"::warning::Erro ao enviar DM do carrossel para @{username}: {e}")

        # 2. Se não era carrossel, busca em data/fila.json
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
                            print(f"Cartão recusado, tentando botão: {e}")
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
                    print(f"💌 Link enviado no direct de @{username}!")
                except Exception as e:
                    reg["dm"] = f"erro: {e}"
                    print(f"::warning::Erro ao responder post único: {e}")

        # 3. Curtir comentário
        if dm_enviada:
            try:
                instagram.curtir_comentario(cid, minha.get("user_id"))
                reg["curtida"] = "ok"
                print(f"❤️ Comentário de @{username} curtido!")
            except Exception as e:
                print(f"Aviso ao curtir comentário: {e}")

        # 4. Resposta pública no comentário
        if dm_enviada and responder.RESPOSTA_PUBLICA:
            try:
                msg_pub = responder._publica(username)
                instagram.responder_comentario(cid, msg_pub)
                reg["publica"] = "ok"
                print(f"💬 Resposta pública enviada no comentário de @{username}.")
            except Exception as e:
                print(f"Aviso ao responder publicamente: {e}")

        salvar_registro_respondido(cid, reg)
    except Exception as e:
        print(f"::error::Erro inesperado ao processar comentário no webhook: {e}")


@app.get("/")
def raiz():
    return {
        "status": "online",
        "marca": config.NOME_MARCA,
        "arroba": config.ARROBA,
        "servico": "Meta Webhook Instantâneo para Instagram"
    }


@app.get("/webhook")
def verificar_webhook(request: Request):
    """Handshake de verificação da Meta ao cadastrar a URL do Webhook."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    token_esperado = os.getenv("WEBHOOK_VERIFY_TOKEN", VERIFY_TOKEN_PADRAO)

    if mode == "subscribe" and token == token_esperado:
        print(f"✅ Webhook verificado com sucesso pela Meta! Challenge: {challenge}")
        return Response(content=str(challenge), media_type="text/plain")

    print(f"::warning::Falha na verificação do webhook: token='{token}' esperado='{token_esperado}'")
    return Response(content="Forbidden", status_code=403)


@app.post("/webhook")
async def receber_evento_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recebe as notificações de comentários e mensagens em tempo real da Meta."""
    try:
        dados = await request.json()
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"JSON inválido: {e}"})

    obj = dados.get("object")
    if obj != "instagram":
        return Response(content="EVENT_RECEIVED", status_code=200)

    for entry in dados.get("entry", []):
        for change in entry.get("changes", []):
            field = change.get("field")
            value = change.get("value", {})
            if field == "comments":
                # Processa em background para responder à Meta em < 50ms
                background_tasks.add_task(responder_comentario_tempo_real, value)

    return Response(content="EVENT_RECEIVED", status_code=200)


if __name__ == "__main__":
    import uvicorn
    porta = int(os.getenv("PORT", "8000"))
    print(f"🚀 Iniciando Webhook do Instagram na porta {porta}...")
    uvicorn.run("src.webhook:app", host="0.0.0.0", port=porta, reload=False)
