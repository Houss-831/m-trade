"""Rapport quotidien en français + envoi Telegram (optionnel)."""
import json
import os
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime

ICON = {"ACHAT": "🟢", "VENTE À DÉCOUVERT": "🔴", "ÉVITER / SORTIR": "🟠", "NEUTRE": "⚪"}


def build_report(signals, orders, state, value, top_news):
    start = state["start_value"]
    perf = value / start - 1
    L = [f"🤖 M-TRADE — RAPPORT — {datetime.now():%d/%m/%Y %H:%M}", "",
         f"💼 Portefeuille fictif : {value:,.0f} € ({perf:+.2%} depuis le départ)", ""]

    L.append("🌍 ACTU QUI BOUGE LES MARCHÉS")
    for n in top_news[:5]:
        L.append(f"• {n['title']} ({n['source']})")
    if not top_news:
        L.append("• Aucune actu récupérée")
    L.append("")

    L.append("🎯 SIGNAUX DU JOUR")
    ranked = sorted(signals.values(), key=lambda s: s["score"], reverse=True)
    for s in ranked:
        L.append(f"{ICON.get(s['action'], '⚪')} {s['name']} : {s['action']} "
                 f"(score {s['score']:+.2f}, confiance {s['confidence']})")
        if s["action"] != "NEUTRE":
            for r in s["reasons"]:
                L.append(f"   – {r}")
            for h in s["headlines"][:1]:
                L.append(f"   📰 {h['title']}")
    L.append("")

    L.append("🧾 ORDRES FICTIFS PASSÉS")
    if orders:
        for o in orders:
            L.append(f"• {o['side']} {o['name']} : {o['amount']:,.0f} € à {o['price']}")
    else:
        L.append("• Aucun changement de position")
    L.append("")
    L.append("⚠️ Simulation avec de l'argent fictif. Ce n'est pas un conseil financier.")
    return "\n".join(L)


def build_trade_alert(order, signal, state, value):
    """Message détaillé pour UN ordre : quoi, pourquoi, comment, quelle actu."""
    perf = value / state["start_value"] - 1
    emoji = "🟢" if order["side"] in ("ACHAT", "RENFORCEMENT") else "🔴"
    L = [f"⚡ M-TRADE", f"{emoji} {order['side']} — {order['name']}", ""]
    L.append("📋 CE QUE J'AI FAIT")
    L.append(f"• Montant : {order['amount']:,.0f} € au prix de {order['price']:,.2f} €")
    L.append(f"• Poids dans le portefeuille : {order['weight_before']:.0%} → {order['weight_after']:.0%}")
    if order.get("pnl") is not None:
        res = "gain" if order["pnl"] >= 0 else "perte"
        L.append(f"• Résultat réalisé : {res} de {order['pnl']:+,.0f} €")
    L.append(f"• Frais simulés : {order['fee']:.2f} €")
    L.append("")
    L.append(f"🧠 POURQUOI (score {signal.get('score', 0):+.2f}, confiance {signal.get('confidence', '?')})")
    for r in signal.get("reasons", []):
        L.append(f"• {r}")
    L.append("")
    L.append("⚙️ COMMENT J'AI DIMENSIONNÉ")
    L.append(f"• Volatilité annuelle de l'actif : {signal.get('volatility', 0):.0%}")
    L.append("• Plus un actif est volatil, plus la position est petite (cible 15 %/an, max 20 % du capital)")
    L.append("")
    heads = signal.get("headlines", [])
    L.append("📰 L'ACTU LIÉE")
    if heads:
        for h in heads[:3]:
            tone = "👍" if h["sentiment"] > 0.15 else "👎" if h["sentiment"] < -0.15 else "➖"
            L.append(f"{tone} {h['title']} ({h['source']})")
            if h.get("link"):
                L.append(f"   {h['link']}")
    else:
        L.append("• Aucune actu marquante : décision purement technique")
    if signal.get("macro"):
        L.append("")
        L.append("🌍 CONTEXTE MONDIAL (IA)")
        L.append(f"• {signal['macro']}")
    L.append("")
    L.append(f"💼 Portefeuille : {value:,.0f} € ({perf:+.2%} depuis le départ) · "
             f"liquidités {state['cash']:,.0f} €")
    L.append("⚠️ Argent fictif, simulation. Pas un conseil financier.")
    return "\n".join(L)


