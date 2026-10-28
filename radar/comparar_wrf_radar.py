# -*- coding: utf-8 -*-
"""Compara a rodada WRF de 22/10 (d03, 1 km) com os nucleos do MaxCAPPI do Morro da Igreja, 29/08/2026.

Entradas: radar/mi/maxcappi/ (baixar_redemet.py) e radar/wrf/recorte_trajetorias_d03.nc (VLab, SHA256_recortes.txt).
Saidas (radar/figuras/):
  wrf_x_radar_trajetorias.png  centroides dos nucleos do radar e dos objetos UH >= 75 m2 s-2 do WRF, 20:30-00:30
  wrf_x_radar_quadros.png      radar x REFD_MAX do WRF no horario mais proximo (21:16 .. 23:36)
Imprime a tabela de centroides usada no texto.
Uso: python comparar_wrf_radar.py [membro]  (membro do ensemble em radar/wrf/ensemble/<membro>/; sem argumento, a
rodada de 22/10; com membro, as figuras ganham o sufixo _<membro>).
"""
import csv
import os
from datetime import datetime, timedelta

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
from PIL import Image
from scipy import ndimage

from plotar_radar_mi import AQUI, PASTA, RELATOS, SAIDA, base, nucleo

INI, FIM = datetime(2026, 8, 29, 20, 30), datetime(2026, 8, 30, 0, 30)
UH_MIN = 75.0


