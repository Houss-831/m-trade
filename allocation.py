"""Moteur d'allocation M-TRADE : compare plusieurs façons d'investir sur les vrais cours et garde la meilleure.

Méthodes comparées (toutes avec frais, sans regarder le futur, positions décidées la veille) :
- council_ls      : conseil des 8 stratégies, hausse et baisse (version actuelle)
- council_long    : conseil des 8 stratégies, hausse seulement
- ew              : tout acheter à parts égales et garder (référence « marché »)
- rp              : parité de risque : chaque actif pèse selon l'inverse de sa volatilité (Bridgewater, années 1990)
- rp_trend        : parité de risque + filtre de tendance 200 jours, vérifié chaque mois (Faber, 2007) :
                    on ne garde un actif que s'il est au-dessus de sa moyenne 200 jours, sinon liquidités
- rp_trend_short  : idem, et pari à la baisse seulement sur les marchés baissiers confirmés
                    (sous la moyenne 200 jours ET momentum 12 mois négatif)
- core_sat        : 70 % rp_trend (cœur) + 30 % conseil hausse/baisse (satellite tactique)
Chaque méthode est testée avec et sans thermomètre de crise.
La sélection se fait sur la régularité (3 périodes successives) ; un contrôle hors échantillon est publié.
"""
import json
import os
from datetime import date

import numpy as np
import pandas as pd

PATH = "data/allocation.json"
MODES = {
    "council_ls": "Conseil des 8 stratégies, hausse et baisse",
    "council_long": "Conseil des 8 stratégies, hausse seulement",
    "ew": "Tout acheter à parts égales et garder",
    "rp": "Parité de risque (chaque actif pèse selon sa volatilité)",
    "rp_trend": "Parité de risque + filtre de tendance 200 jours (Faber 2007)",
    "rp_trend_short": "Parité de risque + tendance 200 j + baisse sur marchés baissiers confirmés",
    "core_sat": "Cœur parité de risque + tendance (70 %) et conseil tactique (30 %)",
    "core50": "Base toujours investie (50 %) + conseil hausse seulement (50 %)",
    "core30": "Base toujours investie (30 %) + conseil hausse seulement (70 %)",
}


def _month_ends(idx):
    s = pd.Series(idx, index=idx)
    return set(s.groupby([idx.year, idx.month]).max().values)


def _monthly(w, idx):
    """Ne change les poids qu'en fin de mois (moins de frais), conservés entre-temps."""
    me = _month_ends(idx)
    mask = pd.Series([d in me for d in idx], index=idx)
    return w.where(mask, np.nan).ffill().fillna(0.0)


def inv_vol(px, days=60):
    v = px.pct_change().rolling(days).std()
    iv = 1 / v.replace(0, np.nan)
    return iv.div(iv.sum(axis=1), axis=0).fillna(0.0)


def weights(px, mode, p, council_score=None, thermo=None, target_vol=0.12):
    idx = px.index
    rets = px.pct_change()
    if mode in ("council_ls", "council_long"):
        from strategy import weights_from_scores, stress_factor
        vol = rets.rolling(p["vol_days"]).std() * np.sqrt(252)
        q = dict(p, allow_short=(mode == "council_ls"))
        w = weights_from_scores(council_score, vol, q, stress=stress_factor(px, p))
    elif mode in ("ew", "core50", "core30"):
        n = px.notna().sum(axis=1).replace(0, np.nan)
        w = px.notna().astype(float).div(n, axis=0).fillna(0.0) * 0.98
        if mode != "ew":
            from strategy import weights_from_scores, stress_factor
            vol = rets.rolling(p["vol_days"]).std() * np.sqrt(252)
            tac = weights_from_scores(council_score, vol, dict(p, allow_short=False), stress=stress_factor(px, p))
            base = 0.5 if mode == "core50" else 0.3
            w = base * w + (1 - base) * tac
    else:
        base = inv_vol(px)
        sma = px.rolling(200).mean()
        up = (px > sma).astype(float)
        if mode == "rp":
            w = base
        elif mode in ("rp_trend", "core_sat"):
            w = base * up
        elif mode == "rp_trend_short":
            bear = ((px < sma) & (px.pct_change(252) < 0)).astype(float)
            w = base * up - 0.5 * base * bear
        w = _monthly(w, idx)
        # volatilité cible du portefeuille (12 %), plafonnée à 100 % investi
        pv = (w.shift(1) * rets).sum(axis=1).rolling(60).std() * np.sqrt(252)
        lev = (target_vol / pv.replace(0, np.nan)).clip(upper=1.0).fillna(1.0)
        w = w.mul(lev, axis=0) * 0.98
        if mode == "core_sat":
            from strategy import weights_from_scores, stress_factor
            vol = rets.rolling(p["vol_days"]).std() * np.sqrt(252)
            sat = weights_from_scores(council_score, vol, dict(p, allow_short=True), stress=stress_factor(px, p))
            w = 0.7 * w + 0.3 * sat
    if thermo is not None:
        w = w.mul(thermo.reindex(idx).fillna(1.0), axis=0)
    return w.fillna(0.0)


def backtest(w, px, fee):
    rets = px.pct_change().fillna(0.0)
    ws = w.shift(1).fillna(0.0)
    return (ws * rets).sum(axis=1) - ws.diff().abs().sum(axis=1).fillna(0.0) * fee


def _sharpe(r):
    r = r.dropna()
    return float(r.mean() / r.std() * np.sqrt(252)) if len(r) > 20 and r.std() > 0 else 0.0


