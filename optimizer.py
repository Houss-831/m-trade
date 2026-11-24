"""Réglage automatique de M-TRADE sur les vrais cours (une fois par semaine).

Méthode (validation croisée temporelle, sans regarder le futur) :
1. On teste des combinaisons de réglages du conseil : fenêtre d'évaluation des stratégies,
   « température » (vitesse à laquelle le conseil change d'avis), groupe de stratégies,
   seuil d'entrée et thermomètre de crise.
2. L'historique est coupé en 3 périodes successives. Un réglage est noté sur sa régularité :
   Sharpe moyen des 3 périodes moins la moitié de leur dispersion (un réglage brillant
   une seule fois est pénalisé).
3. Lissage anti-sur-ajustement : la note d'un réglage est moyennée avec celle de ses voisins
   (un bon réglage isolé au milieu de mauvais est probablement de la chance).
4. Contrôle honnête : on refait la sélection sur les 2 premières périodes seulement,
   et on regarde comment le réglage choisi se comporte sur la 3e, jamais vue.
5. Le nouveau réglage n'est adopté que s'il bat nettement le réglage actuel
   ET qu'il ne fait pas pire hors échantillon.
"""
import itertools
import json
import os
from datetime import date

import numpy as np
import pandas as pd

from strategies import council
from strategy import weights_from_scores, stress_factor, apply_band

PATH = "data/tuning.json"
WINDOWS = [40, 60, 120]
TEMPS = [2.0, 4.0, 8.0]
GROUPS = {
    "tous": None,
    "tendance": ["dow", "tsmom", "xsmom", "donchian", "macd"],
    "sans_chandeliers": ["dow", "tsmom", "xsmom", "donchian", "macd", "bollinger", "rsi2"],
}
GROUP_TXT = {"tous": "les 8 stratégies", "tendance": "suivi de tendance et momentum seulement",
             "sans_chandeliers": "7 stratégies, sans les chandeliers"}
ENTRIES = [0.15, 0.20, 0.25, 0.30, 0.35]
THERMO = [True, False]


def _sharpe(r):
    r = r.dropna()
    return float(r.mean() / r.std() * np.sqrt(252)) if len(r) > 20 and r.std() > 0 else 0.0


def _folds(idx, n=3, start=252):
    cut = np.linspace(start, len(idx), n + 1).astype(int)
    return [(idx[cut[i]], idx[cut[i + 1] - 1]) for i in range(n)]


def _evaluate(px, p, fee, thermo_f):
    """Rendements quotidiens pour toutes les combinaisons (le conseil est calculé une fois par trio)."""
    rets = px.pct_change().fillna(0.0)
    vol = px.pct_change().rolling(p["vol_days"]).std() * np.sqrt(252)
    stress = stress_factor(px, p)
    out = {}
    for wdw, tp, g in itertools.product(WINDOWS, TEMPS, GROUPS):
        score, *_ = council(px, window=wdw, temperature=tp, keys=GROUPS[g], regime=p.get("regime_memory", True))
        for ent, th in itertools.product(ENTRIES, THERMO):
            q = dict(p, entry_threshold=ent, exit_threshold=min(p.get("exit_threshold", 0.10), ent - 0.05))
            st = stress * (thermo_f.reindex(stress.index).fillna(1.0) if th else 1.0)
            w = weights_from_scores(score, vol, q, stress=st)
            w = apply_band(w, p.get("min_trade_pct", 0.03)).shift(1).fillna(0.0)
            port = (w * rets).sum(axis=1) - w.diff().abs().sum(axis=1).fillna(0.0) * fee
            out[(wdw, tp, g, ent, th)] = port
    return out, rets.mean(axis=1)


def _robust(scores_by_key):
    """Moyenne avec les voisins (fenêtre, température et seuil adjacents)."""
    sm = {}
    for k, v in scores_by_key.items():
        wdw, tp, g, ent, th = k
        neigh = [v]
        for dw in (-1, 1):
            i = WINDOWS.index(wdw) + dw
            if 0 <= i < len(WINDOWS):
                neigh.append(scores_by_key[(WINDOWS[i], tp, g, ent, th)])
        for dt in (-1, 1):
            i = TEMPS.index(tp) + dt
            if 0 <= i < len(TEMPS):
                neigh.append(scores_by_key[(wdw, TEMPS[i], g, ent, th)])
        for de in (-1, 1):
            i = ENTRIES.index(ent) + de
            if 0 <= i < len(ENTRIES):
                neigh.append(scores_by_key[(wdw, tp, g, ENTRIES[i], th)])
        sm[k] = 0.5 * v + 0.5 * float(np.mean(neigh[1:])) if len(neigh) > 1 else v
    return sm


