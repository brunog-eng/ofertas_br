"""Cliente da API do Instagram (login Graph API v23.0)."""
import os
import time

import requests

VERSAO = os.getenv("IG_API_VERSION", "v23.0")
API_HOST = os.getenv("IG_API_HOST", "graph.facebook.com").strip()
API = f"https://{API_HOST}/{VERSAO}"

_INFO_PAGINA = None


class ErroInstagram(RuntimeError):
    pass


def _nome_token():
    """Identifica o nome da variável de ambiente com o token."""
    if os.getenv("IG_ACCESS_TOKEN"):
        return "IG_ACCESS_TOKEN"
    if os.getenv("IG_ACCESS_TOKEN_ANA"):
        return "IG_ACCESS_TOKEN_ANA"
    if os.getenv("INSTAGRAM_TOKEN"):
        return "INSTAGRAM_TOKEN"
    return "IG_ACCESS_TOKEN"


def token():
    t = (os.getenv("IG_ACCESS_TOKEN") or os.getenv("IG_ACCESS_TOKEN_ANA") or os.getenv("INSTAGRAM_TOKEN") or "").strip()
    if not t:
        raise ErroInstagram("Segredo de acesso do Instagram (IG_ACCESS_TOKEN) não configurado.")
    return t


def tem_token():
    return bool((os.getenv("IG_ACCESS_TOKEN") or os.getenv("IG_ACCESS_TOKEN_ANA") or os.getenv("INSTAGRAM_TOKEN") or "").strip())


def conferir_conta():
    """Trava de segurança: confere se o token pertence à conta configurada."""
    from . import config
    c = conta()
    esperado = (config.ARROBA or "").lstrip("@").strip().lower()
    atual = (c.get("username") or "").strip().lower()
    if esperado and atual and atual != esperado:
        raise ErroInstagram(f"Token é da conta @{atual}, mas a marca configurada é @{esperado}. Nada foi publicado.")
    return c


def obter_info_pagina(ig_id=None):
    """Busca a página do Facebook conectada e o Page Access Token necessário para /messages."""
    global _INFO_PAGINA
    if _INFO_PAGINA is not None:
        return _INFO_PAGINA
    t = token()
    _INFO_PAGINA = {"page_id": None, "page_token": t}
    try:
        r = requests.get(f"{API}/me/accounts", params={"fields": "id,name,access_token,instagram_business_account"},
                         headers={"Authorization": f"Bearer {t}"}, timeout=15)
        corpo = r.json()
        for p in corpo.get("data", []):
            ig_conta = (p.get("instagram_business_account") or {}).get("id")
            if (ig_id and str(ig_conta) == str(ig_id)) or p.get("access_token"):
                _INFO_PAGINA["page_id"] = p.get("id")
                _INFO_PAGINA["page_token"] = p.get("access_token")
                print(f"📄 Página vinculada identificada: {p.get('name')} (ID: {p.get('id')})")
                break
    except Exception as e:
        print(f"ℹ️ /me/accounts: {e}")
    return _INFO_PAGINA


def _req(metodo, caminho, params=None, json=None, url=None, custom_token=None):
    tok = custom_token or token()
    r = requests.request(metodo, url or f"{API}/{caminho}", params=params, json=json, timeout=60,
                         headers={"Authorization": f"Bearer {tok}"})
    try:
        corpo = r.json()
    except ValueError:
        raise ErroInstagram(f"HTTP {r.status_code}: {r.text[:300]}")
    if r.status_code >= 400 or "error" in corpo:
        erro = corpo.get("error", corpo)
        msg = erro.get("message", erro) if isinstance(erro, dict) else str(erro)
        code = erro.get("code") if isinstance(erro, dict) else None
        subcode = erro.get("error_subcode") if isinstance(erro, dict) else None
        raise ErroInstagram(f"HTTP {r.status_code}: {msg} (code {code}, subcode {subcode})")
    return corpo


def conta():
    """Retorna {'user_id': id da conta profissional, 'username': ...}."""
    ig_id = (os.getenv("IG_USER_ID") or "17841432150685143").strip()
    c = _req("GET", ig_id, params={"fields": "id,username"})
    c["user_id"] = str(c.get("id") or ig_id)
    return c


def criar_container(ig_id, legenda, imagem_url=None, video_url=None):
    if video_url:
        params = {"media_type": "REELS", "video_url": video_url, "caption": legenda,
                  "share_to_feed": "true"}
    else:
        params = {"image_url": imagem_url, "caption": legenda}
    return _req("POST", f"{ig_id}/media", params=params)["id"]