def _stats(r):
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    return {"sharpe": round(_sharpe(r), 2), "return": round(float(eq.iloc[-1] - 1), 4),
            "cagr": round(float(eq.iloc[-1] ** (1 / yrs) - 1), 4) if yrs > 0 else 0,
            "max_dd": round(float((eq / eq.cummax() - 1).min()), 4)}


def evaluate(prices, tradable, p, fee, tag=""):
    import crisis
    from strategies import council
    px = prices[[s for s in tradable if s in prices]].ffill()
    score, *_ = council(px, window=p.get("council_window", 60), temperature=p.get("council_temp", 4.0),
                        keys=p.get("strategies"), regime=p.get("regime_memory", True))
    th = crisis.factor_series(prices, tail=None)
    start = 252
    idx = px.index[start:]
    cut = np.linspace(0, len(idx), 4).astype(int)
    folds = [(idx[cut[i]], idx[cut[i + 1] - 1]) for i in range(3)]
    res = {}
    from strategy import apply_band
    for m in MODES:
        for use_th in (False, True):
            w0 = weights(px, m, p, score, th if use_th else None)
            for band in BANDS:
                r = backtest(apply_band(w0, band), px, fee).iloc[start:]
                fs = [_sharpe(r.loc[a:b]) for a, b in folds]
                res[(tag, m, use_th, band)] = {"mode": m, "thermo": use_th, "universe": tag, "band": band, "name": MODES[m], **_stats(r),
                                    "folds": [round(x, 2) for x in fs],
                                    "robust": round(float(np.mean(fs) - 0.5 * np.std(fs)), 3),
                                    "robust2": round(float(np.mean(fs[:2]) - 0.5 * np.std(fs[:2])), 3),
                                    "last": round(fs[2], 2),
                                    "turnover": round(float(apply_band(w0, band).diff().abs().sum(axis=1).iloc[start:].mean() * 252), 1)}
    return res, folds


UNIV_TXT = {"initial": "10 marchés d'origine", "élargi": "20 marchés (+ secteurs, grandes actions, obligations, argent)",
            "large": "31 marchés (+ pays émergents, Europe, Inde, Chine, immobilier, cuivre, Amazon, Google, Meta)"}
BANDS = [0.03, 0.06]       # seuil sous lequel on ne rééquilibre pas (moins d'ordres, moins de frais)


def choose(prices, universes, p, fee, previous=None, margin=0.05):
    """universes : {"initial": [...], "élargi": [...]}. Compare toutes les méthodes sur chaque univers.
    Anti-va-et-vient : la méthode en place n'est remplacée que si la nouvelle est nettement plus régulière (+0,05)."""
    res, folds = {}, None
    for tag, syms in universes.items():
        r, f = evaluate(prices, syms, p, fee, tag)
        res.update(r)
        folds = folds or f
    best = max(res, key=lambda k: res[k]["robust"])
    kept = False
    if previous:
        pk = (previous.get("universe"), previous.get("mode"), previous.get("thermo"), previous.get("band") or BANDS[0])
        try:
            age = (date.today() - date.fromisoformat(previous.get("since") or previous["date"])).days
        except (KeyError, ValueError):
            age = 999
        need = margin if age >= 28 else 0.15          # moins de 4 semaines : il faut une amélioration très nette
        if pk in res and res[best]["robust"] - res[pk]["robust"] < need:
            best, kept = pk, True
    blind = max(res, key=lambda k: res[k]["robust2"])          # choix sans voir la dernière période
    ranked = sorted(res.values(), key=lambda x: -x["robust"])
    b = res[best]
    ew = res[(b["universe"], "ew", False, BANDS[0])]
    old = res.get(("élargi", "core50", True, BANDS[0])) or res[(b["universe"], "council_long", True, BANDS[0])]
    out = {"date": date.today().isoformat(), "mode": b["mode"], "thermo": b["thermo"], "universe": b["universe"], "band": b["band"], "kept": kept,
           "since": (previous or {}).get("since") or (previous or {}).get("date") if kept else date.today().isoformat(),
           "chosen": b, "ranking": ranked, "folds": [[str(a)[:10], str(z)[:10]] for a, z in folds],
           "blind": {"mode": res[blind]["mode"], "thermo": res[blind]["thermo"], "universe": res[blind]["universe"],
                     "name": res[blind]["name"], "last": res[blind]["last"], "market_last": ew["last"]}}
    yrs = len(prices) / 252 - 1
    out["summary"] = (("Méthode conservée (aucune autre n'est nettement meilleure) : " if kept else "Méthode retenue : ") + f"{b['name']}{' + thermomètre de crise' if b['thermo'] else ''}, "
                      f"sur {UNIV_TXT.get(b['universe'], b['universe'])}, rééquilibrage au-delà de {b['band']:.0%} d'écart "
                      f"({b['turnover']:.0f} fois le portefeuille échangé par an). Sur {yrs:.1f} ans de vrais cours : "
                      f"{b['return']:+.0%} ({b['cagr']:+.1%} par an, Sharpe {b['sharpe']}, pire baisse {b['max_dd']:.0%}), "
                      f"contre {ew['return']:+.0%} ({ew['cagr']:+.1%} par an, pire baisse {ew['max_dd']:.0%}) pour « tout acheter et garder » "
                      f"et {old['return']:+.0%} ({old['cagr']:+.1%} par an) pour « base 50 % + conseil ».")
    return out


def load():
    try:
        with open(PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save(r):
    os.makedirs("data", exist_ok=True)
    with open(PATH, "w") as f:
        json.dump(r, f, ensure_ascii=False)


def due(days=7):
    r = load()
    if not r:
        return True
    try:
        return (date.today() - date.fromisoformat(r["date"])).days >= days
    except (KeyError, ValueError):
        return True
