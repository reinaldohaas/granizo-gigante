# -*- coding: utf-8 -*-
"""Tabela unica: rodada de 22/10 e membros E0-E3 e F1-F4 dos mini-ensembles contra o radar Morro da Igreja (29/08/2026).

Para cada rodada:
  conv_d02_18_20   pontos do d02 com REFD_MAX >= 50 dBZ na faixa 27,0-28,1 S / 48,2-50,2 W, somados de 18:00 a 20:00
                   (o radar nao tem eco amarelo ou mais forte nessa faixa ate 20:36: e a convecção prematura)
  dist_rot_HHMM    distancia (km) do nucleo do radar no horario HH:MM ao objeto UP_HELI_MAX >= 75 m2 s-2 mais proximo no
                   d03, procurado nas saidas de HH:MM-20 a HH:MM+20 min (e o desvio em latitude, + = ao norte)
  dist_50_HHMM     idem para o objeto REFD_MAX >= 50 dBZ mais proximo (com ou sem rotacao)
  hc_ilha          maximo de HAILCAST_DIAM_MAX a ate 25 km dos relatos, 21:50-23:10 (mm)
Saida: radar/figuras/resumo_ensemble.csv (e impressa).
"""
import csv
import os
from datetime import datetime, timedelta

import netCDF4 as nc
import numpy as np
from scipy import ndimage

from plotar_radar_mi import AQUI, RELATOS, SAIDA

RODADAS = [('22/10', os.path.join(AQUI, 'wrf'))] + [
    (m, os.path.join(AQUI, 'wrf', 'ensemble', m)) for m in ('E0_controle', 'E1_mynn', 'E2_inicio06', 'E3_gf_d01',
                                                    'F1_gf_mynn', 'F2_gf_inicio06', 'F3_gf_skebs1', 'F4_gf_skebs2')]
# nucleos do radar (centroides de comparar_wrf_radar.py): horario, lat, lon
NUCLEOS = [(datetime(2026, 8, 29, 21, 16), -27.58, -49.42), (datetime(2026, 8, 29, 21, 36), -27.58, -49.20),
           (datetime(2026, 8, 29, 22, 16), -27.50, -48.61), (datetime(2026, 8, 29, 22, 36), -27.41, -48.32)]


def tempos(f):
    return [datetime.strptime(b''.join(t).decode()[:16], '%Y-%m-%d_%H:%M') for t in f['Times'][:]]


def km(la1, lo1, la2, lo2):
    return np.hypot((la1 - la2) * 111.2, (lo1 - lo2) * 111.2 * np.cos(np.radians(-27.5)))


def mais_proximo(f, la, lo, tw, var, limiar, t0, y0, x0):
    melhor = (np.nan, np.nan)
    for i, t in enumerate(tw):
        if abs(t - t0) > timedelta(minutes=20):
            continue
        lab, n = ndimage.label(f[var][i] >= limiar)
        for k in range(1, n + 1):
            m = lab == k
            if m.sum() < 3:
                continue
            d = km(la[m], lo[m], y0, x0).min()
            if np.isnan(melhor[0]) or d < melhor[0]:
                melhor = (d, (la[m].mean() - y0) * 111.2)
    return melhor


def main():
    linhas = []
    for nome, pasta in RODADAS:
        d2 = nc.Dataset(os.path.join(pasta, 'recorte_trajetorias_d02.nc'))
        la2, lo2 = d2['XLAT'][0], d2['XLONG'][0]
        faixa = (la2 > -28.1) & (la2 < -27.0) & (lo2 > -50.2) & (lo2 < -48.2)
        conv = sum(int(((d2['REFD_MAX'][i] >= 50) & faixa).sum()) for i, t in enumerate(tempos(d2))
                   if datetime(2026, 8, 29, 18) <= t <= datetime(2026, 8, 29, 20))

        f = nc.Dataset(os.path.join(pasta, 'recorte_trajetorias_d03.nc'))
        la, lo, tw = f['XLAT'][0], f['XLONG'][0], tempos(f)
        lin = {'rodada': nome, 'conv_d02_18_20': conv}
        for t0, y0, x0 in NUCLEOS:
            for var, lim, rot in (('UP_HELI_MAX', 75, 'rot'), ('REFD_MAX', 50, '50')):
                d, dlat = mais_proximo(f, la, lo, tw, var, lim, t0, y0, x0)
                lin[f'dist_{rot}_{t0:%H%M}'] = f'{d:.0f} ({dlat:+.0f})' if np.isfinite(d) else '—'
        perto = np.zeros(la.shape, bool)
        for _, y, x, _ in RELATOS:
            perto |= km(la, lo, y, x) <= 25
        sel = [i for i, t in enumerate(tw) if datetime(2026, 8, 29, 21, 50) <= t <= datetime(2026, 8, 29, 23, 10)]
        lin['hc_ilha'] = f"{float(f['HAILCAST_DIAM_MAX'][sel][:, perto].max()):.0f}"
        linhas.append(lin)

    os.makedirs(SAIDA, exist_ok=True)
    with open(os.path.join(SAIDA, 'resumo_ensemble.csv'), 'w', newline='', encoding='utf-8') as g:
        w = csv.DictWriter(g, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    for lin in linhas:
        print(lin)


if __name__ == '__main__':
    main()
