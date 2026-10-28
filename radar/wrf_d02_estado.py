# -*- coding: utf-8 -*-
"""Trajetorias simuladas em toda SC: WRF d02 (3 km) da rodada de 22/10 (controle, Kain-Fritsch no d01).

Para comparar com o rastreio observado (GLM e radar). Grava por saida de 30 min os objetos com
REFD_MAX >= 50 dBZ e o HAILCAST maximo de cada um, e um mapa com a hora da 1a passagem de >= 50 dBZ
e a trilha acumulada do HAILCAST.

Saidas: radar/wrf_d02_objetos.csv e radar/figuras/wrf_d02_estado.png
"""
import csv
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import netCDF4
import numpy as np
from scipy import ndimage

from plotar_radar_mi import base, RELATOS

AQUI = os.path.dirname(os.path.abspath(__file__))
WRF = os.path.join(AQUI, '..', 'run_wrf', 'wrfout_d02_2026-08-29_12_00_00')


def main():
    ds = netCDF4.Dataset(WRF)
    V = ds.variables
    tempos = [b''.join(t).decode() for t in V['Times'][:]]
    lat, lon = np.array(V['XLAT'][0]), np.array(V['XLONG'][0])
    nt = len(tempos)
    primeira = np.full(lat.shape, np.nan)
    trilha = np.zeros(lat.shape)
    linhas = []
    for i, t in enumerate(tempos):
        r = np.array(V['REFD_MAX'][i]) if 'REFD_MAX' in V else np.array(V['REFL_10CM'][i]).max(axis=0)
        hc = np.array(V['HAILCAST_DIAM_MAX'][i])
        uh = np.array(V['UP_HELI_MAX'][i])
        h = i * (12 * 60 / max(nt - 1, 1)) if False else None
        hora = int(t[11:13]) + int(t[14:16]) / 60 + (24 if t[8:10] == '30' else 0)
        m = r >= 50
        primeira[m & np.isnan(primeira)] = hora
        trilha = np.maximum(trilha, np.where(hc < 150, hc, 0))
        lab, n = ndimage.label(m)
        for c in range(1, n + 1):
            k = lab == c
            if k.sum() < 3:
                continue
            linhas.append(dict(t=t[:16], lat=round(float(lat[k].mean()), 3), lon=round(float(lon[k].mean()), 3),
                               area_km2=int(k.sum() * 9), dbz_max=round(float(r[k].max()), 1),
                               hailcast_max_mm=round(float(hc[k].max()), 1), uh_max=round(float(uh[k].max()), 1)))
    with open(os.path.join(AQUI, 'wrf_d02_objetos.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    print(len(tempos), 'saidas,', tempos[0], '..', tempos[-1], '|', len(linhas), 'objetos >= 50 dBZ')

    fig, axs = plt.subplots(1, 2, figsize=(18, 6.6), constrained_layout=True)
    jan = (-54.0, -48.0, -29.4, -25.8)
    im = axs[0].pcolormesh(lon, lat, np.ma.masked_invalid(primeira), cmap='viridis', shading='auto')
    fig.colorbar(im, ax=axs[0], shrink=0.8, label='hora UTC da 1ª passagem de ≥ 50 dBZ (24 = 00 de 30/08)')
    axs[0].set_title('WRF d02: onde e quando houve ≥ 50 dBZ')
    im = axs[1].pcolormesh(lon, lat, np.ma.masked_less(trilha, 5), cmap='YlOrRd', vmin=5, vmax=50, shading='auto')
    fig.colorbar(im, ax=axs[1], shrink=0.8, label='HAILCAST máximo acumulado (mm)')
    axs[1].set_title('WRF d02: trilha do granizo (HAILCAST ≥ 5 mm)')
    for ax in axs:
        base(ax, jan)
        for _, la, lo, _ in RELATOS:
            ax.plot(lo, la, '^', color='#c4129f', ms=5)
        ax.set_xlim(jan[:2])
        ax.set_ylim(jan[2:])
    fig.suptitle(f'Rodada de controle (22/10), {tempos[0][:16]} a {tempos[-1][:16]} UTC', fontsize=12)
    fig.savefig(os.path.join(AQUI, 'figuras', 'wrf_d02_estado.png'), dpi=120)


if __name__ == '__main__':
    main()
