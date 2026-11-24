"""Thermomètre de crise M-TRADE (0 à 100).

Combine cinq symptômes observés lors des grandes crises (1987, 2000, 2008, 2020, 2022) :
- corrélations qui s'envolent (tout baisse ensemble),
- volatilité récente très au-dessus de la normale,
- baisse depuis le plus haut du panier d'actifs risqués,
- vitesse de chute sur 10 jours,
- part des actifs passés sous leur moyenne 50 jours.
Aucun regard vers le futur : chaque jour ne voit que le passé.
"""
import numpy as np
import pandas as pd

RISKY = ["^FCHI", "^GDAXI", "^GSPC", "^IXIC", "^N225", "BTC-USD", "ETH-USD", "SOL-USD", "CL=F"]
LEVELS = [(0, "calme", "Marché calme : le bot applique ses règles normales."),
          (35, "tension", "Tension : quelques signaux de nervosité, vigilance accrue."),
          (55, "stress", "Stress : volatilité et corrélations en hausse, le bot devient plus sélectif."),
          (70, "crise", "Profil de crise : le bot réduit son exposition (×0,6) et protège le capital.")]

ANALOGUES = {
    "eclair": ("2020 · Covid / 1987 · Lundi noir",
               "Chute très rapide et brutale. Historiquement suivie de rebonds violents : réduire sans tout vendre au plus bas."),
    "systemique": ("2008 · Crise financière",
                   "Tout baisse ensemble et longtemps. La diversification s'évapore : priorité au capital et aux liquidités."),
    "taux": ("2022 · Retour de l'inflation",
             "Les taux montent vite : croissance et crypto souffrent le plus, l'or et les liquidités résistent mieux."),
    "bulle": ("2000 · Bulle Internet",
              "Lente érosion après des excès. Les rebonds sont souvent des pièges tant que la tendance de fond est baissière."),
    "calme": ("Aucun analogue de crise",
              "Les symptômes des grandes crises sont absents. Rester discipliné : les krachs arrivent souvent par surprise."),
}


def _clip01(x):
    return np.clip(x, 0.0, 1.0)


def series(px, window=20, long=120, tail=420):
    cols = [c for c in RISKY if c in px.columns]
    p = px[cols].ffill()
    if tail:
        p = p.iloc[-tail:]
    r = p.pct_change()
    basket = (1 + r.mean(axis=1).fillna(0)).cumprod()
    # corrélation moyenne entre paires (fenêtre courte)
    corr = pd.Series(np.nan, index=p.index)
    vals = r.values
    for i in range(window, len(p)):
        w = vals[i - window + 1:i + 1]
        w = w[:, ~np.isnan(w).any(axis=0)]
        if w.shape[1] >= 3:
            m = np.corrcoef(w.T)
            n = m.shape[0]
            corr.iloc[i] = (m.sum() - n) / (n * n - n)
    corr_long = corr.rolling(long, min_periods=40).mean()
    vs = r.rolling(window).std().mean(axis=1)
    vl = r.rolling(long, min_periods=40).std().mean(axis=1)
    dd = basket / basket.rolling(long, min_periods=20).max() - 1
    speed = basket / basket.shift(10) - 1
    breadth = (p < p.rolling(50).mean()).mean(axis=1)

    s_corr = _clip01((corr - corr_long) / 0.35)
    s_vol = _clip01((vs / vl - 1.0) / 1.2)
    s_dd = _clip01(-dd / 0.20)
    s_speed = _clip01(-speed / 0.12)
    s_breadth = _clip01((breadth - 0.4) / 0.5)
    comp = pd.DataFrame({"correlation": s_corr, "volatilite": s_vol, "baisse": s_dd,
                         "vitesse": s_speed, "largeur": s_breadth}).fillna(0)
    score = (100 * (0.20 * comp.correlation + 0.25 * comp.volatilite + 0.25 * comp.baisse
                    + 0.15 * comp.vitesse + 0.15 * comp.largeur)).ewm(span=3, adjust=False).mean()
    return score, comp, {"dd": dd, "speed": speed}


def level(score):
    lab, txt = LEVELS[0][1], LEVELS[0][2]
    for th, l, t in LEVELS:
        if score >= th:
            lab, txt = l, t
    return lab, txt


def analogue(score, comp, px):
    if score < 35:
        return "calme"
    c = comp
    tnx_up = False
    if "^TNX" in px.columns:
        t = px["^TNX"].dropna()
        tnx_up = len(t) > 60 and (t.iloc[-1] - t.iloc[-60]) > 0.6
    if c["vitesse"] > 0.6 and c["volatilite"] > 0.6:
        return "eclair"
    if tnx_up:
        return "taux"
    if c["correlation"] > 0.5 and c["baisse"] > 0.5:
        return "systemique"
    return "bulle"


def thermometer(px):
    score, comp, raw = series(px)
    s = float(score.iloc[-1])
    last = comp.iloc[-1].to_dict()
    lab, txt = level(s)
    key = analogue(s, last, px)
    an, lesson = ANALOGUES[key]
    hist = score.tail(250)
    return {"score": round(s, 1), "level": lab, "text": txt,
            "components": {k: round(float(v) * 100, 1) for k, v in last.items()},
            "analogue": an, "analogue_key": key, "lesson": lesson,
            "drawdown": round(float(raw["dd"].iloc[-1]) * 100, 1),
            "speed10": round(float(raw["speed"].iloc[-1]) * 100, 1),
            "history": [round(float(x), 1) for x in hist.values],
            "dates": [str(d)[:10] for d in hist.index],
            "peak_250": round(float(hist.max()), 1),
            "scale": 0.6 if s >= 70 else (0.85 if s >= 55 else 1.0)}


def factor_series(px, tail=None):
    """Facteur d'exposition quotidien (pour backtest, labo et réglage automatique)."""
    score, _, _ = series(px, tail=tail)
    return pd.Series(np.where(score >= 70, 0.6, np.where(score >= 55, 0.85, 1.0)), index=score.index)
