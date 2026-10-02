"""Test de faisabilité des trois sources de données du projet.

Le script interroge chaque source et affiche ce qui est réellement disponible
(nombre d'observations, première et dernière date, valeurs manquantes) :

1. l'API du ECB Data Portal (taux de la facilité de dépôt, niveau et variation) ;
2. les dates des réunions de politique monétaire, lues dans les listes annuelles
   de communiqués du site de la BCE ;
3. les cours quotidiens via yfinance (indices sectoriels STOXX, banques, ETF).

Usage : python scripts/check_sources.py
"""

import io
import logging
import re

import pandas as pd
import requests
import yfinance as yf

START = "2021-12-01"  # un mois de marge avant la fenêtre d'étude 2022-2026
YEARS = range(2022, 2027)

ECB_API = (
    "https://data-api.ecb.europa.eu/service/data/FM/"
    "B.U2.EUR.4F.KR.DFR.{suffix}?format=csvdata"
)
ECB_PRESS_INDEX = "https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html"

# Indices sectoriels STOXX Europe 600 (symboles Yahoo supposés) et deux indices
# témoins dont on sait qu'ils existent sur Yahoo.
SECTOR_INDICES = ["^SX7P", "^SX8P", "^SX6P", "^SX86P", "^STOXX", "^STOXX50E"]

BANKS = ["BNP.PA", "GLE.PA", "ACA.PA", "DBK.DE", "SAN.MC", "ISP.MI", "UCG.MI", "INGA.AS"]

# ETF iShares STOXX Europe 600 sectoriels cotés sur Xetra (suffixe .DE sur Yahoo).
# Le libellé est celui renvoyé par Yahoo, vérifié ticker par ticker.
ETFS = {
    "EXSA.DE": "STOXX Europe 600 (indice large, référence)",
    "EXV1.DE": "Banks",
    "EXX1.DE": "EURO STOXX Banks (zone euro seulement)",
    "EXH2.DE": "Financial Services",
    "EXH5.DE": "Insurance",
    "EXI5.DE": "Real Estate",
    "EXH9.DE": "Utilities",
    "EXV3.DE": "Technology",
    "EXV2.DE": "Telecommunications",
    "EXV4.DE": "Health Care",
    "EXH3.DE": "Food & Beverage",
    "EXH7.DE": "Personal & Household Goods",
    "EXH1.DE": "Oil & Gas",
    "EXV5.DE": "Automobiles & Parts",
    "EXH4.DE": "Industrial Goods & Services",
    "EXV6.DE": "Basic Resources",
    "EXV7.DE": "Chemicals",
    "EXV8.DE": "Construction & Materials",
    "EXV9.DE": "Travel & Leisure",
    "EXH6.DE": "Media",
    "EXH8.DE": "Retail",
}


def fetch_ecb_series(suffix):
    """Télécharge une série de l'API BCE et renvoie un DataFrame (date, valeur).

    `suffix` vaut "LEV" (niveau du taux) ou "CHG" (variation en points de %).
    """
    response = requests.get(ECB_API.format(suffix=suffix), timeout=60)
    response.raise_for_status()
    raw = pd.read_csv(io.StringIO(response.text), usecols=["TIME_PERIOD", "OBS_VALUE"])
    return pd.DataFrame(
        {"date": pd.to_datetime(raw["TIME_PERIOD"]), "value": raw["OBS_VALUE"]}
    )


def describe_dates(label, dates, n_missing):
    """Affiche une ligne de synthèse : effectif, première et dernière date, NA."""
    print(
        f"{label:<42} n={len(dates):5d}  "
        f"{min(dates).date()} -> {max(dates).date()}  NA={n_missing}"
    )


