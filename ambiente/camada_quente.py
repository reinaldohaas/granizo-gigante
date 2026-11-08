"""
Profundidade da camada quente (base da nuvem ate a isoterma de 0 graus) no granizo de 29/08/2026 x agostos 1940-2025.

Camada quente profunda favorece a chuva quente (colisao-coalescencia), que consome a agua liquida antes de ela
chegar super-resfriada a zona de crescimento do granizo: e um fator contra granizo grande.
  base da nuvem (LCL, m acima do solo) ~ 125 * (T2 - Td2)
  camada quente = isoterma de 0 graus (zero_degree_level, acima do solo) - LCL
ERA5, 18 e 21 UTC de agosto; mesmos pontos de isoterma_analise.py.
Saida: ambiente/camada_quente.csv e resumo no terminal.
"""
import glob
import os

import pandas as pd
import xarray as xr

from isoterma_analise import PONTOS, VEZES_EVENTO

AQUI = os.path.dirname(os.path.abspath(__file__))


def abrir(padrao):
    dss = []
    for a in sorted(glob.glob(os.path.join(AQUI, 'dados', 'era5', padrao, '*.nc'))):
        x = xr.open_dataset(a)
        tdim = 'valid_time' if 'valid_time' in x.dims else 'time'
        x = x.rename({tdim: 't'}).drop_vars([v for v in ('expver', 'number') if v in x.variables])
        x = x.assign_coords(latitude=x.latitude.round(2), longitude=x.longitude.round(2))
        dss.append(x)
    return xr.concat(dss, dim='t').sortby('t')


def main():
    iso = abrir('[12][0-9][0-9][0-9]_[12][0-9][0-9][0-9]')
    t2m = abrir('*_2m')
    linhas = []
    for nome, (lo, la, _) in PONTOS.items():
        a = iso.sel(longitude=lo, latitude=la, method='nearest').deg0l.to_series()
        b = t2m.sel(longitude=lo, latitude=la, method='nearest')
        lcl = 125 * (b.t2m - b.d2m).to_series()
        df = pd.DataFrame({'isoterma0_m': a, 'lcl_m': lcl}).dropna()
        df['camada_quente_m'] = df.isoterma0_m - df.lcl_m
        t_ev = pd.Timestamp(VEZES_EVENTO[nome])
        ev = df.loc[t_ev]
        clima = df[(df.index.year <= 2025) & (df.index.hour == t_ev.hour)]
        linhas.append(dict(lugar=nome, hora=f'{t_ev:%d/%m %H} UTC', lcl_m=round(ev.lcl_m),
                           camada_quente_m=round(ev.camada_quente_m),
                           percentil=round((clima.camada_quente_m < ev.camada_quente_m).mean() * 100, 1),
                           mediana_clima_m=round(clima.camada_quente_m.median())))
    r = pd.DataFrame(linhas)
    r.to_csv(os.path.join(AQUI, 'camada_quente.csv'), index=False)
    print(r.to_string(index=False))


if __name__ == '__main__':
    main()
