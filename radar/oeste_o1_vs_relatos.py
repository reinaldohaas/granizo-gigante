# -*- coding: utf-8 -*-
"""O WRF simula as celulas e o granizo do oeste? Rodada O1_d02oeste_kf (d02 de 3 km ate 58,6 W, inicio 29/08 00Z).

Para cada relato com horario (os mesmos de satelite/glm_relatos.py), no d02 de 30 em 30 min:
  - HAILCAST maximo a ate 25 km do municipio na janela do relato, alargada em 1 h para cada lado;
  - menor distancia ao eco >= 50 dBZ e celula girante (UP_HELI_MAX >= 75) nessa janela;
  - hora do HAILCAST maximo.
Compara tambem a trilha do HAILCAST simulada com as trajetorias observadas do GLM (65, 81, 107, 185).

Saidas: radar/oeste_o1_vs_relatos.csv e radar/figuras/oeste_o1_hailcast.png
"""
import math
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import netCDF4
import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, '..', 'satelite'))
from glm_relatos import RELATOS  # noqa: E402
from glm_trajetorias import contornos, municipios  # noqa: E402

ARQ = os.path.join(AQUI, 'wrf', 'oeste_O1', 'recorte_d02_manha.nc')
RAIO = 25.0
FOLGA = pd.Timedelta(hours=1)


def main():
    d = netCDF4.Dataset(ARQ)
    tempos = pd.to_datetime([b''.join(t).decode().replace('_', ' ') for t in d['Times'][:]]).floor('min')
    lat, lon = np.array(d['XLAT'][0]), np.array(d['XLONG'][0])
    hc = np.array(d['HAILCAST_DIAM_MAX'][:])
    hc[hc > 150] = 0
    refd = np.array(d['REFD_MAX'][:])
    uh = np.array(d['UP_HELI_MAX'][:])
    cent = municipios()
    coslat = math.cos(math.radians(-27))
    linhas = []
    for nome, a, b, fonte in RELATOS:
        lo0, la0 = cent[nome]
        dist = np.hypot((lon - lo0) * 111.32 * coslat, (lat - la0) * 110.57)
        perto = dist <= RAIO
        sel = np.flatnonzero((tempos >= pd.Timestamp(a) - FOLGA) & (tempos <= pd.Timestamp(b) + FOLGA))
        if sel.size == 0:
            continue
        hmax = [hc[i][perto].max() for i in sel]
        k = int(np.argmax(hmax))
        d50 = min((dist[refd[i] >= 50].min() if (refd[i] >= 50).any() else np.inf) for i in sel)
        drot = min((dist[uh[i] >= 75].min() if (uh[i] >= 75).any() else np.inf) for i in sel)
        linhas.append(dict(municipio=nome, janela_relato=f'{a[11:16]}–{b[11:16]}', fonte=fonte,
                           hailcast_max_mm=round(float(hmax[k]), 1), hora_max=f'{tempos[sel[k]]:%H:%M}',
                           dist_eco50_km=round(float(d50)) if np.isfinite(d50) else None,
                           dist_rotacao_km=round(float(drot)) if np.isfinite(drot) else None))
    out = pd.DataFrame(linhas)
    out.to_csv(os.path.join(AQUI, 'oeste_o1_vs_relatos.csv'), index=False)
    pd.set_option('display.width', 220)
    print(out.to_string(index=False))

    # figura: trilha do HAILCAST 00-22 UTC e as trajetorias observadas do GLM
    trilha = hc.max(axis=0)
    hora = np.full(trilha.shape, np.nan)
    for i in range(len(tempos)):
        m = (hc[i] >= 5) & np.isnan(hora)
        hora[m] = tempos[i].hour + tempos[i].minute / 60
    print('HAILCAST maximo no d02 (00-22Z):', round(float(trilha.max()), 1), 'mm')
    cel = pd.read_csv(os.path.join(AQUI, '..', 'satelite', 'glm_celulas.csv'), parse_dates=['t'])
    fig, ax = plt.subplots(figsize=(15, 7.5), constrained_layout=True)
    im = ax.pcolormesh(lon, lat, np.ma.masked_less(trilha, 5), cmap='YlOrRd', vmin=5, vmax=50, shading='auto')
    fig.colorbar(im, ax=ax, shrink=0.8, label='HAILCAST máximo de 00 a 22 UTC (mm), WRF O1 d02')
    contornos(ax, 'America_do_Sul.shp', color='#8a96a6', lw=0.8)
    contornos(ax, 'BR_Estados.shp', color='#5d6b7c', lw=1.0)
    for tid, cor in ((65, '#2a78d6'), (81, '#2a78d6'), (107, '#eb6834'), (185, '#13895f')):
        g = cel[cel.traj == tid].sort_values('t')
        ax.plot(g.lon, g.lat, '-', color=cor, lw=3, label=f'GLM observado, trajetória {tid}')
    for nome, *_ in RELATOS:
        lo0, la0 = cent[nome]
        ax.plot(lo0, la0, '^', color='#b5127f', ms=9, mec='white')
    ax.set_xlim(-58.6, -46.0)
    ax.set_ylim(-31.1, -24.3)
    ax.set_aspect(1 / coslat)
    ax.legend(loc='lower left', fontsize=9)
    ax.set_title('WRF O1 (d02 3 km até 58,6°W, início 29/08 00Z): trilha do HAILCAST × trajetórias observadas pelos raios')
    fig.savefig(os.path.join(AQUI, 'figuras', 'oeste_o1_hailcast.png'), dpi=120)


if __name__ == '__main__':
    main()
