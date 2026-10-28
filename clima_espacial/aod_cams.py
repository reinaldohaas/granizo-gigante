"""
Aerossol (CAMS, Copernicus ADS) em torno do granizo de Florianopolis (29/08/2026).

Alternativa ao MERRA-2 (aod_merra2.py) quando a credencial Earthdata falha.
Mesma ideia do projeto do RS (clima_espacial_amas/scripts/02_baixar_cams_aod.py):
fumaca = materia organica + carbono negro; o que importa e a anomalia relativa.

1) Serie diaria 2026: CAMS global atmospheric composition forecasts, passo 0
   (analise) as 00 e 12 UTC, --ini a --fim.
2) Climatologia de agosto: CAMS EAC4 monthly averaged, 2003 ate o ultimo ano
   disponivel. Atencao: a analise operacional (1) e a reanalise (2) sao sistemas
   diferentes; a comparacao entre as duas e indicativa, nao exata.

Credencial: ~/.adsapirc (url do ADS + key). Uso:
    python clima_espacial/aod_cams.py --ini 2026-08-10 --fim 2026-09-05
"""
import argparse
import pathlib

import cdsapi
import pandas as pd
import xarray as xr

AQUI = pathlib.Path(__file__).resolve().parent
DADOS = AQUI / "dados" / "cams"
AREA = [2, -70, -30, -46]  # N, W, S, E
CAIXAS = {"sc": (-29.5, -25.5, -54.0, -47.5),
          "corredor": (-30.0, -22.0, -60.0, -50.0),
          "fogo": (-20.0, 2.0, -70.0, -50.0)}
VARS = ["total_aerosol_optical_depth_550nm",
        "organic_matter_aerosol_optical_depth_550nm",
        "black_carbon_aerosol_optical_depth_550nm",
        "sulphate_aerosol_optical_depth_550nm",
        "dust_aerosol_optical_depth_550nm",
        "sea_salt_aerosol_optical_depth_550nm"]


def cliente():
    url, key = None, None
    for l in (pathlib.Path.home() / ".adsapirc").read_text().splitlines():
        if l.startswith("url:"):
            url = l.split(":", 1)[1].strip()
        if l.startswith("key:"):
            key = l.split(":", 1)[1].strip()
    return cdsapi.Client(url=url, key=key)


def abrir(arq):
    if str(arq).endswith(".zip"):
        import zipfile
        dest = arq.with_suffix("")
        with zipfile.ZipFile(arq) as z:
            z.extractall(dest)
        return xr.merge([xr.open_dataset(f) for f in sorted(dest.glob("*.nc"))],
                        compat="override")
    return xr.open_dataset(arq)


def medias(ds):
    lat = "latitude" if "latitude" in ds.coords else "lat"
    lon = "longitude" if "longitude" in ds.coords else "lon"
    tempo = [c for c in ("valid_time", "time", "forecast_reference_time") if c in ds.coords][0]
    linhas = {}
    for cx, (la0, la1, lo0, lo1) in CAIXAS.items():
        sub = ds.sel({lat: slice(la1, la0), lon: slice(lo0, lo1)})  # CAMS: lat decrescente
        for v in ds.data_vars:
            s = sub[v].mean(dim=[lat, lon])
            s = s.squeeze(drop=True)
            linhas[f"{cx}_{v}"] = s.to_series()
    df = pd.DataFrame(linhas)
    df.index = pd.to_datetime(df.index)
    df.index.name = tempo
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ini", default="2026-08-10")
    ap.add_argument("--fim", default="2026-09-05")
    ap.add_argument("--anos-clima", default="2003-2025")
    a = ap.parse_args()
    DADOS.mkdir(parents=True, exist_ok=True)
    out = AQUI / "resultados"
    out.mkdir(exist_ok=True)
    c = cliente()

    print("1) analise operacional diaria", flush=True)
    arq = DADOS / f"cams_nrt_{a.ini.replace('-', '')}_{a.fim.replace('-', '')}.zip"
    if not arq.exists():
        c.retrieve("cams-global-atmospheric-composition-forecasts", {
            "date": f"{a.ini}/{a.fim}", "time": ["00:00", "12:00"], "leadtime_hour": ["0"],
            "type": ["forecast"], "variable": VARS, "area": AREA,
            "data_format": "netcdf_zip"}, str(arq))
    d = medias(abrir(arq))
    d.to_csv(out / f"cams_aod_{a.ini.replace('-', '')}_{a.fim.replace('-', '')}.csv",
             float_format="%.4f")
    print("  ok", len(d), "horarios", flush=True)

    print("2) climatologia EAC4 mensal (agosto)", flush=True)
    y0, y1 = (int(x) for x in a.anos_clima.split("-"))
    arq = DADOS / f"cams_eac4_mensal_ago_{y0}_{y1}.nc"
    if not arq.exists():
        c.retrieve("cams-global-reanalysis-eac4-monthly", {
            "variable": VARS, "year": [str(y) for y in range(y0, y1 + 1)],
            "month": ["08"], "product_type": ["monthly_mean"], "area": AREA,
            "data_format": "netcdf"}, str(arq))
    m = medias(abrir(arq))
    m.to_csv(out / f"cams_eac4_aod_ago_{y0}_{y1}.csv", float_format="%.4f")
    print("  ok", len(m), "meses", flush=True)


if __name__ == "__main__":
    main()
