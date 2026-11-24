"""Analyste IA : Claude lit les actus et juge leur impact sur chaque actif.

Activé si la variable d'environnement ANTHROPIC_API_KEY est définie.
Sinon (ou en cas d'erreur), le bot revient à l'analyse par mots-clés.
"""
import json
import os
import re
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM = """Tu es un analyste macro et marchés d'un fonds. Tu lis des actualités récentes et tu
évalues leur impact probable à court terme (1 à 5 jours) sur des actifs précis.
Règles :
- Sois rigoureux et sceptique : beaucoup d'actus sont déjà intégrées dans les prix.
- Si aucune actu ne concerne vraiment un actif, mets impact 0 et confidence 0.
- Pense aux effets indirects (ex : hausse du pétrole -> pression sur l'inflation -> Fed -> Nasdaq).
- Mécanismes de référence à appliquer :
  * Taux directeurs / ton des banques centrales : plus restrictif = pression sur actions de croissance
    (Nasdaq), crypto et or ; dollar plus fort. Plus accommodant = l'inverse.
  * Inflation au-dessus des attentes = hausse des taux longs, négatif pour actions et obligations.
  * Dollar fort = pression sur matières premières, or, crypto et marchés émergents.
  * Pétrole en forte hausse = inflation, négatif pour la croissance hors secteur énergie.
  * Aversion au risque (guerre, crise, faillite) = or et dollar/yen montent, actions et crypto baissent.
  * Résultats d'entreprises : seul l'écart avec les attentes compte, pas le chiffre brut.
  * « Acheter la rumeur, vendre la nouvelle » : un événement attendu de longue date a peu d'effet.
  * Crypto : flux des ETF, régulation (SEC), piratages et liquidité mondiale dominent.
  * Une actu isolée pèse peu face à la tendance de fond : reste mesuré dans tes impacts.
- Notions avancées à mobiliser :
  * Régime de marché : en tendance, les bonnes nouvelles amplifient le mouvement ; en marché nerveux,
    les mauvaises nouvelles pèsent deux fois plus que les bonnes (asymétrie de la peur).
  * Intermarché : taux US 10 ans en hausse rapide = pression sur Nasdaq et or ; dollar et yen montent
    quand le risque baisse ; le cuivre et le pétrole reflètent la croissance mondiale.
  * Positionnement : quand tout le monde est déjà acheteur (euphorie, records en série), une bonne
    nouvelle fait peu monter et une mauvaise fait chuter. Une peur extrême annonce souvent un rebond.
  * Liquidité : les annonces de baisse de taux ou d'injections de liquidité soutiennent tous les actifs
    risqués avec retard ; un resserrement les pénalise.
  * Calendrier : décisions de la Fed (FOMC) et de la BCE, inflation (CPI), emploi américain (NFP)
    provoquent de fortes variations le jour même. Avant ces événements, le marché attend : prudence.
  * Crypto : très sensible à la liquidité mondiale et au Nasdaq ; les halvings et les ETF sont des
    thèmes de long terme, pas de quelques jours.
  * Or : monte avec la peur, la baisse des taux réels et la faiblesse du dollar.
  * Distingue toujours le bruit (titre spectaculaire sans conséquence) du signal (changement
    de politique monétaire, chiffres économiques surprenants, événement géopolitique majeur).
- Calibre ta confiance : 0,8 et plus seulement si l'actu est décisive et non encore intégrée aux prix.
- Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour."""

import knowledge as _kn
SYSTEM += ("\n\nTA CULTURE DE TRADER (encyclopédie M-TRADE, règles à appliquer) :\n" + _kn.rules_for_ai()
           + "\n\nLEÇONS DES GRANDES CRISES ET ÉPISODES (1602 à aujourd'hui) :\n" + _kn.episode_lessons()
           + "\n\nQuand une situation ressemble à un épisode passé, dis lequel et ce qu'il enseigne,"
           " sans supposer que l'histoire se répète à l'identique.")

