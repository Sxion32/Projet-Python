"""Test de faisabilité des sources de taux souverains à 10 ans.

Le script interroge chaque source et affiche ce qui est réellement disponible :
nombre d'observations, première et dernière date, valeurs manquantes par pays,
puis le contrôle de cohérence demandé : la moyenne mensuelle de chaque série
quotidienne doit retomber sur la série mensuelle de la BCE.

Sources :
1. Eurostat, série quotidienne irt_lt_mcby_d via l'API Eurostat, puis la copie
   de cette série conservée par DBnomics ;
2. BCE, jeu IRS mensuel, taux à long terme du critère de convergence ;
3. sources nationales quotidiennes : Banque de France (TEC 10, copie DBnomics),
   Bundesbank (rendement à 10 ans issu de la courbe des taux) et Banco de España
   (obligations de l'État à 10 ans, tableau TI 1.3).

Usage : python scripts/check_sources.py
"""

import csv
import io

import pandas as pd
import requests

START = "2018-01-01"
END = "2026-09-30"
COUNTRIES = ["DE", "FR", "IT", "ES", "PT", "BE", "NL"]
MIN_DAYS_PER_MONTH = 15  # un mois n'est comparé que s'il compte au moins 15 cotations

EUROSTAT_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
    "irt_lt_mcby_d?format=SDMX-CSV&startPeriod=2018-01-01"
)
DBNOMICS_URL = "https://api.db.nomics.world/v22/series/{series}?observations=1"
ECB_URL = (
    "https://data-api.ecb.europa.eu/service/data/IRS/"
    "M.{countries}.L.L40.CI.0000.EUR.N.Z?format=csvdata&startPeriod=2018-01"
)
BUNDESBANK_URL = (
    "https://www.bundesbank.de/statistic-rmi/StatisticDownload"
    "?tsId=BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A"
    "&its_csvFormat=en&its_fileFormat=csv&mode=its"
    f"&its_from={START}&its_to={END}"
)
BDE_URL = "https://www.bde.es/webbe/es/estadisticas/compartido/datos/csv/ti_1_3.csv"
BDE_MONTHS = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
              "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}


def fetch_eurostat_daily_status():
    """Interroge l'API Eurostat pour irt_lt_mcby_d ; renvoie le code HTTP et le début de la réponse."""
    response = requests.get(EUROSTAT_URL, timeout=60)
    return response.status_code, response.text[:160].replace("\n", " ")


def fetch_dbnomics_daily(series):
    """Télécharge une série quotidienne sur DBnomics et renvoie une Series datée.

    `series` est l'identifiant complet "fournisseur/jeu/code". Les jours sans
    valeur (week-ends, fériés) sont conservés comme NaN pour pouvoir les compter.
    """
    response = requests.get(DBNOMICS_URL.format(series=series), timeout=60)
    response.raise_for_status()
    doc = response.json()["series"]["docs"][0]
    values = pd.to_numeric(pd.Series(doc["value"]).replace("NA", None), errors="coerce")
    daily = pd.Series(values.values, index=pd.to_datetime(doc["period"]), name=series)
    return daily[START:END]


def fetch_ecb_monthly(countries):
    """Télécharge le taux à long terme mensuel de la BCE (jeu IRS) pour plusieurs pays.

    Renvoie un DataFrame (country, month, value), `month` au format AAAA-MM.
    """
    response = requests.get(ECB_URL.format(countries="+".join(countries)), timeout=60)
    response.raise_for_status()
    raw = pd.read_csv(io.StringIO(response.text), usecols=["REF_AREA", "TIME_PERIOD", "OBS_VALUE"])
    return raw.rename(columns={"REF_AREA": "country", "TIME_PERIOD": "month", "OBS_VALUE": "value"})