def criar_item_carrossel(ig_id, imagem_url=None, video_url=None):
    params = {"is_carousel_item": "true"}
    params.update({"media_type": "VIDEO", "video_url": video_url} if video_url else {"image_url": imagem_url})
    return _req("POST", f"{ig_id}/media", params=params)["id"]


def criar_carrossel(ig_id, filhos, legenda):
    return _req("POST", f"{ig_id}/media", params={"media_type": "CAROUSEL", "children": ",".join(filhos),
                                                   "caption": legenda})["id"]


def criar_story(ig_id, imagem_url=None, video_url=None):
    """Story (some em 24h). A API não permite adesivo de link."""
    params = {"media_type": "STORIES"}
    params.update({"video_url": video_url} if video_url else {"image_url": imagem_url})
    return _req("POST", f"{ig_id}/media", params=params)["id"]


def aguardar_container(container_id, limite_s=600):
    inicio = time.time()
    while time.time() - inicio < limite_s:
        st = _req("GET", container_id, params={"fields": "status_code,status"})
        codigo = st.get("status_code")
        if codigo in ("FINISHED", "PUBLISHED"):
            return
        if codigo in ("ERROR", "EXPIRED"):
            raise ErroInstagram(f"Container {codigo}: {st.get('status')}")
        time.sleep(10)
    raise ErroInstagram("Tempo esgotado esperando o Instagram processar a mídia.")


def publicar(ig_id, container_id):
    return _req("POST", f"{ig_id}/media_publish", params={"creation_id": container_id})["id"]


def permalink(media_id):
    try:
        return _req("GET", media_id, params={"fields": "permalink"}).get("permalink", "")
    except ErroInstagram:
        return ""


def comentarios(media_id, ig_id=None):
    """Todos os comentários de um post (com paginação), tentando page_token e user_token."""
    caminho = f"{media_id}/comments"
    info = obter_info_pagina(ig_id)
    page_tok = info.get("page_token") if info else None
    tokens = list(dict.fromkeys([t for t in [page_tok, token()] if t]))

    ultimo_erro = None
    for tok in tokens:
        try:
            itens, url = [], None
            params = {"fields": "id,text,timestamp,username,from{id,username}", "limit": 50}
            while True:
                corpo = _req("GET", caminho, params=params, url=url, custom_token=tok)
                itens += corpo.get("data", [])
                url = (corpo.get("paging") or {}).get("next")
                if not url:
                    return itens
                params = None
        except Exception as e:
            ultimo_erro = e
    if ultimo_erro:
        raise ultimo_erro
    return []


def resposta_privada(ig_id, comment_id, texto):
    info = obter_info_pagina(ig_id)
    tok = info.get("page_token") or token()
    try:
        return _req("POST", f"{ig_id}/messages",
                    json={"recipient": {"comment_id": comment_id}, "message": {"text": texto}},
                    custom_token=tok)
    except Exception as e:
        if info.get("page_id") and str(info["page_id"]) != str(ig_id):
            return _req("POST", f"{info['page_id']}/messages",
                        json={"recipient": {"comment_id": comment_id}, "message": {"text": texto}},
                        custom_token=tok)
        raise e


def resposta_privada_botao(ig_id, comment_id, texto, url, titulo_botao):
    """Resposta privada com botão clicável (template de botão)."""
    info = obter_info_pagina(ig_id)
    tok = info.get("page_token") or token()
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {"attachment": {"type": "template", "payload": {
            "template_type": "button", "text": texto[:640],
            "buttons": [{"type": "web_url", "url": url, "title": titulo_botao}]}}}
    }
    try:
        return _req("POST", f"{ig_id}/messages", json=payload, custom_token=tok)
    except Exception as e:
        if info.get("page_id") and str(info["page_id"]) != str(ig_id):
            return _req("POST", f"{info['page_id']}/messages", json=payload, custom_token=tok)
        raise e


def resposta_privada_cartao(ig_id, comment_id, titulo, subtitulo, imagem_url, botoes):
    """Resposta privada em cartão (template genérico): foto do produto, nome, uma linha e até 3 botões."""
    info = obter_info_pagina(ig_id)
    tok = info.get("page_token") or token()
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {"attachment": {"type": "template", "payload": {
            "template_type": "generic", "elements": [{
                "title": titulo[:80], "subtitle": subtitulo[:80], "image_url": imagem_url,
                "default_action": {"type": "web_url", "url": botoes[0][1]},
                "buttons": [{"type": "web_url", "url": u, "title": t[:20]} for t, u in botoes[:3]]}]}}}
    }
    try:
        return _req("POST", f"{ig_id}/messages", json=payload, custom_token=tok)
    except Exception as e:
        if info.get("page_id") and str(info["page_id"]) != str(ig_id):
            return _req("POST", f"{info['page_id']}/messages", json=payload, custom_token=tok)
        raise e


