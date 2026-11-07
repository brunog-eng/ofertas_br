"""Integração com Evolution API v2 para postagem automática em Grupos do WhatsApp.
Envia foto com legenda formatada e link direto de afiliado.
"""
import base64
import json
import os
import sys
import time
import requests
from pathlib import Path
from . import config, marcas

EVOLUTION_API_URL = (os.getenv("EVOLUTION_API_URL") or "").rstrip("/")
EVOLUTION_API_KEY = (os.getenv("EVOLUTION_API_KEY") or "").strip()
EVOLUTION_INSTANCE = (os.getenv("EVOLUTION_INSTANCE") or "bahome").strip()
WHATSAPP_GRUPO_JID = (os.getenv("WHATSAPP_GRUPO_JID") or "").strip()


def configurado() -> bool:
    """Verifica se as variáveis essenciais estão presentes."""
    return bool(EVOLUTION_API_URL and EVOLUTION_API_KEY and WHATSAPP_GRUPO_JID)


def texto_grupo(oferta: dict) -> str:
    """Gera o texto com formatação nativa do WhatsApp (*negrito*, ~riscado~, _itálico_)."""
    titulo = oferta.get("titulo") or oferta.get("nome") or "Oferta Imperdível"
    preco_fmt = oferta.get("preco_fmt") or "0,00"
    link = oferta.get("link_afiliado") or ""

    linhas = [f"✨ *{titulo}*", ""]

    # Preço e Desconto
    if oferta.get("preco_de") and oferta.get("desconto"):
        preco_de_fmt = f"{oferta['preco_de']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        linhas.append(f"💰 De ~R$ {preco_de_fmt}~ por *R$ {preco_fmt}* (-{oferta['desconto']}%)")
    else:
        linhas.append(f"💰 Por apenas *R$ {preco_fmt}*")

    # Prova Social / Avaliação
    if marcas.eh_marca(oferta):
        linhas.append(f"🏬 {marcas.texto_oficial(oferta)}")
    else:
        nota = str(oferta.get("nota", "4.8")).replace(".", ",")
        vendas = f"{oferta.get('vendas', 0):,}".replace(",", ".")
        linhas.append(f"⭐ Nota {nota} • {vendas}+ vendidos")

    linhas += [
        "",
        "🛒 *Compre com desconto direto aqui:*",
        f"👉 {link}",
        "",
        f"Obrigado por apoiar a {config.NOME_MARCA}! ✨"
    ]
    return "\n".join(linhas)


def _headers() -> dict:
    return {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }


def enviar_oferta(oferta: dict, foto_path_ou_url=None, grupo_jid: str = None) -> bool:
    """Envia uma oferta completa (imagem + legenda + link direto) para o grupo."""
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        print("⏸️  Evolution API não configurada (EVOLUTION_API_URL / EVOLUTION_API_KEY ausentes).")
        return False

    jid = grupo_jid or WHATSAPP_GRUPO_JID
    if not jid:
        print("⏸️  ID do Grupo do WhatsApp ausente (WHATSAPP_GRUPO_JID).")
        return False

    # Garante que o JID do grupo termine com @g.us se não especificado
    if "@" not in jid:
        jid = f"{jid}@g.us"

    legenda = texto_grupo(oferta)
    media_url = None
    media_base64 = None

    if foto_path_ou_url:
        p = Path(foto_path_ou_url)
        if p.exists():
            media_base64 = base64.b64encode(p.read_bytes()).decode("utf-8")
        elif str(foto_path_ou_url).startswith("http"):
            media_url = foto_path_ou_url

    if not media_url and not media_base64:
        media_url = oferta.get("imagem")

    url = f"{EVOLUTION_API_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
    payload = {
        "number": jid,
        "mediaMessage": {
            "mediatype": "image",
            "caption": legenda,
            "media": media_base64 if media_base64 else media_url
        }
    }

    try:
        resp = requests.post(url, headers=_headers(), json=payload, timeout=30)
        if resp.status_code in (200, 201):
            print(f"✅ Oferta enviada para o grupo do WhatsApp ({jid}): {oferta.get('titulo')}")
            return True
        else:
            print(f"::warning::Erro ao enviar para o WhatsApp ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"::warning::Falha na requisição para Evolution API: {e}")
        return False


def listar_grupos():
    """Auxiliar: Lista todos os grupos onde o número conectado está presente."""
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        raise RuntimeError("Defina EVOLUTION_API_URL e EVOLUTION_API_KEY para listar grupos.")

    url = f"{EVOLUTION_API_URL}/group/fetchAllGroups/{EVOLUTION_INSTANCE}?getParticipants=false"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    grupos = resp.json()
    return grupos


if __name__ == "__main__":
    if "--listar-grupos" in sys.argv:
        print(f"🔍 Conectando na Evolution API ({EVOLUTION_API_URL}) para listar grupos da instância '{EVOLUTION_INSTANCE}'...")
        try:
            grs = listar_grupos()
            print(f"📋 Encontrados {len(grs)} grupos:")
            for g in grs:
                nome = g.get("subject") or g.get("name") or "Sem nome"
                jid = g.get("id") or g.get("jid")
                print(f"   • {nome} -> ID: {jid}")
        except Exception as err:
            print(f"❌ Erro ao listar grupos: {err}")
    elif "--testar" in sys.argv:
        fila_path = config.RAIZ / "data" / "fila.json"
        if fila_path.exists():
            fila = json.loads(fila_path.read_text(encoding="utf-8"))
            for o in fila.get("ofertas", {}).values():
                if o.get("titulo"):
                    print(f"🧪 Enviando oferta de teste: {o['titulo']}")
                    enviar_oferta(o)
                    break
        else:
            print("Arquivo data/fila.json não encontrado.")
