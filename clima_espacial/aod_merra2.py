"""
Aerossol (MERRA-2) em torno do granizo de Florianopolis (29/08/2026).

1) Serie diaria (M2T1NXAER, media das 24 h) de AOD 550 nm por especie,
   de --ini a --fim, em tres caixas: SC (o evento), corredor (fumaca do
   centro-sul, como no caso do RS) e fogo (fonte de queimadas).
2) Climatologia de agosto (M2TMNXAER, media mensal) de 1980 ate o ano do
   evento, nas mesmas caixas, para dizer se agosto de 2026 foi anomalo.

Mesmo metodo do projeto do RS (clima_espacial_amas/scripts/02b_baixar_merra2_aod.py):
fumaca = carbono organico + carbono negro. Como la, o que importa e a anomalia
relativa, nao o valor absoluto.

Credencial: conta Earthdata no netrc (no Windows o earthaccess le ~/_netrc,
ou o arquivo apontado pela variavel NETRC).
Uso: python clima_espacial/aod_merra2.py --ini 2026-08-10 --fim 2026-09-05
"""
import argparse
import pathlib

import earthaccess
import pandas as pd
import xarray as xr

AQUI = pathlib.Path(__file__).resolve().parent
CAIXAS = {  # lat_min, lat_max, lon_min, lon_max
    "sc": (-29.5, -25.5, -54.0, -47.5),
    "corredor": (-30.0, -22.0, -60.0, -50.0),
    "fogo": (-20.0, 2.0, -70.0, -50.0),
}
VARS = {"aod_total": "TOTEXTTAU", "aod_org": "OCEXTTAU", "aod_bc": "BCEXTTAU",
        "aod_sulfato": "SUEXTTAU", "aod_poeira": "DUEXTTAU", "aod_sal": "SSEXTTAU"}


def medias(ds):
    linhas = {}
    for cx, (la0, la1, lo0, lo1) in CAIXAS.items():
        sub = ds.sel(lat=slice(la0, la1), lon=slice(lo0, lo1))
        for nome, v in VARS.items():
            linhas[f"{cx}_{nome}"] = sub[v].mean(dim=["lat", "lon"]).to_series()
    df = pd.DataFrame(linhas)
    for cx in CAIXAS:
        df[f"{cx}_aod_fumaca"] = df[f"{cx}_aod_org"] + df[f"{cx}_aod_bc"]
    return df


# Recorte via OPeNDAP do GES DISC (servico na nuvem, DAP4): so as variaveis e a caixa, em netCDF-4 (poucos KB),
# aberto com o netCDF4 local. Grade MERRA-2: lat -90:0.5:90, lon -180:0.625:179.375.
IJ = "[{t}][120:184][176:215]"  # lat -30..2, lon -70..-46.25 (cobre as tres caixas)
CACHE = AQUI / "dados" / "merra2"


def url_opendap(gran, nt):
    """URL do OPeNDAP na nuvem (DAP4) com o recorte de variaveis e caixa."""
    from urllib.parse import quote
    base = [u["URL"] for u in gran["umm"]["RelatedUrls"]
            if u.get("Subtype") == "OPENDAP DATA"][0]
    t = f"[0:1:{nt - 1}]"
    ce = ";".join([f"/{v}{t}[120:1:184][176:1:215]" for v in VARS.values()]
                  + ["/lat[120:1:184]", "/lon[176:1:215]", f"/time{t}"])
    return base + ".dap.nc4?dap4.ce=" + quote(ce, safe="/")


def baixar_recorte(gran, sessao, nt):
    nome = gran["umm"]["GranuleUR"].split(":")[-1]
    arq = CACHE / nome.replace(".nc4", "_sc.nc4")
    if not arq.exists():
        url = url_opendap(gran, nt)
        r = sessao.get(url, timeout=300)
        if r.status_code != 200 or r.content[1:4] != b"HDF":  # assinatura HDF5 (netCDF-4)
            raise RuntimeError(f"HTTP {r.status_code} em {url[:140]}...")
        CACHE.mkdir(parents=True, exist_ok=True)
        arq.write_bytes(r.content)
    return xr.open_dataset(arq, engine="netcdf4")


def serie_diaria(short_name, temporal, sessao):
    """Um granulo (um dia, 24 h) por vez: recorta as caixas e guarda a media diaria."""
    res = earthaccess.search_data(short_name=short_name, temporal=temporal)
    if not res:
        raise SystemExit(f"nenhum granulo {short_name} em {temporal}")
    print(f"  {short_name}: {len(res)} granulos", flush=True)
    partes = []
    for i, g in enumerate(res):
        with baixar_recorte(g, sessao, 24) as ds:
            partes.append(medias(ds).resample("1D").mean())
        print(f"    {i + 1}/{len(res)} {partes[-1].index[0]:%Y-%m-%d}", flush=True)
    return pd.concat(partes).sort_index()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ini", default="2026-08-10")
    ap.add_argument("--fim", default="2026-09-05")
    ap.add_argument("--mes", type=int, default=8)
    a = ap.parse_args()
    out = AQUI / "resultados"
    out.mkdir(exist_ok=True)
    earthaccess.login(strategy="netrc")
    sessao = earthaccess.get_requests_https_session()

    print("1) serie diaria", flush=True)
    d = serie_diaria("M2T1NXAER", (a.ini, a.fim), sessao)
    d.index.name = "data"
    arq = out / f"merra2_aod_diario_{a.ini.replace('-', '')}_{a.fim.replace('-', '')}.csv"
    d.to_csv(arq, float_format="%.4f")
    print("  ->", arq, flush=True)

    print("2) climatologia mensal", flush=True)
    ano = int(a.ini[:4])
    regs = []
    for y in range(1980, ano + 1):
        try:
            res = earthaccess.search_data(short_name="M2TMNXAER",
                                          temporal=(f"{y}-{a.mes:02d}-01", f"{y}-{a.mes:02d}-28"))
            if not res:
                print(f"  {y}: sem granulo mensal", flush=True)
                continue
            with baixar_recorte(res[0], sessao, 1) as dm:
                m = medias(dm).iloc[0]
            m["ano"] = y
            regs.append(m)
        except Exception as e:
            print(f"  {y}: erro {e}", flush=True)
    c = pd.DataFrame(regs).set_index("ano")
    arq = out / f"merra2_aod_mes{a.mes:02d}_1980_{ano}.csv"
    c.to_csv(arq, float_format="%.4f")
    print("  ->", arq, flush=True)


if __name__ == "__main__":
    main()
