"""Profil utilisateur de M-TRADE : tout ce que la personne peut régler elle-même.

Le fichier data/settings.json (créé depuis l'onglet Réglages de l'appli) prime sur config.py.
Exemple minimal :
{
  "user_name": "Mahjoub",
  "capital": 5000,            // capital fictif de départ (€)
  "invest_max": 3000,         // montant maximum investi à la fois (€)
  "max_loss_day": 100,        // perte maximale tolérée par jour (€)
  "max_loss_total": 750,      // perte totale à partir de laquelle le bot s'arrête (€)
  "risk_profile": "equilibre",// prudent | equilibre | offensif | perso
  "markets": ["Actions", "Crypto", "Matières", "Obligations"],
  "assets": null,             // null = tous les actifs des marchés choisis
  "strategies": null,         // null = les 8 stratégies
  "ai_weight": 0.3,
  "allow_short": true,
  "notify_orders": true,
  "summary_hour": 21
}
"""
import copy
import json
import os

import config

PROFILES = {
    "prudent":   {"target_vol": 0.08, "max_weight": 0.12, "entry_threshold": 0.35, "atr_mult": 2.5,
                  "dd_reduce": 0.06, "dd_cut": 0.10, "exit_threshold": 0.15, "tp1_atr": 4.0},
    "equilibre": {"target_vol": 0.15, "max_weight": 0.20, "entry_threshold": 0.25, "atr_mult": 3.0,
                  "dd_reduce": 0.12, "dd_cut": 0.20, "exit_threshold": 0.10, "tp1_atr": 6.0},
    "offensif":  {"target_vol": 0.25, "max_weight": 0.30, "entry_threshold": 0.18, "atr_mult": 3.5,
                  "dd_reduce": 0.18, "dd_cut": 0.30, "exit_threshold": 0.06, "tp1_atr": 8.0},
}
CLASSES = {"^FCHI": "Actions", "^GDAXI": "Actions", "^GSPC": "Actions", "^IXIC": "Actions",
           "^N225": "Actions", "BTC-USD": "Crypto", "ETH-USD": "Crypto", "SOL-USD": "Crypto",
           "GC=F": "Matières", "CL=F": "Matières", "SI=F": "Matières",
           "XLK": "Actions", "XLV": "Actions", "XLE": "Actions", "XLF": "Actions", "AAPL": "Actions",
           "MSFT": "Actions", "NVDA": "Actions", "TLT": "Obligations", "IEF": "Obligations"}

DEFAULT = {
    "user_name": "", "capital": config.PAPER["starting_cash"], "invest_max": None,
    "max_loss_day": None, "max_loss_total": None, "risk_profile": "equilibre", "custom": {},
    "markets": ["Actions", "Crypto", "Matières", "Obligations"], "assets": None, "strategies": None,
    "ai_weight": config.AI["news_weight"], "allow_short": True, "take_profit": True,
    "notify_orders": True, "summary_hour": config.PAPER.get("daily_summary_hour", 21),
}


def load_profile(path="data/settings.json"):
    prof = copy.deepcopy(DEFAULT)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                prof.update({k: v for k, v in json.load(f).items() if v is not None or k in DEFAULT})
        except Exception as e:
            print(f"[réglages] fichier illisible, valeurs par défaut utilisées : {e}")
    return prof


def apply_profile(prof):
    """Retourne (STRATEGY, RISK, PAPER, TRADABLE, stratégies actives, poids IA)."""
    preset = PROFILES.get(prof.get("risk_profile"), PROFILES["equilibre"])
    knobs = {**preset, **(prof.get("custom") or {})}
    strat = {**config.STRATEGY, "target_vol": knobs["target_vol"], "max_weight": knobs["max_weight"],
             "entry_threshold": knobs["entry_threshold"], "allow_short": bool(prof.get("allow_short")),
             "exit_threshold": min(knobs.get("exit_threshold", 0.1), knobs["entry_threshold"])}
    risk = {**config.RISK, "atr_mult": knobs["atr_mult"], "dd_reduce": knobs["dd_reduce"],
            "dd_cut": knobs["dd_cut"], "max_loss_day": prof.get("max_loss_day"),
            "take_profit": bool(prof.get("take_profit", True)), "tp1_atr": knobs.get("tp1_atr", 6.0),
            "tp2_atr": 2 * knobs.get("tp1_atr", 6.0),
            "max_loss_total": prof.get("max_loss_total"), "invest_max": prof.get("invest_max")}
    paper = {**config.PAPER, "starting_cash": float(prof.get("capital") or config.PAPER["starting_cash"]),
             "daily_summary_hour": prof.get("summary_hour")}
    markets = set(prof.get("markets") or CLASSES.values())
    tradable = [s for s in config.TRADABLE if CLASSES.get(s) in markets]
    if prof.get("assets"):
        tradable = [s for s in tradable if s in prof["assets"]]
    from strategies import KEYS
    keys = [k for k in (prof.get("strategies") or KEYS) if k in KEYS] or KEYS
    return strat, risk, paper, tradable, keys, float(prof.get("ai_weight", config.AI["news_weight"]))
