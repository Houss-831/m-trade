"""Le conseil des stratégies de M-TRADE.

Les grandes méthodes du trading, chacune codée telle que ses auteurs l'ont décrite.
Chacune vote chaque jour pour chaque actif entre -1 (vendre) et +1 (acheter).
Le conseil pondère ensuite les votes selon la réussite RÉCENTE de chaque méthode :
une stratégie qui marche gagne du poids, une qui échoue en perd, sans jamais tomber à zéro.
"""
import numpy as np
import pandas as pd

LIBRARY = [
    {"key": "dow", "name": "Tendance de fond", "short": "Tend.", "family": "Suivi de tendance",
     "origin": "Charles Dow, vers 1900 ; « golden cross » 50/200 jours",
     "idea": "Le marché suit des tendances durables. On achète tant que la moyenne 50 jours est au-dessus de la 200 jours."},
    {"key": "tsmom", "name": "Momentum temporel", "short": "Mom. T", "family": "Momentum",
     "origin": "Moskowitz, Ooi et Pedersen, 2012",
     "idea": "Un actif qui a monté sur 12 mois (hors dernier mois) a tendance à continuer. Vérifié sur plus d'un siècle de données."},
    {"key": "xsmom", "name": "Momentum relatif", "short": "Mom. R", "family": "Momentum",
     "origin": "Jegadeesh et Titman, 1993",
     "idea": "Acheter les actifs qui ont le mieux performé par rapport aux autres sur 6 mois, éviter les plus faibles."},
    {"key": "donchian", "name": "Cassure de canal", "short": "Cass.", "family": "Suivi de tendance",
     "origin": "Richard Donchian, années 1960 ; les « Turtles » de Richard Dennis, 1983",
     "idea": "Une cassure du plus haut (ou du plus bas) des 55 derniers jours signale le début d'un mouvement."},
    {"key": "macd", "name": "MACD", "short": "MACD", "family": "Momentum",
     "origin": "Gerald Appel, fin des années 1970",
     "idea": "L'écart entre deux moyennes exponentielles (12 et 26 jours) mesure l'accélération du prix."},
    {"key": "bollinger", "name": "Retour à la moyenne", "short": "Boll.", "family": "Retour à la moyenne",
     "origin": "John Bollinger, années 1980",
     "idea": "Un prix trop loin de sa moyenne 20 jours (en écarts-types) tend à y revenir. Actif surtout quand il n'y a pas de tendance (ADX faible)."},
    {"key": "rsi2", "name": "RSI court", "short": "RSI 2", "family": "Retour à la moyenne",
     "origin": "J. Welles Wilder (RSI, 1978) ; Larry Connors (RSI 2 jours, années 2000)",
     "idea": "Acheter les replis excessifs dans une tendance haussière, alléger les excès dans une tendance baissière."},
    {"key": "candles", "name": "Chandeliers japonais", "short": "Chand.", "family": "Figures de chandeliers",
     "origin": "Munehisa Homma, XVIIIe siècle (marché du riz de Dojima) ; Steve Nison, 1991",
     "idea": "Marteau, étoile filante, avalement, étoiles du matin et du soir, trois soldats ou trois corbeaux : des figures de retournement, comptées seulement après une vraie tendance, et dont l'effet s'estompe en quelques jours."},
]
KEYS = [s["key"] for s in LIBRARY]
OHLC = None   # {symbole: DataFrame Open/High/Low/Close}, fourni par main (bougies réelles)

PATTERNS = {
    "marteau": ("Marteau", +1, "Longue mèche basse après une baisse : les acheteurs ont rejeté les plus bas."),
    "etoile_filante": ("Étoile filante", -1, "Longue mèche haute après une hausse : les vendeurs ont rejeté les plus hauts."),
    "avalement_h": ("Avalement haussier", +1, "Une bougie verte englobe la rouge précédente après une baisse."),
    "avalement_b": ("Avalement baissier", -1, "Une bougie rouge englobe la verte précédente après une hausse."),
    "etoile_matin": ("Étoile du matin", +1, "Rouge, petite indécision, puis forte verte : retournement haussier en trois temps."),
    "etoile_soir": ("Étoile du soir", -1, "Verte, petite indécision, puis forte rouge : retournement baissier en trois temps."),
    "trois_soldats": ("Trois soldats blancs", +1, "Trois fortes bougies vertes successives : les acheteurs prennent le contrôle."),
    "trois_corbeaux": ("Trois corbeaux noirs", -1, "Trois fortes bougies rouges successives : les vendeurs prennent le contrôle."),
    "doji": ("Doji", 0, "Ouverture et clôture presque égales : indécision, souvent avant un changement."),
}