def _score(port, folds):
    s = [_sharpe(port.loc[a:b]) for a, b in folds]
    return float(np.mean(s) - 0.5 * np.std(s)), s


def current_key(p):
    keys = p.get("strategies")
    g = next((n for n, ks in GROUPS.items() if (ks is None and not keys) or (ks and keys and sorted(ks) == sorted(keys))), "tous")
    near = lambda v, grid: min(grid, key=lambda x: abs(x - v))
    return (near(p.get("council_window", 60), WINDOWS), near(p.get("council_temp", 4.0), TEMPS), g,
            near(p.get("entry_threshold", 0.25), ENTRIES), bool(p.get("thermo", True)))


def tune(prices, tradable, p, fee):
    import crisis
    px = prices[[s for s in tradable if s in prices]].ffill().dropna(how="all")
    if len(px) < 252 + 180:
        return None
    thermo_f = crisis.factor_series(prices, tail=None)
    res, bench = _evaluate(px, p, fee, thermo_f)
    idx = px.index
    folds = _folds(idx)
    raw = {k: _score(v, folds)[0] for k, v in res.items()}
    sm = _robust(raw)
    best = max(sm, key=sm.get)
    cur = current_key(p)

    # contrôle hors échantillon : sélection sur les 2 premières périodes, test sur la 3e
    raw2 = {k: _score(v, folds[:2])[0] for k, v in res.items()}
    sm2 = _robust(raw2)
    best2 = max(sm2, key=sm2.get)
    a, b = folds[2]
    oos_best = _sharpe(res[best2].loc[a:b])
    oos_cur = _sharpe(res[cur].loc[a:b])
    oos_mkt = _sharpe(bench.loc[a:b])

    adopt = sm[best] > sm[cur] + 0.10 and oos_best >= oos_cur - 0.05
    chosen = best if adopt else cur
    fold_s = _score(res[chosen], folds)[1]
    top = sorted(sm, key=sm.get, reverse=True)[:5]

    def desc(k):
        return {"window": k[0], "temperature": k[1], "group": k[2], "group_txt": GROUP_TXT[k[2]],
                "entry": k[3], "thermo": k[4]}

    def stats(k):
        r = res[k].iloc[252:]
        return {"sharpe": round(_sharpe(r), 2), "return": round(float((1 + r).prod() - 1), 4),
                "max_dd": round(float(((1 + r).cumprod() / (1 + r).cumprod().cummax() - 1).min()), 4),
                "robust": round(sm[k], 2)}

    out = {
        "date": date.today().isoformat(), "tested": len(res), "years": round((len(idx) - 252) / 252, 1),
        "adopted": bool(adopt), "chosen": desc(chosen), "chosen_stats": stats(chosen),
        "previous": desc(cur), "previous_stats": stats(cur),
        "market_sharpe": round(_sharpe(bench.iloc[252:]), 2),
        "folds": [{"from": str(a)[:10], "to": str(b)[:10], "sharpe": round(s, 2)} for (a, b), s in zip(folds, fold_s)],
        "oos": {"from": str(a)[:10], "to": str(b)[:10], "chosen": round(oos_best, 2),
                "previous": round(oos_cur, 2), "market": round(oos_mkt, 2), "pick": desc(best2)},
        "top": [{**desc(k), **stats(k)} for k in top],
    }
    out["summary"] = (
        ("Nouveau réglage adopté : " if adopt else "Réglage actuel conservé : ")
        + f"conseil sur {chosen[0]} jours, température {chosen[1]:g}, {GROUP_TXT[chosen[2]]}, "
        + f"seuil d'entrée {chosen[3]:.2f}, thermomètre {'actif' if chosen[4] else 'inactif'}. "
        + f"Sharpe {out['chosen_stats']['sharpe']} contre {out['previous_stats']['sharpe']} avant et "
        + f"{out['market_sharpe']} pour le marché, sur {out['years']} ans de vrais cours ({len(res)} réglages testés).")
    return out


def load():
    try:
        with open(PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save(res):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w") as f:
        json.dump(res, f, ensure_ascii=False)


def apply(p, res):
    """Applique le réglage choisi à la configuration (sans toucher au niveau de risque de l'utilisateur)."""
    if not res:
        return p
    c = res["chosen"]
    p["council_window"], p["council_temp"] = c["window"], c["temperature"]
    p["entry_threshold"] = c["entry"]
    p["exit_threshold"] = min(p.get("exit_threshold", 0.10), c["entry"] - 0.05)
    p["thermo"] = c["thermo"]
    if not p.get("user_strategies"):
        p["strategies"] = GROUPS[c["group"]]
    return p


def due(days=7):
    r = load()
    if not r:
        return True
    try:
        return (date.today() - date.fromisoformat(r["date"])).days >= days
    except (KeyError, ValueError):
        return True