def fetch_meeting_dates(years):
    """Renvoie les dates d'annonce des décisions de politique monétaire.

    La page d'index charge dynamiquement des fragments annuels dont les URL
    sont listées dans l'attribut `data-snippets`. Chaque fragment est du HTML
    statique où les communiqués de décision ont une URL de la forme
    `ecb.mpAAMMJJ` ; la date d'annonce est lue directement dans cette URL.
    """
    index_html = requests.get(ECB_PRESS_INDEX, timeout=60).text
    snippets = re.search(r"data-snippets='([^']+)'", index_html).group(1).split(",")
    dates = set()
    for year in years:
        path = next(s for s in snippets if f"/{year}/" in s)  # "../2024/html/index_include.en.html"
        url = ECB_PRESS_INDEX.rsplit("/", 2)[0] + path.lstrip(".")
        html = requests.get(url, timeout=60).text
        for yymmdd in re.findall(r"ecb\.mp(\d{6})", html):
            dates.add(pd.to_datetime(yymmdd, format="%y%m%d"))
    return sorted(dates)


def describe_prices(label, tickers):
    """Télécharge les cours et affiche, par ticker, la couverture réelle.

    Pour chaque ticker : nombre de clôtures valides, première et dernière date,
    NA à l'intérieur de cette plage et jours à volume nul (séances sans échange,
    signe d'un ETF peu liquide dont la clôture peut être peu informative).
    Le téléchargement groupé aligne tous les tickers sur l'union des calendriers
    de bourse : un NA signale donc le plus souvent un jour férié local (par
    exemple Francfort fermé alors que Paris est ouvert), pas une donnée perdue.
    """
    print(f"\n--- {label} ---")
    data = yf.download(tickers, start=START, auto_adjust=False, progress=False)
    for ticker in tickers:
        close = data["Close"].get(ticker)
        if close is None or close.notna().sum() == 0:
            print(f"{ticker:<10} ABSENT de Yahoo Finance")
            continue
        close = close.loc[close.first_valid_index(): close.last_valid_index()]
        volume = data["Volume"][ticker].reindex(close.index)
        print(
            f"{ticker:<10} n={close.notna().sum():5d}  "
            f"{close.index.min().date()} -> {close.index.max().date()}  "
            f"NA_calendrier_commun={close.isna().sum()}  volume_nul={(volume == 0).sum()}"
        )


def main():
    print("=== 1. API BCE : taux de la facilité de dépôt (dates d'entrée en vigueur) ===")
    level = fetch_ecb_series("LEV")
    change = fetch_ecb_series("CHG")
    describe_dates("DFR niveau (LEV), série complète", level["date"], level["value"].isna().sum())
    describe_dates("DFR variation (CHG), série complète", change["date"], change["value"].isna().sum())
    change_window = change[change["date"] >= "2022-01-01"]
    describe_dates("DFR variation, fenêtre 2022-2026", change_window["date"], change_window["value"].isna().sum())

    print("\n=== 2. Site BCE : dates d'annonce des décisions (communiqués ecb.mpAAMMJJ) ===")
    meetings = fetch_meeting_dates(YEARS)
    describe_dates("Réunions de politique monétaire", meetings, 0)
    per_year = pd.Series([d.year for d in meetings]).value_counts().sort_index()
    print("Réunions par an :", per_year.to_dict())
    # Contrôle de cohérence : depuis 2022 une décision annoncée un jeudi entre en
    # vigueur le mercredi suivant, soit 6 jours plus tard.
    announced = {d + pd.Timedelta(days=6) for d in meetings}
    matched = change_window["date"].isin(announced).sum()
    print(
        f"Variations de taux 2022-2026 : {len(change_window)}, "
        f"dont {matched} précédées d'une réunion exactement 6 jours avant"
    )

    print("\n=== 3. yfinance : cours quotidiens ===")
    describe_prices("Indices sectoriels STOXX (symboles Yahoo)", SECTOR_INDICES)
    describe_prices("Grandes banques de la zone euro", BANKS)
    describe_prices("ETF iShares STOXX Europe 600 sectoriels (Xetra)", list(ETFS))


if __name__ == "__main__":
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)  # masque les avertissements des tickers absents
    main()