def radar():
    """[(t, rgba, extent, LA, LO)] dos quadros entre INI e FIM."""
    out = []
    with open(os.path.join(PASTA, 'quadros.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            t = datetime.strptime(r['data_utc'], '%Y-%m-%d %H:%M:%S')
            if not INI <= t <= FIM:
                continue
            x0, x1, y0, y1 = (float(r[k]) for k in ('lon_min', 'lon_max', 'lat_min', 'lat_max'))
            a = np.array(Image.open(os.path.join(PASTA, r['arquivo'])).convert('RGBA'))
            LA, LO = np.meshgrid(y1 - (np.arange(a.shape[0]) + .5) / a.shape[0] * (y1 - y0),
                                 x0 + (np.arange(a.shape[1]) + .5) / a.shape[1] * (x1 - x0), indexing='ij')
            out.append((t, a, [x0, x1, y0, y1], LA, LO))
    return out


def objetos(mascara, LA, LO, minimo):
    lab, n = ndimage.label(mascara)
    return [(LA[lab == k].mean(), LO[lab == k].mean(), (lab == k).sum()) for k in range(1, n + 1)
            if (lab == k).sum() >= minimo]


def recorte_d03(membro=''):
    if membro:
        return os.path.join(AQUI, 'wrf', 'ensemble', membro, 'recorte_trajetorias_d03.nc')
    return os.path.join(AQUI, 'wrf', 'recorte_trajetorias_d03.nc')


def main(membro=''):
    sufixo = f'_{membro}' if membro else ''
    f = nc.Dataset(recorte_d03(membro))
    la, lo = f['XLAT'][0], f['XLONG'][0]
    tw = [datetime.strptime(b''.join(t).decode(), '%Y-%m-%d_%H:%M:%S') for t in f['Times'][:]]
    caixa = (lo.min(), lo.max(), la.min(), la.max())
    quadros = radar()

    fig, ax = plt.subplots(figsize=(11, 8.5), constrained_layout=True)
    base(ax, caixa)
    ax.contour(lo, la, f['HGT'][0], [400, 800, 1200], colors='0.6', linewidths=0.5)
    cmap, norm = plt.get_cmap('turbo'), plt.Normalize(0, (FIM - INI).total_seconds() / 3600)
    print('radar (centroide dos nucleos vermelho/magenta dentro do d03)')
    for t, a, ext, LA, LO in quadros:
        dentro = (LA >= caixa[2]) & (LA <= caixa[3]) & (LO >= caixa[0]) & (LO <= caixa[1])
        obs = objetos(nucleo(a) & dentro, LA, LO, 2)
        print(f'  {t:%H:%M}', ' | '.join(f'({y:.2f},{x:.2f}) n{n}' for y, x, n in obs))
        for y, x, n in obs:
            h = (t - INI).total_seconds() / 3600
            ax.scatter(x, y, s=20 + 6 * n, marker='s', color=cmap(norm(h)), edgecolor='k', lw=0.6, zorder=4)
            ax.annotate(f'{t:%H:%M}', (x, y), xytext=(4, 4), textcoords='offset points', fontsize=7, color='k')
    print(f'WRF d03 (centroide dos objetos UP_HELI_MAX >= {UH_MIN:.0f} m2 s-2; HAILCAST_DIAM_MAX max no objeto)')
    uh, hc = f['UP_HELI_MAX'][:], f['HAILCAST_DIAM_MAX'][:]
    for i, t in enumerate(tw):
        if not INI <= t <= FIM:
            continue
        lab, n = ndimage.label(uh[i] >= UH_MIN)
        lin = []
        for k in range(1, n + 1):
            m = lab == k
            if m.sum() < 3:
                continue
            y, x = la[m].mean(), lo[m].mean()
            lin.append(f'({y:.2f},{x:.2f}) UH {uh[i][m].max():.0f} HC {hc[i][m].max():.0f} mm')
            ax.scatter(x, y, s=30, marker='o', color=cmap(norm((t - INI).total_seconds() / 3600)),
                       edgecolor='k', lw=0.3, zorder=3)
        print(f'  {t:%H:%M}', ' | '.join(lin))
    sw = np.ma.masked_less(hc[[i for i, t in enumerate(tw) if INI <= t <= FIM]].max(axis=0), 10)
    cs = ax.contourf(lo, la, sw, [10, 20, 30, 40, 60], cmap='Purples', alpha=0.45, zorder=2)
    fig.colorbar(cs, ax=ax, shrink=0.5, label='WRF HAILCAST_DIAM_MAX 20:30–00:30 (mm)')
    fig.colorbar(plt.cm.ScalarMappable(norm, cmap), ax=ax, shrink=0.5, label=f'horas após {INI:%H:%M} UTC')
    for nome, y, x, h in RELATOS[::2]:
        ax.annotate(nome, (x, y), xytext=(3, -10), textcoords='offset points', fontsize=7)
    ax.set_title('■ núcleos do radar Morro da Igreja   ● objetos UH ≥ 75 m² s⁻² do WRF d03   ▲ relatos de granizo')
    fig.savefig(os.path.join(SAIDA, f'wrf_x_radar_trajetorias{sufixo}.png'), dpi=130)

    # radar x REFD_MAX do WRF no horario de saida mais proximo
    horas = [datetime(2026, 8, 29, 21, 16), datetime(2026, 8, 29, 21, 36), datetime(2026, 8, 29, 22, 16),
             datetime(2026, 8, 29, 22, 36), datetime(2026, 8, 29, 23, 16), datetime(2026, 8, 29, 23, 36)]
    fig, axs = plt.subplots(2, 6, figsize=(24, 8.5), constrained_layout=True)
    for j, h in enumerate(horas):
        t, a, ext, _, _ = min(quadros, key=lambda q: abs(q[0] - h))
        axs[0, j].imshow(a, extent=ext, origin='upper', interpolation='nearest')
        base(axs[0, j], caixa)
        axs[0, j].set_title(f'radar {t:%H:%M}')
        i = min(range(len(tw)), key=lambda k: abs(tw[k] - h - timedelta(minutes=4)))
        im = axs[1, j].pcolormesh(lo, la, np.ma.masked_less(f['REFD_MAX'][i], 20), cmap='turbo', vmin=20, vmax=65)
        axs[1, j].contour(lo, la, uh[i], [UH_MIN], colors='k', linewidths=0.8)
        base(axs[1, j], caixa)
        axs[1, j].set_title(f'WRF {tw[i]:%H:%M} REFD_MAX, contorno UH {UH_MIN:.0f}')
    fig.colorbar(im, ax=axs[1, :], shrink=0.7, label='REFD_MAX WRF (dBZ)')
    fig.savefig(os.path.join(SAIDA, f'wrf_x_radar_quadros{sufixo}.png'), dpi=110)


if __name__ == '__main__':
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else '')
