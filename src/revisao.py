"""Revisão semanal do robô (toda semana): confere tudo o que aconteceu na semana e envia
o balanço completo no Telegram do administrador (segredo TELEGRAM_CHAT_PRIVADO).

Métricas analisadas nos últimos 7 dias:
  1. Quantas postagens fez: Carrosséis no feed, Stories publicados e ofertas no grupo do WhatsApp.
  2. Quantas pessoas pediram link: Total de comentários/DMs atendidos pelo robô e pessoas únicas.
  3. Top produtos mais pedidos na semana.
  4. Saúde do sistema e erros: Análise das execuções e falhas dos workflows no GitHub Actions.
  5. Status da fila: Quantidade de ofertas prontas aguardando publicação.

Teste local: python -m src.revisao
"""
import compileall
import html
import io
import json
import os
import sys
import contextlib
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests

from . import config, telegram

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DIAS = 7
BRT = timezone(timedelta(hours=-3))
ARQ_TOP = config.PASTA_PERFIL / "top.json"

# Workflows principais de produção do robô
PRODUCAO = {
    "achados.yml": "Carrossel Instagram",
    "whatsapp.yml": "Postagens WhatsApp (2 em 2h)",
    "garimpo.yml": "Garimpo Shopee",
    "responder.yml": "Robô do Direct",
    "token.yml": "Renovação Token IG",
    "revisao.yml": "Balanço Semanal",
}


def _gh(caminho, params=None):
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GH_TOKEN") or os.getenv("GH_PAT")
    if not repo or not token:
        return {}
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}/{caminho}",
                         params=params, timeout=60,
                         headers={"Authorization": f"Bearer {token}",
                                  "Accept": "application/vnd.github+json"})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Aviso na API do GitHub ({caminho}): {e}")
        return {}


def checar_workflows():
    """Consulta as execuções dos workflows de produção dos últimos 7 dias."""
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GH_TOKEN") or os.getenv("GH_PAT")
    if not repo or not token:
        return [], [], 0, 0, "⚠️ Informações do GitHub indisponíveis localmente."

    corte = datetime.now(timezone.utc) - timedelta(days=DIAS)
    por_wf = {}
    for arq, nome in PRODUCAO.items():
        runs, pagina = [], 1
        while pagina <= 15:
            lote = _gh(f"actions/workflows/{arq}/runs", {"per_page": 100, "page": pagina}).get("workflow_runs", [])
            runs += [r for r in lote if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= corte]
            antigas = [r for r in lote if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) < corte]
            if len(lote) < 100 or antigas:
                break
            pagina += 1
        d = {"total": len(runs), "falhas": 0, "ultima_falha": None, "ultimo_ok": None}
        for r in runs:
            if r.get("conclusion") in ("failure", "timed_out", "startup_failure"):
                d["falhas"] += 1
                d["ultima_falha"] = max(d["ultima_falha"] or "", r["created_at"])
            elif r.get("conclusion") == "success":
                d["ultimo_ok"] = max(d["ultimo_ok"] or "", r["created_at"])
        por_wf[arq] = d

    problemas, resolvidas, ok = [], [], 0
    for arq, nome in PRODUCAO.items():
        d = por_wf[arq]
        if d["total"] == 0:
            problemas.append(f"⛔ <b>{nome}</b>: não rodou na semana")
        elif d["falhas"]:
            quando = datetime.fromisoformat(d["ultima_falha"].replace("Z", "+00:00")).astimezone(BRT)
            if d["ultimo_ok"] and d["ultimo_ok"] > d["ultima_falha"]:
                ok += 1
                resolvidas.append(f"✅ <i>{nome}</i>: {d['falhas']} falha(s) anterior(es) já resolvida(s); última ok")
            else:
                problemas.append(f"❌ <b>{nome}</b>: {d['falhas']} falha(s) em {d['total']} rodadas (última {quando:%d/%m %H:%M})")
        else:
            ok += 1
    total_rodadas = sum(d["total"] for d in por_wf.values())
    return problemas, resolvidas, ok, total_rodadas, None


