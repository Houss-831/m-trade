"""Récupération des cours et des actualités."""
import re
import html
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import numpy as np
import pandas as pd


def get_prices(symbols, period="3y"):
    """Cours de clôture quotidiens (Yahoo Finance via yfinance)."""
    import time
    import yfinance as yf
    for attempt in range(3):
        try:
            full = yf.download(list(symbols), period=period, interval="1d",
                               auto_adjust=True, progress=False)
            df = full["Close"]
            if len(df):
                break
        except Exception as e:
            print(f"[cours] tentative {attempt + 1} échouée : {e}")
        time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError("Impossible de télécharger les cours (Yahoo Finance)")
    if isinstance(df, pd.Series):
        df = df.to_frame(symbols[0])
    df = df.ffill().dropna(how="all")
    ohlc = {}
    for s in df.columns:                       # bougies : ouverture, plus haut, plus bas, clôture, volume
        try:
            o = pd.DataFrame({k: full[k][s] for k in ("Open", "High", "Low", "Close", "Volume")}).dropna(subset=["Close"])
            ohlc[s] = o
        except Exception:
            pass
    return df, ohlc


def synthetic_ohlc(close, seed=7):
    """Bougies simulées cohérentes avec une série de clôtures (mode démo)."""
    rng = np.random.default_rng(seed)
    c = close.values
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.002, len(c)))
    span = np.abs(np.r_[0, np.diff(np.log(c))]) + 0.004
    h = np.maximum(o, c) * (1 + span * rng.uniform(0.2, 0.9, len(c)))
    lo = np.minimum(o, c) * (1 - span * rng.uniform(0.2, 0.9, len(c)))
    v = rng.lognormal(10, 0.4, len(c)) * (1 + 20 * span)
    return pd.DataFrame({"Open": o, "High": h, "Low": lo, "Close": c, "Volume": v}, index=close.index)


def synthetic_prices(symbols, days=900, seed=42):
    """Cours simulés pour tester le bot sans connexion."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    base = {"^FCHI": 7500, "^GDAXI": 19000, "^GSPC": 5800, "^IXIC": 19000, "^N225": 38000,
            "BTC-USD": 60000, "ETH-USD": 2500, "SOL-USD": 120, "EURUSD=X": 1.08, "USDJPY=X": 150,
            "GC=F": 2400, "CL=F": 75, "^TNX": 4.2}
    out = {}
    for i, s in enumerate(symbols):
        drift = rng.normal(0.0003, 0.0004)
        vol = 0.035 if "-USD" in s else 0.012
        regime = np.sin(np.linspace(0, rng.uniform(2, 6), days)) * 0.001
        rets = rng.normal(drift + regime, vol, days)
        if s in ("EURUSD=X", "USDJPY=X", "^TNX"):
            rets = rets / 4                     # taux et devises bougent peu
        out[s] = base.get(s, 100) * np.exp(np.cumsum(rets))
    return pd.DataFrame(out, index=idx)


def _clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def get_news(feeds, max_age_hours=36, timeout=10):
    """Titres récents depuis des flux RSS. Les flux en erreur sont ignorés."""
    items = []
    now = datetime.now(timezone.utc)
    for url in feeds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                root = ET.fromstring(r.read())
        except Exception as e:
            print(f"[news] flux ignoré {url}: {e}")
            continue
        for it in root.iter("item"):
            title = _clean(it.findtext("title"))
            desc = _clean(it.findtext("description"))[:300]
            link = (it.findtext("link") or "").strip()
            pub = it.findtext("pubDate")
            try:
                dt = parsedate_to_datetime(pub)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                dt = now
            if (now - dt).total_seconds() / 3600 <= max_age_hours and title:
                items.append({"title": title, "summary": desc, "link": link,
                              "date": dt, "source": url.split("/")[2]})
    seen, unique = set(), []
    for n in sorted(items, key=lambda x: x["date"], reverse=True):
        key = n["title"].lower()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(n)
    return unique
