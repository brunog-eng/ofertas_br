"""Fila e agendamento exclusivo de postagens para o grupo do WhatsApp.

Regras definidas pelo usuário:
  1. Envia 4 itens a cada 2 horas, das 09:00 às 21:00 (horário de Brasília).
  2. Aceita itens das categorias Gold e Silver ('ouro', 'prata', 'achado').
  3. Intervalo randômico entre 1 e 5 minutos (60s a 300s) entre cada postagem para não floodar o grupo.
  4. Fila dedicada salva em data/fila_whatsapp.json.

Uso: python -m src.whatsapp_fila
"""
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, whatsapp_grupo

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BRT = timezone(timedelta(hours=-3))
FMT = "%Y-%m-%d %H:%M:%S"
ARQ_FILA_WHATSAPP = config.PASTA_DADOS / "fila_whatsapp.json"


def agora():
    return datetime.now(BRT)


def carregar_fila() -> dict:
    if ARQ_FILA_WHATSAPP.exists():
        try:
            return json.loads(ARQ_FILA_WHATSAPP.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"::warning::Erro ao ler fila_whatsapp.json: {e}")
    return {"ofertas": {}, "ultimo_envio": None}


def salvar_fila(fila: dict):
    ARQ_FILA_WHATSAPP.parent.mkdir(parents=True, exist_ok=True)
    ARQ_FILA_WHATSAPP.write_text(json.dumps(fila, ensure_ascii=False, indent=2), encoding="utf-8")


def sincronizar_com_garimpo(fila_zap: dict) -> int:
    """Importa ofertas novas de data/fila.json para a fila do WhatsApp (Gold e Silver)."""
    if not config.ARQ_FILA.exists():
        return 0

    try:
        dados_gerais = json.loads(config.ARQ_FILA.read_text(encoding="utf-8"))
        ofertas_gerais = dados_gerais.get("ofertas", {})
    except Exception as e:
        print(f"::warning::Erro ao ler data/fila.json para sincronizar: {e}")
        return 0

    novas = 0
    for oid, o in ofertas_gerais.items():
        # Filtro: precisa ter link de afiliado e ser Gold ou Silver ('ouro', 'prata', 'achado')
        nivel = o.get("nivel", "prata")
        if nivel not in ("ouro", "prata", "achado"):
            continue
        if not o.get("link_afiliado"):
            continue

        if oid not in fila_zap["ofertas"]:
            # Cria cópia dedicada para a fila do WhatsApp
            item_zap = dict(o)
            item_zap["status"] = "pendente"
            item_zap["adicionado_em"] = agora().strftime(FMT)
            item_zap["postado_em"] = ""
            fila_zap["ofertas"][oid] = item_zap
            novas += 1

    if novas > 0:
        print(f"📥 {novas} novas ofertas (Gold/Silver) importadas para a fila do WhatsApp.")
        salvar_fila(fila_zap)
    return novas


def escolher_ofertas(fila_zap: dict, qtd: int = 4) -> list:
    """Seleciona as melhores ofertas pendentes garantindo variedade de categorias."""
    candidatos = [
        o for o in fila_zap["ofertas"].values()
        if o.get("status") == "pendente" and o.get("link_afiliado")
    ]

    if not candidatos:
        return []

    # Prioridade de nível: achado > ouro > prata, desempatado por pontos/avaliação
    ordem_nivel = {"achado": 0, "ouro": 1, "prata": 2}
    candidatos.sort(key=lambda o: (
        ordem_nivel.get(o.get("nivel", "prata"), 2),
        -o.get("pontos", 0),
        -float(o.get("nota") or 0)
    ))

    escolhidos = []
    categorias_usadas = set()

    # 1ª Rodada: 1 item por categoria distinta para máxima diversidade
    for o in candidatos:
        cat = o.get("categoria", "geral")
        if cat not in categorias_usadas and len(escolhidos) < qtd:
            escolhidos.append(o)
            categorias_usadas.add(cat)

    # 2ª Rodada: completar com os melhores restantes até atingir qtd
    for o in candidatos:
        if o["id"] not in [x["id"] for x in escolhidos] and len(escolhidos) < qtd:
            escolhidos.append(o)

    return escolhidos


def rodar(qtd: int = 4, min_esp: int = None, max_esp: int = None):
    """Executa o ciclo de envio de ofertas para o grupo do WhatsApp."""
    print("=" * 60)
    print(f"📲 [WhatsApp Grupo] Iniciando rodada de postagens — {agora():%d/%m/%Y %H:%M}")
    print("=" * 60)

    if not whatsapp_grupo.configurado():
        print("::warning::Evolution API / WhatsApp Grupo não configurado no ambiente.")
        notificar_erro_telegram("Evolution API / WhatsApp Grupo não configurado no ambiente.")
        return

    min_esp = min_esp if min_esp is not None else int(os.getenv("WHATSAPP_ESPERA_MIN", "60"))
    max_esp = max_esp if max_esp is not None else int(os.getenv("WHATSAPP_ESPERA_MAX", "300"))

    fila_zap = carregar_fila()
    sincronizar_com_garimpo(fila_zap)

    pendentes_total = sum(1 for o in fila_zap["ofertas"].values() if o.get("status") == "pendente")
    print(f"📊 Fila do WhatsApp: {pendentes_total} ofertas pendentes.")

    itens = escolher_ofertas(fila_zap, qtd=qtd)
    if not itens:
        print("⚠️ Nenhuma oferta pendente disponível na fila do WhatsApp.")
        return

    print(f"🎯 Selecionadas {len(itens)} ofertas para publicação:")
    for i, it in enumerate(itens, 1):
        print(f"   {i}. [{it.get('nivel', 'prata').upper()}] {it.get('titulo')} — R$ {it.get('preco_fmt')}")

    enviados = 0
    for idx, it in enumerate(itens, 1):
        print(f"\n🚀 Enviando item #{idx}/{len(itens)}: {it.get('titulo')}...")
        sucesso = whatsapp_grupo.enviar_oferta(it)

        if sucesso:
            it["status"] = "postado"
            it["postado_em"] = agora().strftime(FMT)
            salvar_fila(fila_zap)
            enviados += 1
        else:
            print(f"::warning::Falha no envio do item #{idx}.")
            notificar_erro_telegram(f"Falha ao enviar o item #{idx} ({it.get('titulo')}) para o grupo.")

        # Intervalo randômico entre 1 e 5 minutos entre as postagens (exceto no último item)
        if idx < len(itens):
            espera = random.randint(min_esp, max_esp)
            print(f"⏳ Aguardando intervalo anti-spam: {espera // 60}m {espera % 60}s antes do próximo item...")
            time.sleep(espera)

    fila_zap["ultimo_envio"] = agora().strftime(FMT)
    salvar_fila(fila_zap)

    restantes = sum(1 for o in fila_zap["ofertas"].values() if o.get("status") == "pendente")
    print("\n" + "=" * 60)
    print(f"✅ Rodada concluída: {enviados}/{len(itens)} ofertas enviadas ao WhatsApp.")
    print(f"📦 Ofertas pendentes restantes na fila: {restantes}")
    print("=" * 60)


if __name__ == "__main__":
    qtd = int((sys.argv[1:2] or ["4"])[0])
    rodar(qtd=qtd)