def obter_metricas_semana():
    """Coleta os números de postagens, pedidos de link e fila dos últimos 7 dias."""
    agora = datetime.now(BRT)
    corte = agora - timedelta(days=DIAS)
    corte_str = corte.strftime("%Y-%m-%d %H:%M:%S")

    # 1. Carrosséis em data/top.json
    carrosseis = []
    try:
        if ARQ_TOP.exists():
            dados_top = json.loads(ARQ_TOP.read_text(encoding="utf-8")).get("posts", {})
            carrosseis = [p for p in dados_top.values() if p.get("postado_em", "") >= corte_str]
    except Exception as e:
        print(f"Aviso ao ler top.json: {e}")

    total_prods_carrossel = sum(len(p.get("itens", [])) for p in carrosseis)

    # 2. Fila (Stories, WhatsApp e Pendentes)
    stories = []
    whatsapp = []
    pendentes = 0
    fila_ofertas = {}
    try:
        if config.ARQ_FILA.exists():
            fila_ofertas = json.loads(config.ARQ_FILA.read_text(encoding="utf-8")).get("ofertas", {})
            stories = [o for o in fila_ofertas.values() if o.get("story") == "ok" and o.get("postado_em", "") >= corte_str]
            whatsapp = [o for o in fila_ofertas.values() if o.get("whatsapp") == "ok" and o.get("whatsapp_em", "") >= corte_str]
            pendentes = sum(1 for o in fila_ofertas.values() if o.get("status") == "pendente")
    except Exception as e:
        print(f"Aviso ao ler fila.json: {e}")

    # 3. WhatsApp (data/fila_whatsapp.json)
    arq_zap = config.PASTA_DADOS / "fila_whatsapp.json"
    zap_postados = 0
    zap_pendentes = 0
    if arq_zap.exists():
        try:
            dados_zap = json.loads(arq_zap.read_text(encoding="utf-8")).get("ofertas", {})
            zap_postados = sum(1 for o in dados_zap.values() if o.get("status") == "postado" and o.get("postado_em", "") >= corte_str)
            zap_pendentes = sum(1 for o in dados_zap.values() if o.get("status") == "pendente")
        except Exception as e:
            print(f"Aviso ao ler fila_whatsapp.json: {e}")
    else:
        zap_postados = len(whatsapp)

    # 4. Pedidos de link em respondidos.json
    respondidos = []
    usuarios_unicos = set()
    top_pedidos = []
    try:
        arq_resp = config.PASTA_PERFIL / "respondidos.json"
        if arq_resp.exists():
            dados_resp = json.loads(arq_resp.read_text(encoding="utf-8"))
            respondidos = [r for r in dados_resp.values() if r.get("em", "") >= corte_str]
            for r in respondidos:
                u = r.get("usuario") or r.get("autor")
                if u:
                    usuarios_unicos.add(u)
            
            cont = Counter(r.get("oferta") for r in respondidos if r.get("oferta"))
            for oid, qtd in cont.most_common(3):
                nome = fila_ofertas.get(oid, {}).get("titulo") or fila_ofertas.get(oid, {}).get("nome") or oid
                top_pedidos.append((nome[:40], qtd))
    except Exception as e:
        print(f"Aviso ao ler respondidos.json: {e}")

    return {
        "inicio": corte,
        "fim": agora,
        "carrosseis": len(carrosseis),
        "produtos_carrossel": total_prods_carrossel,
        "stories": len(stories),
        "whatsapp": zap_postados,
        "whatsapp_pendentes": zap_pendentes,
        "pedidos_link": len(respondidos),
        "usuarios_unicos": len(usuarios_unicos),
        "top_pedidos": top_pedidos,
        "pendentes": pendentes,
    }


