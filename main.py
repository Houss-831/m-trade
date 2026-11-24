"""Point d'entrée du bot.

  python main.py backtest          # teste la stratégie sur 5 ans d'historique
  python main.py run               # analyse, passe les ordres fictifs, alerte Telegram par ordre
  python main.py run --demo        # même chose avec des données simulées (sans internet)
  python main.py status            # état du portefeuille fictif
  python main.py replay --days 120  # rejoue 120 jours pour démarrer avec un historique
"""
import argparse
import numpy as np
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from data import get_prices, synthetic_prices, synthetic_ohlc, get_news
from ai_analyst import analyze
from sentiment import news_by_asset, score_text
from strategy import explain, weights_from_scores, compute_scores, build_context
from risk import apply_risk, corr_adjust
from lab import lab_cached
import ai_memory
import knowledge
from strategies import market_regimes, REGIME_TXT, council
from signals_feed import build_feed, data_health
from settings import load_profile, apply_profile
from backtest import run_backtest, format_report
from paper import load_state, save_state, rebalance, append_journal, portfolio_value
from dashboard import build_payload, write_dashboard, score_snapshot
from report import build_report, build_trade_alert, build_summary, send_telegram


def load_prices(demo, period):
    syms = list(config.UNIVERSE)
    if "USDJPY=X" not in syms:
        syms.append("USDJPY=X")
    if demo:
        px = synthetic_prices(syms)
        px["EURUSD=X"], px["USDJPY=X"] = 1.08, 150.0
        ohlc = {s: synthetic_ohlc(px[s], seed=i) for i, s in enumerate(px.columns)}
    else:
        px, ohlc = get_prices(syms, period)
    raw = px.ffill()
    eur = to_eur(px)
    eur.attrs["raw"] = raw
    import strategies as _st
    _st.OHLC = ohlc
    config.OHLC = ohlc            # gardé hors de pandas.attrs (recopié à chaque opération, trop lent)
    return eur


def to_eur(px):
    """Convertit les prix des actifs tradés en euros (vrais taux de change)."""
    px = px.copy()
    eurusd = px["EURUSD=X"].ffill()
    usdjpy = px["USDJPY=X"].ffill()
    for s in config.TRADABLE:
        if s not in px:
            continue
        cur = config.CURRENCY.get(s, "USD")
        if cur == "USD":
            px[s] = px[s] / eurusd
        elif cur == "JPY":
            px[s] = px[s] / (usdjpy * eurusd)
    return px.ffill()


def cmd_backtest(args):
    prices = load_prices(args.demo, "5y")
    res = run_backtest(prices, config.STRATEGY, config.PAPER["fee_rate"], config.TRADABLE)
    print(format_report(res))


def _mock_ai(prompt, model, version):
    """Fausse réponse IA pour tester sans clé API."""
    return json.dumps({"event_risk": {"level": 0.3, "event": "décision de la Fed dans la semaine"},
        "principle": "Exemple : « réduire la taille avant les grandes publications » — la Fed parle cette semaine.",
        "analogue": "",
        "lesson": "Exemple : mes appels sur le pétrole ont été trop confiants, je réduis ma confiance sur ce marché.",
        "macro": "Exemple de lecture IA : appétit pour le risque porté par la tech et la crypto, avec une Fed qui temporise. Le pétrole recule sur des craintes d'offre, l'Europe reste à la traîne et l'or profite des tensions géopolitiques.",
        "assets": {"^IXIC": {"impact": 0.5, "confidence": 0.6, "news_ids": [3, 2],
            "explication": "Des résultats tech solides et une Fed moins agressive soutiennent les valeurs de croissance."},
                   "^FCHI": {"impact": -0.3, "confidence": 0.5, "news_ids": [4],
            "explication": "Les craintes de la BCE sur la croissance pèsent sur les actions européennes."},
                   "GC=F": {"impact": 0.4, "confidence": 0.5, "news_ids": [5],
            "explication": "Les tensions géopolitiques renforcent la demande de valeur refuge."},
                   "BTC-USD": {"impact": 0.7, "confidence": 0.8, "news_ids": [0],
            "explication": "Les entrées record dans les ETF montrent une demande institutionnelle forte."},
                   "CL=F": {"impact": -0.6, "confidence": 0.7, "news_ids": [1],
            "explication": "Les craintes d'offre excédentaire de l'OPEP pèsent sur les prix du brut."}}})


