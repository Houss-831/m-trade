"""Encyclopédie M-TRADE : la culture de trader du bot.

Chaque notion comporte une explication et une règle actionnable.
- L'IA reçoit les règles condensées (rules_for_ai) à chaque analyse.
- L'assistant de l'appli reçoit l'encyclopédie pour répondre et enseigner.
- L'appli l'affiche dans l'onglet Savoir.
Les dates et chiffres historiques sont des repères arrondis.
"""

EPISODES = [
    {"year": "1602", "name": "Naissance de la Bourse", "where": "Amsterdam",
     "what": "La Compagnie néerlandaise des Indes orientales émet les premières actions librement échangeables.",
     "lesson": "Une action est une part d'entreprise : sur le long terme, son prix suit les bénéfices."},
    {"year": "1637", "name": "Tulipomanie", "where": "Provinces-Unies",
     "what": "Les bulbes de tulipe atteignent des prix extravagants, puis le marché s'effondre en quelques semaines.",
     "lesson": "Quand tout le monde achète parce que « ça monte », le prix ne repose plus sur rien."},
    {"year": "1720", "name": "Bulle des mers du Sud et système de Law", "where": "Londres et Paris",
     "what": "Deux bulles spéculatives éclatent la même année, ruinant épargnants et institutions.",
     "lesson": "Le crédit facile et les promesses de richesse rapide gonflent les bulles."},
    {"year": "1929", "name": "Le grand krach", "where": "New York",
     "what": "Krach d'octobre 1929. Le Dow Jones perd près de 90 % entre 1929 et 1932, sur fond de spéculation à crédit.",
     "lesson": "L'effet de levier transforme une baisse en catastrophe. Ne jamais être forcé de vendre."},
    {"year": "1973", "name": "Choc pétrolier", "where": "Monde",
     "what": "L'embargo pétrolier quadruple le prix du brut. Inflation forte et marché baissier en 1973-1974.",
     "lesson": "L'inflation et la hausse des taux pèsent sur les actions ; les matières premières montent."},
    {"year": "1987", "name": "Lundi noir", "where": "Monde",
     "what": "Le 19 octobre 1987, le Dow Jones perd environ 22 % en une seule séance, amplifié par des ventes automatiques.",
     "lesson": "Les stratégies automatiques identiques peuvent toutes vendre en même temps : la liquidité disparaît."},
    {"year": "1998", "name": "Faillite de LTCM", "where": "États-Unis",
     "what": "Un fonds dirigé par des prix Nobel, très endetté, s'effondre quand des corrélations jugées impossibles se produisent.",
     "lesson": "Les modèles calibrés sur le passé sous-estiment les événements extrêmes. Le levier tue."},
    {"year": "2000", "name": "Bulle Internet", "where": "Nasdaq",
     "what": "Le Nasdaq atteint un sommet en mars 2000, puis perd près de 80 % jusqu'en 2002.",
     "lesson": "Un secteur révolutionnaire peut quand même être une mauvaise affaire au mauvais prix."},
    {"year": "2008", "name": "Crise financière", "where": "Monde",
     "what": "Faillite de Lehman Brothers en septembre 2008. Le S&P 500 perd plus de 50 % entre 2007 et 2009.",
     "lesson": "En crise, presque tous les actifs risqués baissent ensemble : la diversification s'évapore."},
    {"year": "2009", "name": "Naissance du Bitcoin", "where": "Internet",
     "what": "Premier bloc de la chaîne Bitcoin, en janvier 2009, en pleine crise bancaire.",
     "lesson": "Nouvelle classe d'actifs, extrêmement volatile : la taille des positions doit en tenir compte."},
    {"year": "2010", "name": "Flash crash", "where": "États-Unis",
     "what": "Le 6 mai 2010, les indices plongent puis remontent en quelques minutes.",
     "lesson": "Les ordres au marché peuvent être exécutés à des prix absurdes quand la liquidité disparaît."},
    {"year": "2020", "name": "Krach du Covid", "where": "Monde",
     "what": "Le S&P 500 perd environ un tiers en un mois, la chute la plus rapide de l'histoire, puis rebondit sous l'effet des banques centrales.",
     "lesson": "Les krachs éclair sont suivis de rebonds violents : réduire le risque sans tout vendre au plus bas."},
    {"year": "2022", "name": "Retour de l'inflation", "where": "Monde",
     "what": "Hausse rapide des taux de la Fed. Le Nasdaq perd environ un tiers sur l'année ; effondrement de Terra/Luna puis de FTX dans la crypto.",
     "lesson": "Quand les taux montent vite, les actifs de croissance et la crypto souffrent le plus. Le risque de contrepartie existe."},
    {"year": "2024", "name": "ETF Bitcoin au comptant", "where": "États-Unis",
     "what": "Autorisation des ETF Bitcoin au comptant en janvier 2024, ouvrant la crypto aux grands investisseurs.",
     "lesson": "Les flux institutionnels deviennent un moteur majeur des prix de la crypto."},
]