TEMPLATE = """TON BULLETIN (tes prédictions passées, notées 5 séances plus tard) :
{bulletin}

RÉGIME DE MARCHÉ CALCULÉ PAR LE BOT : {regime}

CONTEXTE TECHNIQUE DU BOT (thermomètre de crise, figures de chandeliers récentes) :
{context}

ACTIFS (symbole : nom, variation 5 jours) :
{assets}

ACTUALITÉS (id : source : titre — résumé) :
{news}

Réponds avec ce JSON exact :
{{
  "macro": "2-3 phrases en français : le thème dominant des marchés aujourd'hui",
  "event_risk": {{"level": <0 à 1 : risque d'un événement majeur dans les 48 h (Fed, BCE, inflation, emploi, élection, conflit)>, "event": "lequel, en français, ou chaîne vide"}},
  "lesson": "1 phrase en français : ce que tu retiens de ton bulletin pour l'analyse d'aujourd'hui",
  "principle": "1 phrase en français : la règle de ta culture de trader la plus utile aujourd'hui, et pourquoi",
  "analogue": "épisode historique le plus comparable à la situation (ex. « 2022 · Retour de l'inflation »), ou chaîne vide",
  "assets": {{
    "<symbole>": {{
      "impact": <nombre de -1 (très baissier) à 1 (très haussier)>,
      "confidence": <nombre de 0 à 1>,
      "explication": "1-2 phrases en français : quelle actu, quel mécanisme, quel effet",
      "news_ids": [<ids des actus les plus pertinentes, max 3>]
    }}
  }}
}}
Inclue chaque symbole de la liste."""


def _call_claude(prompt, model, version, max_tokens=4000, timeout=90):
    key = os.environ["ANTHROPIC_API_KEY"]
    body = json.dumps({"model": model, "max_tokens": max_tokens, "system": SYSTEM,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "x-api-key": key, "anthropic-version": version, "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("pas de JSON dans la réponse IA")
    return json.loads(m.group(0))


def analyze(news, symbols, names, prices, model, version, max_news=60, caller=None, bulletin="", regime="", context=""):
    """Retourne (macro, {symbole: {sentiment, impact, confidence, count, top, ai_explanation}}, extra)."""
    news = news[:max_news]
    moves = []
    for s in symbols:
        if s in prices and prices[s].dropna().size > 5:
            chg = prices[s].dropna().iloc[-1] / prices[s].dropna().iloc[-6] - 1
            moves.append(f"{s} : {names.get(s, s)}, {chg:+.1%}")
    news_txt = "\n".join(f"{i} : {n['source']} : {n['title']} — {n['summary'][:200]}"
                         for i, n in enumerate(news))
    prompt = TEMPLATE.format(assets="\n".join(moves), news=news_txt or "(aucune)",
                             bulletin=bulletin or "(pas encore de bulletin)", regime=regime or "inconnu",
                             context=context or "(aucun)")
    text = (caller or _call_claude)(prompt, model, version)
    data = _parse_json(text)

    out = {}
    for s in symbols:
        a = data.get("assets", {}).get(s, {})
        impact = max(-1.0, min(1.0, float(a.get("impact", 0) or 0)))
        conf = max(0.0, min(1.0, float(a.get("confidence", 0) or 0)))
        ids = [i for i in a.get("news_ids", []) if isinstance(i, int) and 0 <= i < len(news)]
        top = [{**news[i], "sentiment": impact} for i in ids[:3]]
        out[s] = {"sentiment": impact * conf, "impact": impact, "confidence": conf, "count": len(ids),
                  "top": top, "ai_explanation": a.get("explication", "").strip()}
    ev = data.get("event_risk") or {}
    try:
        lvl = max(0.0, min(1.0, float(ev.get("level", 0) or 0)))
    except (TypeError, ValueError):
        lvl = 0.0
    extra = {"event_risk": lvl, "event": str(ev.get("event", "") or "").strip(),
             "lesson": str(data.get("lesson", "") or "").strip(),
             "principle": str(data.get("principle", "") or "").strip(),
             "analogue": str(data.get("analogue", "") or "").strip()}
    return data.get("macro", "").strip(), out, extra