def ai_payload(mem, rep, nw, nw_why, extra, reg_now, ctx):
    """Bulletin de l'IA et lecture du régime, pour l'interface."""
    from strategies import NAMES
    rep = rep or ai_memory.report(mem, config.UNIVERSE)
    w, why = (nw, nw_why) if nw is not None else ai_memory.weight(rep, config.AI["news_weight"])
    cond = getattr(council, "last_cond", None)
    regs = getattr(council, "last_regime", None)
    fav = []
    if cond is not None and len(cond):
        row = cond.iloc[-1]
        fav = [{"key": k, "name": NAMES.get(k, k), "sharpe": round(float(v), 2)} for k, v in row.sort_values(ascending=False).items()]
    timeline = []
    if regs is not None:
        r = regs.iloc[-180:]
        timeline = [[d.strftime("%Y-%m-%d"), g] for d, g in r.items()]
    return {"report": rep, "weight": round(float(w), 3), "weight_why": why, "base": config.AI["news_weight"],
            "event_risk": extra.get("event_risk", 0), "event": extra.get("event", ""), "lesson": extra.get("lesson", ""),
            "principle": extra.get("principle", ""), "analogue": extra.get("analogue", ""),
            "regime": reg_now, "regime_txt": REGIME_TXT.get(reg_now, ""), "favorites": fav, "timeline": timeline,
            "regime_memory": config.STRATEGY.get("regime_memory", True)}


def activate_profile():
    """Applique data/settings.json (onglet Réglages de l'appli) à la configuration."""
    prof = load_profile()
    strat, risk, paper, tradable, keys, aiw = apply_profile(prof)
    config.STRATEGY.update(strat)
    config.STRATEGY["strategies"] = keys
    config.STRATEGY["user_strategies"] = bool(prof.get("strategies"))
    import optimizer
    tun = optimizer.load()
    if tun:
        optimizer.apply(config.STRATEGY, tun)
        print("🎛️  réglage automatique du " + tun["date"] + " : " + tun["summary"])
    config.RISK.update(risk)
    config.PAPER.update(paper)
    config.TRADABLE[:] = tradable
    config.AI["news_weight"] = aiw
    config.PROFILE = prof
    try:                                                   # le labo décide si la mémoire des régimes aide vraiment
        with open("data/lab.json") as f:
            rt = json.load(f).get("regime_test")
        if rt:
            config.STRATEGY["regime_memory"] = bool(rt.get("use", True))
            print(f"🧪 mémoire des régimes {'activée' if rt['use'] else 'désactivée'} par le labo "
                  f"(Sharpe {rt['with']} avec, {rt['without']} sans)")
    except (OSError, ValueError):
        pass
    who = prof.get("user_name") or "profil par défaut"
    print(f"👤 {who} · profil {prof.get('risk_profile')} · {len(tradable)} actifs · {len(keys)} stratégies"
          + (f" · perte max/jour {prof['max_loss_day']} €" if prof.get("max_loss_day") else ""))
    return prof