CHAPTERS = [
    {"id": "technique", "title": "Analyse technique", "icon": "candle", "notions": [
        {"name": "Tendance", "text": "Une suite de plus hauts et de plus bas croissants (haussière) ou décroissants (baissière). Les moyennes mobiles 50 et 200 jours la résument.",
         "rule": "Ne pas acheter contre une tendance baissière de fond sans signal de retournement confirmé."},
        {"name": "Supports et résistances", "text": "Des niveaux où le prix a souvent rebondi ou buté, parce que beaucoup d'acheteurs ou de vendeurs s'y trouvent.",
         "rule": "Une cassure franche d'une résistance avec du volume est un signal ; un échec sous la résistance en est un autre."},
        {"name": "Momentum", "text": "Ce qui a monté récemment tend à continuer à monter pendant quelques mois. C'est l'une des anomalies les plus documentées.",
         "rule": "Favoriser les actifs les plus forts sur 3 à 12 mois, couper les plus faibles."},
        {"name": "RSI", "text": "Indice de force relative de Wilder (1978), entre 0 et 100. Au-dessus de 70 : suracheté ; sous 30 : survendu.",
         "rule": "En tendance forte, un RSI élevé peut durer : l'utiliser surtout pour acheter les replis dans le sens de la tendance."},
        {"name": "MACD", "text": "Écart entre deux moyennes exponentielles (12 et 26), comparé à sa moyenne sur 9. Mesure l'accélération.",
         "rule": "Un croisement du MACD dans le sens de la tendance de fond est plus fiable qu'à contre-tendance."},
        {"name": "ATR et volatilité", "text": "L'ATR mesure l'amplitude moyenne d'une journée. La volatilité varie par phases : calme puis agitée.",
         "rule": "Placer les stops en multiples d'ATR et réduire la taille quand la volatilité monte."},
        {"name": "Bandes de Bollinger", "text": "Moyenne 20 jours plus ou moins 2 écarts-types. Les bandes se resserrent avant les grands mouvements.",
         "rule": "En marché sans tendance, vendre près de la bande haute et acheter près de la basse ; en tendance, s'abstenir."},
        {"name": "Volume", "text": "Le volume confirme les mouvements : une hausse sur fort volume est plus solide qu'une hausse sans volume.",
         "rule": "Se méfier des cassures sans augmentation de volume."},
        {"name": "Chandeliers japonais", "text": "Inventés par Munehisa Homma au XVIIIe siècle sur le marché du riz, popularisés par Steve Nison en 1991. Marteau, étoile filante, avalement, étoile du matin et du soir, trois soldats blancs.",
         "rule": "Une figure de retournement ne compte qu'au bon endroit : après une vraie tendance, de préférence sur un support ou une résistance."},
        {"name": "Divergences", "text": "Le prix fait un nouveau sommet mais le RSI ou le MACD non : l'élan s'essouffle.",
         "rule": "Une divergence prévient, elle ne déclenche pas : attendre une cassure pour agir."},
    ]},
    {"id": "macro", "title": "Macroéconomie et banques centrales", "icon": "globe", "notions": [
        {"name": "Taux directeurs", "text": "La Fed et la BCE fixent le coût de l'argent. Des taux qui montent rendent l'épargne plus attractive et pèsent sur les actifs risqués.",
         "rule": "Un ton plus restrictif que prévu : prudence sur Nasdaq, crypto et or. Plus accommodant : soutien."},
        {"name": "Inflation", "text": "La hausse des prix (CPI aux États-Unis) pousse les banques centrales à monter les taux.",
         "rule": "Une inflation au-dessus des attentes est négative pour les actions et les obligations à court terme."},
        {"name": "Emploi", "text": "Le rapport sur l'emploi américain (NFP), le premier vendredi du mois, fait souvent bouger tous les marchés.",
         "rule": "Réduire la taille avant les grandes publications, ne pas parier sur leur résultat."},
        {"name": "Courbe des taux", "text": "Quand les taux courts dépassent les taux longs (courbe inversée), une récession a souvent suivi, avec un délai variable.",
         "rule": "Signal d'alerte de long terme, pas un signal de vente immédiat."},
        {"name": "Cycle économique", "text": "Reprise, expansion, ralentissement, récession : chaque phase favorise des actifs différents (actions cycliques, matières premières, obligations, liquidités).",
         "rule": "Adapter l'exposition au régime plutôt que de chercher le point bas exact."},
        {"name": "Liquidité", "text": "Quand les banques centrales injectent de la liquidité (QE), les actifs risqués montent souvent avec retard ; quand elles la retirent, ils souffrent.",
         "rule": "Surveiller la direction de la liquidité mondiale, surtout pour la crypto."},
    ]},
    {"id": "intermarche", "title": "Intermarché", "icon": "layers", "notions": [
        {"name": "Dollar", "text": "Un dollar fort pèse sur l'or, les matières premières, la crypto et les marchés émergents.",
         "rule": "Une hausse rapide du dollar invite à réduire ces actifs."},
        {"name": "Taux longs", "text": "Le rendement à 10 ans américain sert de référence pour valoriser tous les actifs.",
         "rule": "Une hausse rapide des taux longs pèse d'abord sur le Nasdaq et les valeurs de croissance."},
        {"name": "Valeurs refuges", "text": "En cas de peur, l'or, le dollar, le yen et les obligations d'État montent ; actions et crypto baissent.",
         "rule": "Quand l'or et le yen montent ensemble pendant que les actions baissent, le marché a peur."},
        {"name": "Pétrole", "text": "Un pétrole en forte hausse nourrit l'inflation et freine la croissance, sauf pour le secteur de l'énergie.",
         "rule": "Un choc pétrolier est négatif pour les indices larges."},
        {"name": "Corrélations", "text": "Les corrélations changent avec le temps et montent fortement en crise.",
         "rule": "Quand tous les actifs bougent ensemble, la diversification ne protège plus : réduire l'exposition totale."},
    ]},
    {"id": "risque", "title": "Gestion du risque", "icon": "shield", "notions": [
        {"name": "Mathématique des pertes", "text": "Perdre 50 % exige ensuite +100 % pour revenir à zéro. Perdre 20 % exige +25 %.",
         "rule": "Éviter les grosses pertes compte plus que de chercher les gros gains."},
        {"name": "Taille de position", "text": "Risquer une petite fraction fixe du capital par opération (souvent 0,5 à 2 %), calculée entre l'entrée et le stop.",
         "rule": "La taille se décide par le stop et la volatilité, jamais par l'envie."},
        {"name": "Critère de Kelly", "text": "John Kelly (1956) : la mise optimale dépend de l'avantage réel. Miser plus que Kelly mène à la ruine, même avec un avantage.",
         "rule": "Utiliser au plus une demi-mise de Kelly, et seulement avec un avantage prouvé."},
        {"name": "Espérance", "text": "Gain moyen × taux de réussite − perte moyenne × taux d'échec − frais. Un taux de réussite élevé ne suffit pas.",
         "rule": "Ne garder que les stratégies à espérance positive après frais."},
        {"name": "Value at Risk", "text": "Popularisée par RiskMetrics (1994) : la perte qu'on ne devrait dépasser qu'une fois sur 20, par exemple.",
         "rule": "Dimensionner pour qu'une mauvaise journée reste dans le budget de perte."},
        {"name": "Drawdown", "text": "La baisse depuis le plus haut. C'est elle qui fait abandonner les stratégies.",
         "rule": "Réduire l'exposition quand le drawdown s'aggrave (disjoncteur)."},
        {"name": "Sur-ajustement", "text": "Une stratégie trop réglée sur le passé échoue sur l'avenir.",
         "rule": "Toujours valider sur des données jamais vues avant de faire confiance."},
    ]},
    {"id": "psychologie", "title": "Psychologie et finance comportementale", "icon": "chat", "notions": [
        {"name": "Aversion aux pertes", "text": "Kahneman et Tversky (1979) : une perte fait environ deux fois plus mal qu'un gain du même montant ne fait plaisir.",
         "rule": "Suivre les règles fixées à l'avance plutôt que l'émotion du moment."},
        {"name": "Effet de disposition", "text": "On vend trop tôt ce qui gagne et on garde trop longtemps ce qui perd.",
         "rule": "Couper les pertes vite, laisser courir les gains (stops suiveurs)."},
        {"name": "Peur de rater (FOMO)", "text": "Acheter parce que tout le monde gagne, souvent près des sommets.",
         "rule": "Ne jamais entrer sans signal ni stop, même si le marché s'envole."},
        {"name": "Trading de revanche", "text": "Après une perte, prendre plus de risque pour se refaire.",
         "rule": "Après une série de pertes, devenir plus exigeant, pas plus agressif."},
        {"name": "Excès de confiance", "text": "Surestimer sa capacité à prévoir, surtout après quelques succès.",
         "rule": "Mesurer ses prévisions et ajuster sa confiance à ses résultats réels."},
        {"name": "Sentiment extrême", "text": "L'euphorie générale précède souvent les baisses, la peur extrême les rebonds.",
         "rule": "Être plus prudent quand tout le monde est acheteur, plus attentif aux opportunités en pleine panique."},
    ]},
    {"id": "academique", "title": "Découvertes académiques", "icon": "book", "notions": [
        {"name": "Marchés efficients", "text": "Eugene Fama (1970) : les prix intègrent vite l'information publique. Battre le marché durablement est difficile.",
         "rule": "Exiger une preuve statistique avant de croire à un avantage."},
        {"name": "Diversification", "text": "Harry Markowitz (1952) : combiner des actifs peu corrélés réduit le risque.",
         "rule": "Limiter le poids de chaque pari et tenir compte des corrélations."},
        {"name": "Momentum", "text": "Jegadeesh et Titman (1993) ; momentum temporel de Moskowitz, Ooi et Pedersen (2012), observé sur un siècle.",
         "rule": "Le momentum fonctionne en moyenne mais subit des krachs brutaux lors des retournements."},
        {"name": "Value et taille", "text": "Fama et French (1992) : les actions bon marché et les petites capitalisations ont historiquement rapporté plus, avec de longues périodes de sous-performance.",
         "rule": "Une anomalie connue peut disparaître ou s'affaiblir."},
        {"name": "Anomalie de la faible volatilité", "text": "Les actifs les moins volatils ont souvent offert un meilleur rendement ajusté du risque.",
         "rule": "Ne pas confondre volatilité et rendement espéré."},
        {"name": "Dérive post-résultats", "text": "Après une surprise de résultats, le cours continue souvent dans le même sens pendant des semaines (Ball et Brown, 1968).",
         "rule": "Une surprise forte et durable compte plus que le chiffre brut."},
    ]},
    {"id": "crypto", "title": "Crypto-actifs", "icon": "coins", "notions": [
        {"name": "Volatilité", "text": "Bitcoin varie souvent 3 à 4 fois plus que les grands indices boursiers.",
         "rule": "Positions plus petites et stops plus larges en ATR."},
        {"name": "Halving", "text": "Tous les 4 ans environ (2012, 2016, 2020, 2024), la création de nouveaux bitcoins est divisée par deux.",
         "rule": "Thème de long terme, sans valeur pour prévoir les prochains jours."},
        {"name": "Lien avec le Nasdaq", "text": "Depuis 2020, la crypto évolue souvent comme les actions technologiques, surtout en période de stress.",
         "rule": "Ne pas compter sur la crypto pour diversifier un portefeuille d'actions technologiques."},
        {"name": "Risque de plateforme", "text": "Mt. Gox (2014), FTX (2022) : des plateformes peuvent faire faillite avec les fonds des clients.",
         "rule": "Le risque de contrepartie s'ajoute au risque de prix."},
        {"name": "Marché 24 h/24", "text": "La crypto cote en continu, y compris le week-end, souvent avec moins de liquidité.",
         "rule": "Prévoir des stops et des tailles adaptés aux mouvements nocturnes et de week-end."},
    ]},
    {"id": "matieres", "title": "Matières premières", "icon": "flame", "notions": [
        {"name": "Or", "text": "Monte souvent avec la peur, la baisse des taux réels et la faiblesse du dollar.",
         "rule": "Surveiller les taux réels et le dollar pour juger l'or."},
        {"name": "Pétrole et OPEP", "text": "L'offre est influencée par les décisions de l'OPEP+ et la géopolitique ; la demande par la croissance mondiale.",
         "rule": "Les décisions de l'OPEP+ et les conflits au Moyen-Orient sont des événements à risque."},
        {"name": "Contrats à terme", "text": "Les matières premières se traitent souvent en contrats à terme, dont le prix peut différer du comptant (contango, backwardation).",
         "rule": "Le rendement d'un contrat à terme ne suit pas toujours le prix au comptant."},
    ]},
    {"id": "microstructure", "title": "Exécution et microstructure", "icon": "zap", "notions": [
        {"name": "Spread et glissement", "text": "L'écart entre prix d'achat et de vente, plus le glissement à l'exécution, s'ajoutent aux frais.",
         "rule": "Plus on trade souvent, plus les coûts cachés comptent : viser des objectifs plusieurs fois supérieurs aux frais."},
        {"name": "Ordres au marché et à cours limité", "text": "Un ordre au marché s'exécute tout de suite à n'importe quel prix ; un ordre limité fixe le prix maximal ou minimal.",
         "rule": "En marché agité ou peu liquide, préférer les ordres limités."},
        {"name": "Gaps", "text": "Écart entre la clôture et l'ouverture suivante, souvent après une nouvelle importante.",
         "rule": "Un stop ne protège pas d'un gap : la taille de position est la vraie protection."},
        {"name": "Effets de calendrier", "text": "Effet janvier, fin de mois, « sell in May » : des effets faibles et instables dans le temps.",
         "rule": "Ne jamais trader sur un effet de calendrier seul."},
    ]},
]


def rules_for_ai(max_per_chapter=4):
    """Règles condensées pour le prompt de l'IA."""
    out = []
    for ch in CHAPTERS:
        out.append(f"[{ch['title']}] " + " ".join(n["rule"] for n in ch["notions"][:max_per_chapter]))
    return "\n".join(out)


def episode_lessons():
    return "\n".join(f"{e['year']} {e['name']} : {e['lesson']}" for e in EPISODES)


def payload():
    return {"chapters": CHAPTERS, "episodes": EPISODES,
            "count": sum(len(c["notions"]) for c in CHAPTERS) + len(EPISODES)}