_CP_CACHE = {}


def candle_patterns(df):
    """Mis en cache par série (les figures n'utilisent que le passé : calcul unique sur tout l'historique)."""
    k = (id(df), len(df))
    if k not in _CP_CACHE:
        _CP_CACHE[k] = _candle_patterns(df)
    return _CP_CACHE[k]


def _candle_patterns(df):
    """Détecte les figures sur un DataFrame OHLC. Retourne (signal décroissant -1..+1, DataFrame booléen des figures)."""
    o, h, l, c = (df[k].astype(float) for k in ("Open", "High", "Low", "Close"))
    body = (c - o).abs()
    rng_ = (h - l).replace(0, np.nan)
    up_w = h - np.maximum(o, c)
    lo_w = np.minimum(o, c) - l
    avg_body = body.rolling(10).mean()
    prior = c.shift(1) / c.shift(8) - 1                  # tendance des jours précédents
    vol = c.pct_change().rolling(20).std() * np.sqrt(7)
    down, up = prior < -0.6 * vol, prior > 0.6 * vol
    green, red = c > o, c < o
    big = body > avg_body
    f = pd.DataFrame(index=df.index)
    f["marteau"] = down & (lo_w > 2 * body) & (up_w < body + 0.1 * rng_)
    f["etoile_filante"] = up & (up_w > 2 * body) & (lo_w < body + 0.1 * rng_)
    f["avalement_h"] = down & green & red.shift(1, fill_value=False) & (c >= o.shift(1)) & (o <= c.shift(1)) & big
    f["avalement_b"] = up & red & green.shift(1, fill_value=False) & (c <= o.shift(1)) & (o >= c.shift(1)) & big
    small1 = body.shift(1) < 0.5 * avg_body
    f["etoile_matin"] = (prior.shift(1) < -0.6 * vol) & red.shift(2, fill_value=False) & big.shift(2, fill_value=False) & small1 & green & (c > (o.shift(2) + c.shift(2)) / 2)
    f["etoile_soir"] = (prior.shift(1) > 0.6 * vol) & green.shift(2, fill_value=False) & big.shift(2, fill_value=False) & small1 & red & (c < (o.shift(2) + c.shift(2)) / 2)
    g3 = green & green.shift(1, fill_value=False) & green.shift(2, fill_value=False)
    r3 = red & red.shift(1, fill_value=False) & red.shift(2, fill_value=False)
    f["trois_soldats"] = g3 & big & big.shift(1, fill_value=False) & (c > c.shift(1)) & (c.shift(1) > c.shift(2)) & (up_w < 0.3 * body)
    f["trois_corbeaux"] = r3 & big & big.shift(1, fill_value=False) & (c < c.shift(1)) & (c.shift(1) < c.shift(2)) & (lo_w < 0.3 * body)
    f["doji"] = body < 0.08 * rng_
    f = f.fillna(False).astype(bool)
    raw = sum(f[k].astype(float) * PATTERNS[k][1] for k in PATTERNS)
    sig = raw.clip(-1, 1).ewm(alpha=0.35, adjust=False).mean() * 1.6   # effet qui s'estompe en ~5 jours
    return sig.clip(-1, 1), f


_CV_CACHE = {}


def _candle_votes(px):
    """Votes des chandeliers alignés sur les dates de px (calcul unique, puis découpage)."""
    if not OHLC:
        return pd.DataFrame(0.0, index=px.index, columns=px.columns)
    key = (id(OHLC), tuple(px.columns))
    full = _CV_CACHE.get(key)
    if full is None:
        cols = {}
        for sym in px.columns:
            d = OHLC.get(sym)
            if d is not None and len(d) > 15:
                sg, _ = candle_patterns(d)
                idx = pd.to_datetime(sg.index)
                if getattr(idx, "tz", None) is not None:
                    idx = idx.tz_localize(None)
                sg = pd.Series(sg.values, index=idx.normalize())
                cols[sym] = sg[~sg.index.duplicated(keep="last")]
        full = pd.DataFrame(cols)
        _CV_CACHE.clear()
        _CV_CACHE[key] = full
    return full.reindex(px.index).ffill(limit=2).reindex(columns=px.columns).fillna(0.0)