def decide(prices, p, per_asset=None, nw=None, macro="", state=None, now=None):
    """Signaux du conseil + actu, poids cibles, puis gestion du risque."""
    syms = [s for s in config.TRADABLE if s in prices]
    ctx = build_context(prices[syms], p)
    held = {s: (1 if q > 0 else -1) for s, q in (state or {}).get("positions", {}).items() if q}
    signals = {}
    for sym in syms:
        s = explain(sym, config.UNIVERSE[sym], prices, p, (per_asset or {}).get(sym), nw, ctx=ctx,
                    held=sym in held)
        if s:
            s["macro"] = macro
            signals[sym] = s
    last_score = ctx["score"].iloc[[-1]].copy()
    for sym, s in signals.items():
        last_score[sym] = s["score"]
    target = weights_from_scores(last_score, ctx["vol"].iloc[[-1]], p, held=held,
                                 stress=ctx["stress"].iloc[[-1]]).iloc[-1].to_dict()
    import crisis, strategies as _st
    th = crisis.thermometer(prices)
    ctx["thermo"] = th
    for sym, s_ in signals.items():
        s_["patterns"] = _st.latest_patterns(sym, asof=prices.index[-1])
        for pt in s_["patterns"][:2]:
            if pt["dir"]:
                s_["reasons"].append(f"chandeliers : {pt['name'].lower()} {'il y a ' + str(pt['ago']) + ' j' if pt['ago'] else 'aujourd’hui'}")
    if th["scale"] < 1 and p.get("thermo", True):
        for k in target:
            target[k] *= th["scale"]
        for s_ in signals.values():
            s_["reasons"].append(f"thermomètre de crise {th['score']:.0f}/100 ({th['analogue']}) : exposition × {th['scale']:.2f}")
    raw = dict(target)
    sf = float(ctx["stress"].iloc[-1])
    if sf < 0.99:
        for s_ in signals.values():
            s_["reasons"].append(f"filtre de crise : marché très nerveux, exposition globale × {sf:.2f}")
    events, stops = [], {}
    if config.RISK.get("corr_adjust", True):
        target, events = corr_adjust(target, prices[syms], config.UNIVERSE, signals)
    after_corr = dict(target)
    if state is not None:
        target, ev2, stops = apply_risk(state, target, prices.iloc[-1].to_dict(),
                                        ctx["atr"].iloc[-1].to_dict(), signals, now, config.RISK,
                                        rets=prices[syms].pct_change())
        events = ev2 + events
    for sym, s in signals.items():               # trace complète pour le cockpit
        s["pipe"] = {"raw": raw.get(sym, 0.0), "corr": after_corr.get(sym, 0.0), "final": target.get(sym, 0.0)}
    return signals, target, events, stops, ctx


def tech_context(prices):
    """Résumé du thermomètre de crise et des figures de chandeliers pour le prompt de l'IA."""
    import crisis, strategies as _st
    th = crisis.thermometer(prices)
    lines = [f"Thermomètre de crise : {th['score']:.0f}/100 ({th['level']}), baisse du panier {th['drawdown']:+.1f} %, "
             f"vitesse 10 j {th['speed10']:+.1f} %, profil proche de : {th['analogue']}"]
    for s in config.TRADABLE:
        pts = [p for p in _st.latest_patterns(s) if p["dir"]]
        if pts:
            lines.append(f"{s} : " + ", ".join(f"{p['name']} ({'aujourd’hui' if not p['ago'] else 'il y a ' + str(p['ago']) + ' j'})" for p in pts))
    return "\n".join(lines)