def comentar(media_id, texto):
    """Comentário da própria conta num post (devolve o id do comentário)."""
    return _req("POST", f"{media_id}/comments", params={"message": texto}).get("id")


def responder_comentario(comment_id, texto):
    return _req("POST", f"{comment_id}/replies", params={"message": texto})




def enviar_dm_cartao(ig_id, destinatario_id, titulo, subtitulo, imagem_url, botoes):
    """Envia um cartão com foto, título, subtítulo e botões para um usuário no Direct."""
    info = obter_info_pagina(ig_id)
    tok = info.get("page_token") or token()
    payload = {
        "recipient": {"id": destinatario_id},
        "message": {"attachment": {"type": "template", "payload": {
            "template_type": "generic", "elements": [{
                "title": titulo[:80], "subtitle": subtitulo[:80], "image_url": imagem_url,
                "default_action": {"type": "web_url", "url": botoes[0][1]},
                "buttons": [{"type": "web_url", "url": u, "title": t[:20]} for t, u in botoes[:3]]}]}}}
    }
    try:
        return _req("POST", f"{ig_id}/messages", json=payload, custom_token=tok)
    except Exception as e:
        if info.get("page_id") and str(info["page_id"]) != str(ig_id):
            return _req("POST", f"{info['page_id']}/messages", json=payload, custom_token=tok)
        raise e


def enviar_dm_botao(ig_id, destinatario_id, texto, url, titulo_botao):
    """Envia uma mensagem com botão clicável para um usuário no Direct."""
    info = obter_info_pagina(ig_id)
    tok = info.get("page_token") or token()
    payload = {
        "recipient": {"id": destinatario_id},
        "message": {"attachment": {"type": "template", "payload": {
            "template_type": "button", "text": texto[:640],
            "buttons": [{"type": "web_url", "url": url, "title": titulo_botao}]}}}
    }
    try:
        return _req("POST", f"{ig_id}/messages", json=payload, custom_token=tok)
    except Exception as e:
        if info.get("page_id") and str(info["page_id"]) != str(ig_id):
            return _req("POST", f"{info['page_id']}/messages", json=payload, custom_token=tok)
        raise e


def enviar_dm_texto(ig_id, destinatario_id, texto):
    """Envia uma mensagem de texto simples para um usuário no Direct."""
    info = obter_info_pagina(ig_id)
    tok = info.get("page_token") or token()
    payload = {"recipient": {"id": destinatario_id}, "message": {"text": texto}}
    try:
        return _req("POST", f"{ig_id}/messages", json=payload, custom_token=tok)
    except Exception as e:
        if info.get("page_id") and str(info["page_id"]) != str(ig_id):
            return _req("POST", f"{info['page_id']}/messages", json=payload, custom_token=tok)
        raise e


def curtir_comentario(comment_id, ig_id=None):
    """Curte um comentário no Instagram."""
    ig_id = str(ig_id or (os.getenv("IG_USER_ID") or "17841432150685143")).strip()
    info = obter_info_pagina(ig_id)
    tokens = [t for t in [info.get("page_token"), token()] if t]
    ultimo_erro = None
    for tok in tokens:
        try:
            return _req("POST", f"{ig_id}/likes", params={"comment_id": comment_id}, custom_token=tok)
        except Exception as e:
            ultimo_erro = e
            try:
                return _req("POST", f"{comment_id}/likes", custom_token=tok)
            except Exception as e2:
                ultimo_erro = e2
    if ultimo_erro:
        raise ultimo_erro


def renovar_token():
    """Renova o token de longa duração quando aplicável."""
    t = token()
    if t.startswith("EAA"):
        print("ℹ️ Token Meta EAA... (gerenciado via Meta for Developers / Graph API).")
        return t, None
    r = requests.get("https://graph.instagram.com/refresh_access_token", timeout=30,
                     params={"grant_type": "ig_refresh_token", "access_token": t})
    corpo = r.json()
    if "access_token" not in corpo:
        raise ErroInstagram(f"Falha ao renovar token: {corpo}")
    return corpo["access_token"], corpo.get("expires_in")
