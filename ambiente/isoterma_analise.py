"""
A isoterma de 0 graus no granizo de 29/08/2026 foi baixa para agosto? E ela vem baixando desde 1940?

Le os arquivos de era5_isoterma.py (agosto, 18 e 21 UTC, 1940-2026) e, para tres pontos do caminho das
celulas (oeste, Meio-Oeste, Grande Florianopolis), calcula:
  - o valor no dia e na hora do granizo em cada lugar;
  - o percentil desse valor entre todos os dias de agosto de 1940-2025 na mesma hora;
  - a media de agosto por ano e a tendencia linear (m por decada) da isoterma, do CAPE e do vapor.
A isoterma do ERA5 (zero_degree_level) e altura acima da superficie; somo a altitude do terreno do ERA5 nao
disponivel aqui, entao os valores sao acima do solo de cada ponto (comparacao sempre no mesmo ponto).

Saidas: ambiente/isoterma_resumo.csv, ambiente/isoterma_anual.csv
"""
import glob
import os

import numpy as np
import pandas as pd
import xarray as xr

AQUI = os.path.dirname(os.path.abspath(__file__))
PONTOS = {  # nome: (lon, lat, data-hora UTC do granizo mais proxima de 18/21 UTC)
    'Oeste (Ipuaçu)': (-52.3, -26.7, '2026-08-29 18:00'),      # granizo de madrugada: usa 28/08 21 UTC abaixo
    'Meio-Oeste (Joaçaba)': (-51.5, -27.2, '2026-08-29 18:00'),
    'Grande Florianópolis (Biguaçu)': (-48.65, -27.5, '2026-08-29 21:00'),
}
VEZES_EVENTO = {'Oeste (Ipuaçu)': '2026-08-28 21:00', 'Meio-Oeste (Joaçaba)': '2026-08-28 21:00',
                'Grande Florianópolis (Biguaçu)': '2026-08-29 21:00'}


def abrir():
    arqs = sorted(glob.glob(os.path.join(AQUI, 'dados', 'era5', '*', '*.nc')))
    dss = []
    for a in arqs:
        x = xr.open_dataset(a)
        tdim = 'valid_time' if 'valid_time' in x.dims else 'time'
        x = x.rename({tdim: 't'}).drop_vars([v for v in ('expver', 'number') if v in x.variables])
        # blocos com coordenadas em float ligeiramente diferentes: arredonda para a grade de 0,25 grau
        x = x.assign_coords(latitude=x.latitude.round(2), longitude=x.longitude.round(2))
        dss.append(x)
    return xr.concat(dss, dim='t').sortby('t')


def main():
    ds = abrir()
    print(ds)
    nomes = {v: v for v in ds.data_vars}
    deg0 = [v for v in ds.data_vars if v.lower() in ('deg0l', 'zero_degree_level')][0]
    cape = [v for v in ds.data_vars if v.lower() in ('cape', 'convective_available_potential_energy')][0]
    tcwv = [v for v in ds.data_vars if v.lower() in ('tcwv', 'total_column_water_vapour')][0]
    resumo, anual = [], []
    for nome, (lo, la, _) in PONTOS.items():
        p = ds.sel(longitude=lo, latitude=la, method='nearest')
        df = p[[deg0, cape, tcwv]].to_dataframe()[[deg0, cape, tcwv]]
        df.index = pd.to_datetime(df.index)
        t_ev = pd.Timestamp(VEZES_EVENTO[nome])
        ev = df.loc[t_ev]
        clima = df[(df.index.year <= 2025) & (df.index.hour == t_ev.hour)]
        if nome.startswith('Grande'):
            clima[[deg0]].rename(columns={deg0: 'isoterma0_m'}).to_csv(
                os.path.join(AQUI, 'isoterma_dias_biguacu.csv'), float_format='%.1f')
        linha = dict(lugar=nome, hora_evento=f'{t_ev:%d/%m %H} UTC')
        for v, rot in ((deg0, 'isoterma0_m'), (cape, 'cape_jkg'), (tcwv, 'vapor_mm')):
            linha[rot] = round(float(ev[v]), 1)
            linha[rot + '_percentil'] = round(float((clima[v] < ev[v]).mean() * 100), 1)
            linha[rot + '_mediana_clima'] = round(float(clima[v].median()), 1)
        ano = df.groupby(df.index.year).mean()
        for v, rot in ((deg0, 'isoterma0_m'), (cape, 'cape_jkg'), (tcwv, 'vapor_mm')):
            y = ano.loc[:2025, v]
            b = np.polyfit(y.index.values, y.values, 1)[0] * 10
            linha[rot + '_tend_por_decada'] = round(float(b), 2)
            linha[rot + '_media_1940_1969'] = round(float(y.loc[1940:1969].mean()), 1)
            linha[rot + '_media_1996_2025'] = round(float(y.loc[1996:2025].mean()), 1)
        resumo.append(linha)
        a = ano.reset_index().rename(columns={'index': 'ano', deg0: 'isoterma0_m', cape: 'cape_jkg', tcwv: 'vapor_mm'})
        a.columns = ['ano', 'isoterma0_m', 'cape_jkg', 'vapor_mm']
        a.insert(0, 'lugar', nome)
        anual.append(a)
    r = pd.DataFrame(resumo)
    r.to_csv(os.path.join(AQUI, 'isoterma_resumo.csv'), index=False)
    pd.concat(anual).to_csv(os.path.join(AQUI, 'isoterma_anual.csv'), index=False, float_format='%.2f')
    pd.set_option('display.width', 250)
    pd.set_option('display.max_columns', 30)
    print(r.T.to_string())


if __name__ == '__main__':
    main()