def cmd_run(args):
    p, pp = config.STRATEGY, config.PAPER
    full = load_prices(args.demo, "5y")
    prices = full.iloc[-600:]
    prices.attrs["raw"] = full.attrs["raw"].iloc[-600:]
    news = [] if args.demo else get_news(config.NEWS_FEEDS)
    if args.demo:
        news = [{"title": t, "summary": "", "link": "", "source": "démo", "date": None} for t in [
            "Exemple : entrées record dans les ETF bitcoin",
            "Exemple : le pétrole recule sur des craintes d'offre excédentaire",
            "Exemple : la Fed laisse entendre une pause sur les taux",
            "Exemple : résultats des géants de la tech au-dessus des attentes",
            "Exemple : la BCE inquiète de la croissance en zone euro",
            "Exemple : l'or soutenu par les tensions géopolitiques"]]
    per_asset, macro, nw = news_by_asset(news, config.KEYWORDS), "", None
    ai = config.AI
    mem = ai_memory.load()
    ai_memory.score(mem, prices)
    rep = ai_memory.report(mem, config.UNIVERSE)
    reg_now = market_regimes(prices[[s for s in config.TRADABLE if s in prices]]).iloc[-1]
    ai_extra, nw_why = {}, ""
    if not ai["enabled"]:
        print("💤 Analyse IA Claude désactivée (option payante) : lecture de l'actu par mots-clés")
    if ai["enabled"] and (os.getenv("ANTHROPIC_API_KEY") or args.mock_ai):
        try:
            macro, per_asset, ai_extra = analyze(news, config.TRADABLE, config.UNIVERSE, prices,
                                                 ai["model"], ai["api_version"],
                                                 caller=_mock_ai if args.mock_ai else None,
                                                 bulletin=ai_memory.bulletin(rep), regime=REGIME_TXT[reg_now],
                                                 context=tech_context(prices))
            nw, nw_why = ai_memory.weight(rep, ai["news_weight"])
            ai_memory.record(mem, per_asset, prices, datetime.now())
            print(f"🧠 Analyse IA OK — {macro}")
            print(f"🧠 Poids de l'IA : {nw:.0%} ({nw_why})")
        except Exception as e:
            print(f"[IA] indisponible ({e}), retour à l'analyse par mots-clés")
    ai_memory.save(mem)

    health = data_health(full.attrs["raw"], config.TRADABLE)
    bad = [h["symbol"] for h in health if not h["ok"]]
    if bad and not args.demo:
        print("⚠️  données écartées ce passage : " + ", ".join(f"{h['symbol']} ({h['why']})" for h in health if not h["ok"]))
        config.TRADABLE[:] = [s for s in config.TRADABLE if s not in bad]
    state = load_state(pp["state_file"], pp["starting_cash"])
    signals, target, events, stops, ctx = decide(prices, p, per_asset, nw, macro, state)
    lvl = ai_extra.get("event_risk", 0) or 0
    if lvl >= 0.6:                                        # événement majeur imminent : on réduit la voilure
        f_ev = 1 - 0.4 * lvl
        for s_ in target:
            target[s_] *= f_ev
        txt = f"événement à risque ({ai_extra.get('event') or 'annonce majeure'}) : positions réduites à {f_ev:.0%}"
        events.insert(0, {"type": "event", "symbol": None, "text": txt})
        for sg in signals.values():
            sg["reasons"].append(txt)
    new_feed = build_feed(state, signals, events, stops, ctx, config.UNIVERSE)
    for e in new_feed:
        if e["level"] == "important" and e["kind"] not in ("risk:halt",):
            send_telegram(f"📡 M-TRADE — SIGNAL\n{e['title']}\n{e['text']}")
    for ev in events:
        print(f"🛡️  {ev['text']}")
        if ev["type"] == "halt":
            send_telegram(f"🛑 M-TRADE — GARDE-FOU\n{ev['text']}")
    last_px = prices.iloc[-1].to_dict()
    orders, value = rebalance(state, signals, target, last_px, pp["fee_rate"],
                              pp.get("min_trade_pct", 0.03))
    save_state(state, pp["state_file"])
    append_journal(orders, pp["journal_file"])
    score_snapshot(state, pp["journal_file"], prices, config, datetime.now())
    save_state(state, pp["state_file"])
    payload = build_payload(prices, signals, state, pp["journal_file"], news, macro, config,
                            ctx=ctx, events=events, stops=stops)
    payload["demo"] = bool(args.demo)
    payload["health"] = health
    payload["ai_report"] = ai_payload(mem, rep, nw, nw_why, ai_extra, reg_now, ctx)
    payload["feed"] = list(reversed(state.get("feed", [])))[:120]
    payload["thermo"] = ctx.get("thermo") if ctx else None
    payload["knowledge"] = knowledge.payload()
    import optimizer
    payload["tuning"] = optimizer.load()
    payload["options"] = [{**o, "enabled": (not o["paid"]) or bool(config.AI["enabled"])} for o in config.OPTIONS]
    payload["lab"] = lab_cached(full, [s for s in config.TRADABLE if s in full], p, pp["fee_rate"])
    path = write_dashboard(payload)
    print(f"🖥️  Interface mise à jour : {path}")

    if args.full:
        top_news = sorted(news, key=lambda n: abs(score_text(n["title"])), reverse=True)
        print(build_report(signals, orders, state, value, top_news))

    # Une alerte détaillée par ordre ; rien si le bot n'a rien fait
    for o in orders:
        msg = build_trade_alert(o, signals.get(o["symbol"], {}), state, value)
        print(msg + "\n" + "-" * 40)
        if config.PROFILE.get("notify_orders", True):
            send_telegram(msg)
    if not orders:
        print("Aucun ordre : positions inchangées.")

    # Bilan quotidien optionnel
    hour = pp.get("daily_summary_hour")
    now = datetime.now(ZoneInfo("Europe/Paris"))
    if hour is not None and now.hour == hour and state.get("last_summary") != now.date().isoformat():
        lead = max(ctx["weights"].iloc[-1].items(), key=lambda kv: kv[1])
        from strategies import NAMES
        extra = {"leader": f"{NAMES[lead[0]]} ({lead[1]:.0%} des voix)",
                 "breaker": state.get("breaker", {}), "events": events,
                 "lab": payload.get("lab"), "top": max(signals.values(), key=lambda s: s["score"])}
        msg = build_summary(state, value, last_px, config.UNIVERSE, extra)
        print(msg)
        send_telegram(msg)
        state["last_summary"] = now.date().isoformat()
        save_state(state, pp["state_file"])