def latest_patterns(sym, days=3, asof=None):
    """Figures repérées sur les `days` dernières bougies d'un actif (jusqu'à `asof` inclus)."""
    if not OHLC or sym not in OHLC or OHLC[sym] is None or len(OHLC[sym]) < 15:
        return []
    _, f = candle_patterns(OHLC[sym])
    if asof is not None:
        idx = pd.to_datetime(f.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        f = f[idx.normalize() <= pd.Timestamp(asof).normalize()]
    out = []
    for i, (ts, row) in enumerate(f.tail(days).iloc[::-1].iterrows()):
        for k in PATTERNS:
            if row[k]:
                nm, d, txt = PATTERNS[k]
                out.append({"key": k, "name": nm, "dir": d, "text": txt, "ago": i, "date": str(ts)[:10]})
    return out
NAMES = {s["key"]: s["name"] for s in LIBRARY}


def _vol(px, n=20):
    return px.pct_change().rolling(n).std()


def adx(px, n=14):
    """ADX de Wilder approché sur les seuls cours de clôture (force de la tendance, 0 à 100)."""
    up = px.diff().clip(lower=0)
    dn = (-px.diff()).clip(lower=0)
    tr = px.diff().abs()
    atr = tr.ewm(alpha=1 / n, adjust=False).mean()
    pdi = 100 * up.ewm(alpha=1 / n, adjust=False).mean() / atr.replace(0, np.nan)
    mdi = 100 * dn.ewm(alpha=1 / n, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def atr(px, n=14):
    """ATR approché sur clôtures (amplitude moyenne d'une journée, en prix)."""
    return px.diff().abs().ewm(alpha=1 / n, adjust=False).mean()


def votes(px, p=None):
    """Retourne {clé: DataFrame de votes entre -1 et +1}."""
    v = {}
    vol = _vol(px)
    sma50, sma200 = px.rolling(50).mean(), px.rolling(200).mean()
    v["dow"] = np.sign(sma50 - sma200)

    r12 = px.shift(21) / px.shift(252) - 1
    v["tsmom"] = (r12 / (vol * np.sqrt(231))).clip(-2, 2) / 2

    r6 = px / px.shift(126) - 1
    rank = r6.rank(axis=1, pct=True)
    v["xsmom"] = (rank - 0.5) * 2

    hi, lo = px.rolling(55).max(), px.rolling(55).min()
    v["donchian"] = ((px - (hi + lo) / 2) / ((hi - lo) / 2).replace(0, np.nan)).clip(-1, 1)

    macd = px.ewm(span=12, adjust=False).mean() - px.ewm(span=26, adjust=False).mean()
    hist = macd - macd.ewm(span=9, adjust=False).mean()
    v["macd"] = (hist / (px * vol).replace(0, np.nan) / 2).clip(-1, 1)

    z = (px - px.rolling(20).mean()) / px.rolling(20).std().replace(0, np.nan)
    a = adx(px)
    range_factor = ((30 - a) / 15).clip(0, 1)            # actif seulement sans tendance forte
    v["bollinger"] = (-z / 2).clip(-1, 1) * range_factor

    delta = px.diff()
    upm = delta.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    dnm = (-delta.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    rsi2 = 100 - 100 / (1 + upm / dnm.replace(0, np.nan))
    trend = np.sign(px - sma200)
    sig = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    sig[(rsi2 < 10) & (trend > 0)] = 1.0
    sig[(rsi2 < 25) & (rsi2 >= 10) & (trend > 0)] = 0.5
    sig[(rsi2 > 90) & (trend < 0)] = -1.0
    sig[(rsi2 > 75) & (rsi2 <= 90) & (trend < 0)] = -0.5
    v["rsi2"] = sig

    cs = _candle_votes(px)
    v["candles"] = cs
    return {k: v[k].reindex_like(px).fillna(0.0) for k in KEYS}


REGIMES = ["haussier", "baissier", "indécis", "crise"]
REGIME_TXT = {"haussier": "Marché haussier : la majorité des actifs est en tendance montante",
              "baissier": "Marché baissier : la majorité des actifs est en tendance descendante",
              "indécis": "Marché indécis : pas de direction commune claire",
              "crise": "Marché en crise : la volatilité explose par rapport à la normale"}


def market_regimes(px):
    """Régime de marché de chaque jour, à partir de l'ensemble des actifs (sans regarder le futur)."""
    r = px.pct_change()
    ratio = (r.rolling(20).std() / r.rolling(250, min_periods=60).std()).median(axis=1)
    breadth = (px.rolling(50).mean() > px.rolling(200).mean()).mean(axis=1)
    reg = pd.Series("indécis", index=px.index)
    reg[breadth >= 0.6] = "haussier"
    reg[breadth <= 0.4] = "baissier"
    reg[ratio > 1.5] = "crise"
    return reg


def council(px, window=60, temperature=4.0, floor=0.04, keys=None, regime=True):
    """Pondère les stratégies selon leur Sharpe récent (sur `window` jours), sans regarder le futur.

    Retourne (score, poids, votes, skill) :
      score : DataFrame des scores combinés, entre -1 et +1
      poids : DataFrame (date × stratégie), somme = 1
      skill : DataFrame (date × stratégie), Sharpe annualisé récent de chaque stratégie
    """
    ks = [k for k in (keys or KEYS) if k in KEYS] or KEYS
    V = {k: v for k, v in votes(px).items() if k in ks}
    rets = px.pct_change().fillna(0.0)
    strat_ret = pd.DataFrame({k: (V[k].shift(1) * rets).mean(axis=1) for k in ks})
    m = strat_ret.rolling(window, min_periods=20).mean()
    s = strat_ret.rolling(window, min_periods=20).std()
    recent = (m / s.replace(0, np.nan) * np.sqrt(252)).fillna(0.0).clip(-3, 3)
    # Mémoire par régime : comment chaque méthode s'est comportée, dans le passé, dans le même type de marché
    reg = market_regimes(px)
    prev = reg.shift(1)
    cond = pd.DataFrame(0.0, index=px.index, columns=ks)
    known = pd.Series(False, index=px.index)
    for g in REGIMES:
        mask = (prev == g)
        x = strat_ret.where(mask)
        cnt = x.notna().cumsum().shift(1)
        s1 = x.fillna(0).cumsum().shift(1)
        s2 = (x.fillna(0) ** 2).cumsum().shift(1)
        mu = s1 / cnt
        sd = np.sqrt((s2 / cnt - mu ** 2).clip(lower=1e-12))
        sh = (mu / sd * np.sqrt(252)).clip(-3, 3)
        ok = (cnt >= 40)
        today = (reg == g)
        for k in ks:
            cond.loc[today & ok[k], k] = sh.loc[today & ok[k], k]
        known |= today & ok[ks[0]]
    skill = recent.where(~known, 0.5 * recent + 0.5 * cond) if regime else recent
    ex = np.exp(temperature * skill.shift(1).fillna(0.0) / 3)
    w = ex.div(ex.sum(axis=1), axis=0)
    w = w.ewm(span=10, adjust=False).mean()                     # lissage : moins de revirements
    w = w.div(w.sum(axis=1), axis=0)
    floor = min(floor, 0.5 / len(ks))
    w = w * (1 - floor * len(ks)) + floor                       # chaque méthode garde une voix
    score = sum(V[k].mul(w[k], axis=0) for k in ks)
    # Les votes se contredisent souvent : on ré-étale pour garder l'échelle -1..+1
    score = (score * 1.8).clip(-1, 1)
    council.last_regime = reg
    council.last_cond = cond
    return score, w, V, skill


def standalone(px, fee=0.001):
    """Performance de chaque stratégie seule sur l'historique (pour comparer)."""
    V = votes(px)
    rets = px.pct_change().fillna(0.0)
    out = {}
    for k in KEYS:
        w = V[k].shift(1).fillna(0) / len(px.columns)
        r = (w * rets).sum(axis=1) - w.diff().abs().sum(axis=1).fillna(0) * fee
        r = r.iloc[252:]
        eq = (1 + r).cumprod()
        out[k] = {"return": float(eq.iloc[-1] - 1) if len(eq) else 0.0,
                  "sharpe": float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0.0,
                  "hit": float((r[r != 0] > 0).mean()) if (r != 0).any() else 0.0}
    return out
