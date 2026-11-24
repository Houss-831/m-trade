"""Analyse de sentiment des actualités (lexique financier FR/EN, sans dépendance).

Option avancée : remplacer score_text() par un modèle (FinBERT ou un LLM).
"""
import re

POSITIVE = {
    "surge", "soar", "rally", "beat", "beats", "record", "gain", "gains", "rise",
    "rises", "jump", "jumps", "growth", "bullish", "upgrade", "strong", "boost",
    "approval", "approved", "rate cut", "cuts rates", "stimulus", "optimism",
    "hausse", "bondit", "record", "progresse", "rebond", "croissance", "optimisme",
    "relèvement", "baisse des taux", "accord", "dépasse", "solide",
}
NEGATIVE = {
    "plunge", "crash", "slump", "fall", "falls", "drop", "drops", "miss", "misses",
    "recession", "bearish", "downgrade", "weak", "fears", "war", "sanctions",
    "tariff", "tariffs", "default", "hack", "hacked", "lawsuit", "inflation surge",
    "rate hike", "layoffs", "selloff", "sell-off", "ban", "crisis",
    "chute", "plonge", "recul", "baisse", "récession", "crainte", "craintes",
    "guerre", "sanctions", "droits de douane", "faillite", "crise", "piratage",
    "hausse des taux", "licenciements", "inquiétude",
}
NEGATORS = {"not", "no", "pas", "ne", "without", "sans"}


def score_text(text):
    """Score entre -1 (très négatif) et +1 (très positif)."""
    t = " " + text.lower() + " "
    words = re.findall(r"[a-zàâçéèêëîïôûùüÿœ'-]+", t)
    pos = neg = 0
    for phrase in POSITIVE:
        if " " in phrase and phrase in t:
            pos += 1
    for phrase in NEGATIVE:
        if " " in phrase and phrase in t:
            neg += 1
    for i, w in enumerate(words):
        flip = i > 0 and words[i - 1] in NEGATORS
        if w in POSITIVE:
            neg, pos = (neg + 1, pos) if flip else (neg, pos + 1)
        elif w in NEGATIVE:
            pos, neg = (pos + 1, neg) if flip else (pos, neg + 1)
    total = pos + neg
    return 0.0 if total == 0 else (pos - neg) / total


def news_by_asset(news, keywords):
    """Associe les actus aux actifs et calcule un sentiment moyen par actif."""
    result = {}
    for sym, kws in keywords.items():
        matched = []
        for n in news:
            text = f" {n['title']} {n['summary']} ".lower()
            if any(k in text for k in kws):
                s = score_text(n["title"] + " " + n["summary"])
                matched.append({**n, "sentiment": s})
        avg = sum(m["sentiment"] for m in matched) / len(matched) if matched else 0.0
        result[sym] = {"sentiment": avg, "count": len(matched),
                       "top": sorted(matched, key=lambda m: abs(m["sentiment"]),
                                     reverse=True)[:3]}
    return result