def cmd_replay(args):
    """Rejoue la stratégie jour par jour sur les N derniers jours (technique seule, sans actu).
    Sert à démarrer l'interface avec un historique. Repart d'un portefeuille neuf."""
    p, pp = config.STRATEGY, config.PAPER
    for f in (pp["state_file"], pp["journal_file"]):
        if os.path.exists(f):
            os.remove(f)
    prices = load_prices(args.demo, "2y")
    state = load_state(pp["state_file"], pp["starting_cash"])
    syms = [s for s in config.TRADABLE if s in prices]
    days = prices.index[-args.days:]
    signals, events, stops, ctx = {}, [], {}, None
    demo_mem = []
    if os.path.exists(ai_memory.PATH):
        os.remove(ai_memory.PATH)
    for i, d in enumerate(days):
        hist = prices.loc[:d].iloc[-600:]
        when = d.to_pydatetime().replace(hour=18)
        signals, target, ev, stops, ctx = decide(hist, p, state=state, now=when)
        build_feed(state, signals, ev, stops, ctx, config.UNIVERSE, now=when)
        if args.demo and args.mock_ai:                    # appels d'IA fictifs pour illustrer le bulletin
            rng = np.random.default_rng(i)
            pa = {s_: {"impact": float(np.clip(rng.normal(0, 0.5), -1, 1)), "confidence": float(rng.uniform(0.3, 0.8)),
                       "ai_explanation": "appel d'exemple (démo)"} for s_ in ["^IXIC", "^FCHI", "GC=F", "BTC-USD", "CL=F"]}
            ai_memory.record(demo_mem, pa, hist, when)
        events = (ev + events)[:30]
        orders, value = rebalance(state, signals, target, hist.iloc[-1].to_dict(), pp["fee_rate"],
                                  pp.get("min_trade_pct", 0.03), now=d.to_pydatetime().replace(hour=18))
        append_journal(orders, pp["journal_file"])
        if i % 5 == 0 or i == len(days) - 1:
            score_snapshot(state, pp["journal_file"], hist, config, d.to_pydatetime().replace(hour=18))
    state["replayed"] = True
    save_state(state, pp["state_file"])
    print(f"Rejoué {len(days)} jours : {value:,.0f} € ({value / state['start_value'] - 1:+.2%})")
    payload = build_payload(prices, signals, state, pp["journal_file"], [], "", config,
                            ctx=ctx, events=events, stops=stops)
    payload["demo"] = bool(args.demo)
    payload["health"] = data_health(prices.attrs.get("raw", prices), config.TRADABLE, now=prices.index[-1])
    ai_memory.score(demo_mem, prices)
    ai_memory.save(demo_mem)
    rep = ai_memory.report(demo_mem, config.UNIVERSE)
    payload["ai_report"] = ai_payload(demo_mem, rep, None, "", {}, market_regimes(prices[syms]).iloc[-1], ctx)
    payload["feed"] = list(reversed(state.get("feed", [])))[:120]
    payload["thermo"] = ctx.get("thermo") if ctx else None
    payload["knowledge"] = knowledge.payload()
    import optimizer
    payload["tuning"] = optimizer.load()
    payload["options"] = [{**o, "enabled": (not o["paid"]) or bool(config.AI["enabled"])} for o in config.OPTIONS]
    payload["lab"] = lab_cached(prices, [s for s in config.TRADABLE if s in prices], p,
                                pp["fee_rate"], force=True)
    print(f"Interface : {write_dashboard(payload)}")


