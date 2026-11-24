"""Mémoire de l'IA : chaque prédiction est notée quelques jours plus tard.

- record()  : enregistre les impacts prévus par l'IA pour chaque actif, avec le prix du moment.
- score()   : 5 séances plus tard, compare la prévision au mouvement réel.
- report()  : bilan (taux de bons appels, corrélation prévision/réalité, erreurs récentes, par actif).
- weight()  : le poids de l'IA dans les décisions dépend de ses vrais résultats.
- bulletin(): texte renvoyé à l'IA dans son prompt, pour qu'elle tienne compte de ses erreurs.
"""
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

PATH = "data/ai_memory.json"
HORIZON = 5          # séances
MIN_CALLS = 30       # appels notés avant d'ajuster le poids de l'IA
SIGNIFICANT = 0.1    # |impact × confiance| minimal pour compter comme un vrai appel


def load(path=PATH):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save(mem, path=PATH):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mem[-3000:], f, ensure_ascii=False)


def record(mem, per_asset, prices, when):
    day = pd.Timestamp(when).strftime("%Y-%m-%d")
    mem[:] = [m for m in mem if not (m["date"] == day and m["sym"] in per_asset)]   # un appel par actif et par jour
    for sym, a in per_asset.items():
        if sym not in prices or a.get("impact") is None:
            continue
        mem.append({"date": day, "sym": sym, "impact": round(float(a["impact"]), 3),
                    "conf": round(float(a.get("confidence", 0)), 3), "px": float(prices[sym].dropna().iloc[-1]),
                    "why": (a.get("ai_explanation") or "")[:160]})


def score(mem, prices):
    for m in mem:
        if m.get("ret") is not None or m["sym"] not in prices:
            continue
        s = prices[m["sym"]].dropna()
        after = s[s.index > pd.Timestamp(m["date"])]
        if len(after) >= HORIZON:
            m["ret"] = round(float(after.iloc[HORIZON - 1] / m["px"] - 1), 5)
            sig = m["impact"] * m["conf"]
            m["hit"] = None if abs(sig) < SIGNIFICANT else bool(np.sign(sig) == np.sign(m["ret"]))


def report(mem, names=None):
    names = names or {}
    done = [m for m in mem if m.get("ret") is not None]
    sig = [m for m in done if m.get("hit") is not None]
    acc = float(np.mean([m["hit"] for m in sig])) if sig else None
    ic = None
    if len(done) >= 10:
        x = np.array([m["impact"] * m["conf"] for m in done]); y = np.array([m["ret"] for m in done])
        if x.std() > 0 and y.std() > 0:
            ic = float(np.corrcoef(x, y)[0, 1])
    by = {}
    for m in sig:
        b = by.setdefault(m["sym"], [0, 0]); b[0] += m["hit"]; b[1] += 1
    wrong = sorted([m for m in sig if not m["hit"]], key=lambda m: -abs(m["impact"] * m["conf"] * m["ret"]))[:5]
    return {"calls": len(mem), "scored": len(done), "significant": len(sig), "accuracy": acc, "ic": ic,
            "by_asset": [{"symbol": k, "name": names.get(k, k), "hits": v[0], "n": v[1], "acc": v[0] / v[1]}
                         for k, v in sorted(by.items(), key=lambda kv: -kv[1][1])],
            "recent": [{**m, "name": names.get(m["sym"], m["sym"])} for m in sorted(done, key=lambda m: m["date"], reverse=True)[:12]],
            "pending": len(mem) - len(done),
            "mistakes": [{**m, "name": names.get(m["sym"], m["sym"])} for m in wrong]}


def weight(rep, base):
    """Poids de l'IA : il monte si elle voit juste, il baisse si elle se trompe."""
    if not rep or rep["significant"] < MIN_CALLS or rep["accuracy"] is None:
        return base, "en apprentissage (" + str(rep["significant"] if rep else 0) + f"/{MIN_CALLS} appels notés)"
    f = float(np.clip(1 + (rep["accuracy"] - 0.5) * 5, 0.3, 1.6))
    if rep["ic"] is not None and rep["ic"] < 0:
        f = min(f, 0.5)
    w = float(np.clip(base * f, 0.05, 0.5))
    why = f"{rep['accuracy']:.0%} de bons appels" + (f", corrélation {rep['ic']:+.2f}" if rep["ic"] is not None else "")
    return w, why


def bulletin(rep):
    if not rep or not rep["significant"]:
        return "Aucun de tes appels n'a encore été noté : reste prudent dans tes niveaux de confiance."
    L = [f"Sur tes {rep['significant']} derniers appels notés (horizon {HORIZON} séances), "
         f"{rep['accuracy']:.0%} étaient dans le bon sens"
         + (f", corrélation prévision/réalité {rep['ic']:+.2f}" if rep["ic"] is not None else "") + "."]
    good = [b for b in rep["by_asset"] if b["n"] >= 5 and b["acc"] >= 0.6]
    bad = [b for b in rep["by_asset"] if b["n"] >= 5 and b["acc"] <= 0.4]
    if good:
        L.append("Tu es fiable sur : " + ", ".join(f"{b['name']} ({b['acc']:.0%})" for b in good) + ".")
    if bad:
        L.append("Tu te trompes souvent sur : " + ", ".join(f"{b['name']} ({b['acc']:.0%})" for b in bad)
                 + ". Baisse ta confiance sur ces actifs sauf information vraiment décisive.")
    for m in rep["mistakes"][:3]:
        L.append(f"Erreur du {m['date']} sur {m['name']} : tu prévoyais {m['impact']:+.2f} "
                 f"(« {m['why'][:90]} »), le marché a fait {m['ret']:+.1%}.")
    return "\n".join(L)