def montar_mensagem():
    m = obter_metricas_semana()
    ini_str = m["inicio"].strftime("%d/%m")
    fim_str = m["fim"].strftime("%d/%m/%Y")

    linhas = [
        f"📊 <b>Balanço Semanal — {config.NOME_MARCA}</b>",
        f"🗓️ <i>Período: {ini_str} a {fim_str}</i>",
        "",
        "✨ <b>Postagens Realizadas:</b>",
        f"• 🖼️ <b>{m['carrosseis']}</b> carrosséis no Feed ({m['produtos_carrossel']} achados divulgados)",
        f"• 📱 <b>{m['stories']}</b> stories publicados",
        f"• 💬 <b>{m['whatsapp']}</b> ofertas enviadas no WhatsApp" + (f" ({m['whatsapp_pendentes']} na fila)" if m['whatsapp_pendentes'] else ""),
        "",
        "👥 <b>Interações & Pedidos de Link:</b>",
        f"• 💌 <b>{m['pedidos_link']}</b> links enviados no Direct",
        f"• 🙋‍♂️ <b>{m['usuarios_unicos']}</b> pessoas únicas atendidas",
        "",
        "📈 <b>Distribuição de Links por Canal (SubIDs):</b>",
        f"• 💬 <b>WhatsApp (Grupo VIP):</b> {m['whatsapp']} ofertas divulgadas [<code>wpp</code>]",
        f"• 💌 <b>Instagram Direct:</b> {m['pedidos_link']} DMs entregues [<code>igdm</code>]",
        f"• 🖼️ <b>Instagram Feed:</b> {m['carrosseis']} carrosséis ativos [<code>igtop</code>]",
    ]

    if m["top_pedidos"]:
        linhas.append("\n🏆 <b>Achados mais pedidos:</b>")
        for idx, (nome, qtd) in enumerate(m["top_pedidos"], 1):
            linhas.append(f"  {idx}. {html.escape(nome)} — <b>{qtd}</b> pedido(s)")

    linhas.append("\n🩺 <b>Saúde do Sistema & Automações:</b>")
    try:
        problemas, resolvidas, ok, total, aviso = checar_workflows()
        if aviso:
            linhas.append(f"• {aviso}")
        elif problemas:
            linhas.append(f"• ⚠️ Atenção em {len(problemas)} rotina(s):")
            for p in problemas:
                linhas.append(f"  {p}")
            if resolvidas:
                for r in resolvidas:
                    linhas.append(f"  {r}")
        else:
            linhas.append(f"• ✅ Todas as <b>{ok} rotinas</b> operando sem erros ({total} execuções na semana)")
            if resolvidas:
                for r in resolvidas:
                    linhas.append(f"  {r}")
    except Exception as e:
        linhas.append(f"• ⚠️ Não foi possível verificar workflows: {html.escape(str(e))[:100]}")

    linhas.append("\n📦 <b>Status da Fila de Ofertas:</b>")
    if m["pendentes"] >= 10:
        linhas.append(f"• ✅ Fila abastecida: <b>{m['pendentes']}</b> ofertas prontas esperando.")
    else:
        linhas.append(f"• ⚠️ Fila baixa: apenas <b>{m['pendentes']}</b> ofertas restantes. Sugere-se novo garimpo.")

    linhas += [
        "",
        "🚀 <i>Automação operando normalmente. Ótima semana!</i>"
    ]
    return "\n".join(linhas)


def obter_chat_id():
    chat = os.getenv("TELEGRAM_CHAT_PRIVADO", "").strip()
    if chat:
        return chat
    # Auto-descoberta via getUpdates caso o segredo ainda não tenha sido cadastrado
    try:
        ups = telegram._api("getUpdates", data={"limit": 50})
        for u in reversed(ups):
            c = (u.get("message") or {}).get("chat") or {}
            if c.get("type") == "private" and c.get("id"):
                chat_id = str(c["id"])
                nome = c.get("first_name") or c.get("username") or ""
                print(f"💡 Chat ID privado detectado automaticamente via getUpdates: {chat_id} ({nome})")
                return chat_id
    except Exception as e:
        print(f"Aviso ao consultar getUpdates do Telegram: {e}")
    return None


def main():
    texto = montar_mensagem()
    print("=" * 60)
    print(texto)
    print("=" * 60)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("::warning::TELEGRAM_BOT_TOKEN não configurado — balanço exibido apenas no log.")
        return

    chat_id = obter_chat_id()
    if not chat_id:
        print("::warning::TELEGRAM_CHAT_PRIVADO não configurado e nenhuma mensagem recente no bot.")
        print("👉 Para receber o balanço: abra o Telegram, busque o bot @bbshopeebot e envie /start.")
        return

    try:
        telegram._api("sendMessage", data={
            "chat_id": chat_id,
            "text": texto,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true"
        })
        print(f"📨 Balanço semanal enviado com sucesso no Telegram (Chat ID: {chat_id})!")
    except Exception as e:
        print(f"::error::Erro ao enviar mensagem para o Telegram: {e}")


if __name__ == "__main__":
    main()