def cmd_status(args):
    pp = config.PAPER
    state = load_state(pp["state_file"], pp["starting_cash"])
    prices = load_prices(args.demo, "5d").iloc[-1].to_dict()
    v = portfolio_value(state, prices)
    print(f"Valeur : {v:,.2f} € ({v / state['start_value'] - 1:+.2%})")
    print(f"Liquidités : {state['cash']:,.2f} €")
    for s, q in state["positions"].items():
        print(f"  {config.UNIVERSE.get(s, s):16} {q:>12.4f}  ≈ {q * prices.get(s, 0):>10,.0f} €")


def cmd_tune(args):
    """Réglage automatique sur les vrais cours (une fois par semaine, ou --force)."""
    import optimizer
    if not args.force and not optimizer.due():
        print("🎛️  réglage automatique déjà fait cette semaine")
        return
    full = load_prices(args.demo, "5y")
    res = optimizer.tune(full, config.TRADABLE, dict(config.STRATEGY), config.PAPER["fee_rate"])
    if not res:
        print("🎛️  pas assez d'historique pour le réglage automatique")
        return
    optimizer.save(res)
    print("🎛️  " + res["summary"])
    print(f"   contrôle hors échantillon ({res['oos']['from']} → {res['oos']['to']}) : "
          f"Sharpe {res['oos']['chosen']} (sélection aveugle) contre {res['oos']['previous']} (avant) et {res['oos']['market']} (marché)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Bot d'analyse et de paper trading")
    ap.add_argument("command", choices=["backtest", "run", "status", "replay", "tune"])
    ap.add_argument("--demo", action="store_true", help="données simulées, sans internet")
    ap.add_argument("--mock-ai", action="store_true", help="simule la réponse de l'IA (test)")
    ap.add_argument("--days", type=int, default=120, help="jours à rejouer (replay)")
    ap.add_argument("--force", action="store_true", help="refaire le réglage automatique (tune)")
    ap.add_argument("--full", action="store_true", help="affiche aussi le rapport complet des signaux")
    a = ap.parse_args()
    activate_profile()
    {"backtest": cmd_backtest, "run": cmd_run, "status": cmd_status, "replay": cmd_replay, "tune": cmd_tune}[a.command](a)