def fetch_bundesbank_daily():
    """Télécharge le rendement quotidien à 10 ans des titres fédéraux (Bundesbank).

    Le CSV commence par des lignes de métadonnées, puis donne une ligne par jour
    civil avec "." quand il n'y a pas de cotation. Renvoie une Series datée avec NaN.
    """
    response = requests.get(BUNDESBANK_URL, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    rows = [line.split(",")[:2] for line in response.text.splitlines() if line[:4].isdigit()]
    table = pd.DataFrame(rows, columns=["date", "value"])
    values = pd.to_numeric(table["value"].replace(".", None), errors="coerce")
    return pd.Series(values.values, index=pd.to_datetime(table["date"]), name="Bundesbank")


def fetch_bde_daily():
    """Télécharge le taux quotidien à 10 ans des obligations de l'État espagnol (Banco de España).

    Le tableau TI 1.3 regroupe plusieurs séries en colonnes, précédées de lignes
    de métadonnées ; la colonne utile est repérée par sa description. Les dates
    s'écrivent avec un mois abrégé en espagnol ("30 SEP 2026") et "_" signale
    l'absence de valeur. Renvoie une Series datée avec NaN.
    """
    response = requests.get(BDE_URL, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    rows = list(csv.reader(io.StringIO(response.content.decode("latin-1"))))
    descriptions = next(r for r in rows if r and r[0].startswith("DESCRIPCIÓN DE LA SERIE"))
    column = next(i for i, d in enumerate(descriptions) if "10 Años" in d and "obligaciones" in d.lower())
    data = [r for r in rows if r and r[0][:1].isdigit()]
    dates = []
    for row in data:
        day, month, year = row[0].split()
        dates.append(f"{year}-{BDE_MONTHS[month.upper()]:02d}-{int(day):02d}")
    values = pd.to_numeric(pd.Series([r[column] for r in data]).replace({"_": None, "": None}), errors="coerce")
    daily = pd.Series(values.values, index=pd.to_datetime(dates), name="Banco de España").sort_index()
    return daily[START:END]


def describe_daily(label, daily):
    """Affiche effectif, dates extrêmes et jours ouvrés sans valeur d'une série quotidienne."""
    valid = daily.dropna()
    if valid.empty:
        print(f"{label:<24} aucune valeur")
        return
    weekdays = daily[daily.index.dayofweek < 5]
    covers_end = "oui" if valid.index.max() >= pd.Timestamp(END) else "non"
    print(
        f"{label:<24} n={len(valid):5d}  {valid.index.min().date()} -> {valid.index.max().date()}  "
        f"jours ouvrés sans valeur={int(weekdays.isna().sum()):3d}  couvre {END} : {covers_end}"
    )


def compare_with_ecb(daily, ecb_country):
    """Compare la moyenne mensuelle d'une série quotidienne à la série mensuelle de la BCE.

    Seuls les mois comptant au moins MIN_DAYS_PER_MONTH cotations sont comparés.
    Renvoie (mois comparés, écart absolu moyen, écart absolu maximal) en points de %.
    """
    valid = daily.dropna()
    monthly = valid.groupby(valid.index.strftime("%Y-%m")).agg(["mean", "count"])
    monthly = monthly[monthly["count"] >= MIN_DAYS_PER_MONTH]
    merged = monthly.join(ecb_country.set_index("month")["value"], how="inner")
    gap = (merged["mean"] - merged["value"]).abs()
    return len(merged), gap.mean(), gap.max()


def main():
    print(f"Période visée : {START} -> {END}\n")

    print("=== 1. Eurostat : série quotidienne irt_lt_mcby_d via l'API Eurostat ===")
    status, message = fetch_eurostat_daily_status()
    print(f"HTTP {status} : {message}\n")

    print("=== 2. BCE : jeu IRS mensuel, taux à long terme du critère de convergence ===")
    ecb = fetch_ecb_monthly(COUNTRIES)
    for country in COUNTRIES:
        part = ecb[ecb["country"] == country]
        print(f"{country}  n={len(part):4d}  {part['month'].min()} -> {part['month'].max()}  NA={int(part['value'].isna().sum())}")

    print("\n=== 3. Copie DBnomics de la série quotidienne Eurostat ===")
    checks = []
    for country in COUNTRIES:
        daily = fetch_dbnomics_daily(f"Eurostat/IRT_LT_MCBY_D/D.MCBY.{country}")
        describe_daily(f"Eurostat {country}", daily)
        checks.append(("Eurostat via DBnomics", country, *compare_with_ecb(daily, ecb[ecb["country"] == country])))

    print("\n=== 4. Sources nationales quotidiennes ===")
    tec10 = fetch_dbnomics_daily("BDF/FM/D.FR.EUR.FR2.BB.FRMOYTEC10.HSTA")
    describe_daily("Banque de France TEC 10", tec10)
    checks.append(("Banque de France TEC 10", "FR", *compare_with_ecb(tec10, ecb[ecb["country"] == "FR"])))
    bund = fetch_bundesbank_daily()
    describe_daily("Bundesbank 10 ans", bund)
    checks.append(("Bundesbank 10 ans", "DE", *compare_with_ecb(bund, ecb[ecb["country"] == "DE"])))
    bde = fetch_bde_daily()
    describe_daily("Banco de España 10 ans", bde)
    checks.append(("Banco de España 10 ans", "ES", *compare_with_ecb(bde, ecb[ecb["country"] == "ES"])))

    print("\n=== 5. Contrôle : moyenne mensuelle du quotidien contre série mensuelle BCE (points de %) ===")
    table = pd.DataFrame(checks, columns=["source", "pays", "mois comparés", "écart abs. moyen", "écart abs. max"])
    print(table.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