def build_summary(state, value, prices, names, extra=None):
    perf = value / state["start_value"] - 1
    L = [f"🌙 M-TRADE — BILAN DU {datetime.now():%d/%m/%Y}", "",
         f"💼 {value:,.0f} € ({perf:+.2%} depuis le départ)",
         f"💶 Gains/pertes réalisés : {state.get('realized_pnl', 0):+,.0f} €",
         f"💵 Liquidités : {state['cash']:,.0f} €", "", "📦 POSITIONS"]
    basis = state.get("cost_basis", {})
    for s, q in state["positions"].items():
        v = q * prices.get(s, 0)
        lat = v / basis[s] - 1 if basis.get(s) else 0
        L.append(f"• {names.get(s, s)} : {v:,.0f} € ({lat:+.1%} latent)")
    if not state["positions"]:
        L.append("• Aucune, 100 % en liquidités")
    if extra:
        L.append("")
        L.append(f"🏛️ Méthode dominante du conseil : {extra['leader']}")
        t = extra.get("top")
        if t:
            L.append(f"🎯 Plus forte conviction : {t['name']} ({t['action']}, score {t['score']:+.2f})")
        b = extra.get("breaker") or {}
        L.append(f"🛡️ Bouclier : {'disjoncteur ACTIVÉ ×' + str(b.get('factor')) if b.get('factor', 1) < 1 else 'au repos'}"
                 f" · recul depuis le sommet {b.get('drawdown', 0):.1%}")
        for e in (extra.get("events") or [])[:3]:
            L.append(f"   – {e['text']}")
        lab = extra.get("lab")
        if lab:
            L.append(f"🧪 Laboratoire : {lab['verdict']} (probabilité d'un vrai avantage {lab['prob_edge']:.0%})")
    L.append("\n⚠️ Argent fictif, simulation.")
    return "\n".join(L)


def clean_token(raw):
    """Le jeton collé peut contenir des espaces, un retour à la ligne ou le texte de BotFather autour : on extrait le jeton."""
    import re
    m = re.search(r"\d{5,}:[A-Za-z0-9_-]{20,}", raw or "")
    return m.group(0) if m else (raw or "").strip()


def telegram_chat(token):
    """Identifiant de la conversation : secret TELEGRAM_CHAT_ID, sinon trouvé tout seul
    à partir du dernier message que tu as envoyé à ton bot (il suffit de lui écrire « bonjour »)."""
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if chat:
        return chat
    path = "data/telegram_chat.txt"
    try:
        with open(path) as f:
            return f.read().strip() or None
    except OSError:
        pass
    def status(txt):
        os.makedirs("data", exist_ok=True)
        with open("data/telegram_status.json", "w") as f:
            json.dump({"at": datetime.now().isoformat(timespec="seconds"), "status": txt}, f, ensure_ascii=False)
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15) as r:
            ups = json.loads(r.read().decode()).get("result", [])
        status(f"jeton valide, {len(ups)} message(s) reçu(s) par le bot")
        for u in reversed(ups):
            m = u.get("message") or u.get("edited_message") or {}
            if m.get("chat", {}).get("id"):
                chat = str(m["chat"]["id"])
                os.makedirs("data", exist_ok=True)
                with open(path, "w") as f:
                    f.write(chat)
                return chat
    except urllib.error.HTTPError as e:
        status(f"erreur Telegram {e.code} : " + ("jeton invalide (vérifie le secret TELEGRAM_TOKEN)" if e.code in (401, 404) else
                                                 "conflit : un autre programme lit déjà les messages du bot" if e.code == 409 else "inconnue"))
        return None
    except Exception as e:
        raw = os.getenv("TELEGRAM_TOKEN") or ""
        import re
        shape = ("ressemble à un lien t.me ou à un nom de bot, pas au jeton" if ("t.me" in raw or raw.strip().startswith("@") or raw.strip().lower().endswith("bot"))
                 else "il manque le « : » entre les chiffres et les lettres" if ":" not in raw
                 else "format inattendu")
        status(f"erreur : {type(e).__name__} · le secret TELEGRAM_TOKEN n'a pas la forme d'un jeton Telegram "
               f"({len(raw.strip())} caractères ; {shape}). Un jeton ressemble à 1234567890:AAH… (environ 46 caractères).")
        return None
    status("jeton valide mais aucune conversation : écris « bonjour » à ton bot dans Telegram")
    return None


_WELCOMED = False


def send_telegram(text):
    """Envoie le message si TELEGRAM_TOKEN est défini (la conversation est trouvée automatiquement)."""
    global _WELCOMED
    token = clean_token(os.getenv("TELEGRAM_TOKEN"))
    if not token:
        return False
    first = not os.path.exists("data/telegram_chat.txt") and not os.getenv("TELEGRAM_CHAT_ID")
    chat = telegram_chat(token)
    if not chat:
        return False
    if first and not _WELCOMED:
        _WELCOMED = True
        text = ("✅ M-TRADE est connecté à ton Telegram. Tu recevras ici chaque achat et chaque vente du bot "
                "(avec ses raisons et le verdict des 10 000 scénarios), les alertes importantes et un résumé chaque soir.\n\n") + text
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for i in range(0, len(text), 4000):            # limite Telegram : 4096 caractères
        data = urllib.parse.urlencode({"chat_id": chat, "text": text[i:i + 4000]}).encode()
        urllib.request.urlopen(url, data=data, timeout=15)
    return True
