"""
A fumaca de 29/08/2026 sobre SC esteve acima da media daquele dia do ano?

Compara o AOD diario do MERRA-2 de 25/08 a 02/09 de 2026 com os mesmos dias de 1980 a 2025 (mesmo recorte,
mesmas caixas e mesmo metodo de aod_merra2.py). Os granulos ficam em cache em dados/merra2/.

A busca do earthaccess leva ~2,5 min por ano; por isso a lista de granulos vem de uma consulta direta ao CMR
(varias janelas temporais numa so consulta) e os recortes sao baixados em paralelo.

Saidas: resultados/merra2_aod_diario_clima_2508_0209.csv (todos os anos) e resultados/fumaca_clima_diaria.json
(percentil de 29/08/2026 entre os dias 25/08-02/09 de 1980-2025 e entre os 29/08 de cada ano).
Credencial: netrc do Earthdata (rodar com NETRC apontando para ~/.netrc no Windows).
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import earthaccess
import pandas as pd
import requests
import xarray as xr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aod_merra2 import AQUI, CACHE, medias, url_opendap  # noqa: E402

ANOS = range(1980, 2027)
INI, FIM = '08-25', '09-02'
CMR = 'https://cmr.earthdata.nasa.gov/search/granules.umm_json'


def granulos():
    gran = []
    for bloco in (ANOS[:24], ANOS[24:]):
        par = [('short_name', 'M2T1NXAER'), ('page_size', '2000')]
        par += [('temporal[]', f'{a}-{INI}T00:00:00Z,{a}-{FIM}T23:59:59Z') for a in bloco]
        r = requests.get(CMR, params=par, timeout=300)
        r.raise_for_status()
        gran += r.json()['items']
    return gran


def arquivo(g):
    return CACHE / g['umm']['GranuleUR'].split(':')[-1].replace('.nc4', '_sc.nc4')


def main():
    gran = granulos()
    print(len(gran), 'granulos', flush=True)
    earthaccess.login(strategy='netrc')
    sessao = earthaccess.get_requests_https_session()
    CACHE.mkdir(parents=True, exist_ok=True)

    def um(g):
        arq = arquivo(g)
        if arq.exists():
            return 0
        for _ in range(3):
            try:
                r = sessao.get(url_opendap(g, 24), timeout=300)
            except requests.RequestException:
                continue
            if r.status_code == 200 and r.content[1:4] == b'HDF':
                arq.write_bytes(r.content)
                return 1
        return -1

    feitos = 0
    with ThreadPoolExecutor(16) as pool:
        for res in pool.map(um, gran):
            feitos += 1
            if feitos % 25 == 0:
                print(f'  {feitos}/{len(gran)}', flush=True)
    partes = []
    for g in gran:
        if arquivo(g).exists():
            with xr.open_dataset(arquivo(g), engine='netcdf4') as ds:
                partes.append(medias(ds).resample('1D').mean())
    df = pd.concat(partes).sort_index()
    df = df[~df.index.duplicated()]
    df.index.name = 'data'
    df.to_csv(AQUI / 'resultados' / 'merra2_aod_diario_clima_2508_0209.csv', float_format='%.4f')
    print('dias por ano:', df.groupby(df.index.year).size().value_counts().to_dict())

    ev = df.loc['2026-08-29']
    clima = df[df.index.year <= 2025]
    mesmo = clima[(clima.index.month == 8) & (clima.index.day == 29)]
    res = {}
    for v in ('sc_aod_total', 'sc_aod_fumaca', 'corredor_aod_fumaca'):
        res[v] = dict(evento=round(float(ev[v]), 3), mediana=round(float(clima[v].median()), 3),
                      pct_janela=round(float((clima[v] < ev[v]).mean() * 100)),
                      pct_29ago=round(float((mesmo[v] < ev[v]).mean() * 100)),
                      pct_janela_2001_2025=round(float((clima[clima.index.year >= 2001][v] < ev[v]).mean() * 100)))
        print(v, res[v])
    json.dump(res, open(AQUI / 'resultados' / 'fumaca_clima_diaria.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
