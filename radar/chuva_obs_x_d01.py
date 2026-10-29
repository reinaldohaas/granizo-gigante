# -*- coding: utf-8 -*-
"""Chuva observada (IMERG Late V07, 0,1 grau, 30 min) x chuva do d01 do E0 (Kain-Fritsch) e do E3 (Grell-Freitas),
29/08/2026 12-21 UTC, com os flashes do GLM como marca de convecção.

Pergunta: a linha de chuva convectiva de 20-40 mm que o KF poe a oeste do d02 entre 12 e 18 UTC existiu?
O modelo e levado a grade do IMERG pela media dos pontos do d01 em cada celula de 0,1 grau.
Entradas: satelite/imerg/*.HDF5, satelite/glm_pontos_sc.csv, radar/wrf/ensemble/<membro>/recorte_d01_1222.nc.
Saidas: radar/figuras/d01_E0_E3/chuva_obs_x_d01.png e chuva_obs_oeste_horaria.png; tabela impressa.
"""
import glob
import os
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
import pandas as pd

from comparar_d01_E0_E3 import D02, MEMBROS, OUT, caixa
from plotar_radar_mi import AQUI, contornos

IMERG = os.path.join(AQUI, '..', 'satelite', 'imerg')
GLM = os.path.join(AQUI, '..', 'satelite', 'glm_pontos_sc.csv')
JANELAS = (('12:00', '18:00'), ('18:00', '21:00'))
NIVEIS = [1, 5, 10, 20, 40, 80]


def imerg():
    """{inicio da meia hora: chuva (mm) na meia hora}, lons, lats (centros)."""
    out = {}
    for p in sorted(glob.glob(os.path.join(IMERG, '*.HDF5'))):
        n = os.path.basename(p)
        t = datetime.strptime(n.split('.')[4][:8] + n.split('-S')[1][:4], '%Y%m%d%H%M')
        g = nc.Dataset(p)['Grid']
        lon, lat = g['lon'][:], g['lat'][:]
        i = (lon >= -55) & (lon <= -42.5)
        j = (lat >= -33) & (lat <= -22)
        pr = g['precipitation'][0][np.ix_(i, j)].T          # (lat, lon), mm/h
        out[t] = np.ma.filled(pr, np.nan) * 0.5
    return out, lon[i], lat[j]


def na_grade(campo, la, lo, lons, lats):
    """Media dos pontos do modelo em cada celula de 0,1 grau (nan onde nao ha ponto)."""
    be_x = np.r_[lons - 0.05, lons[-1] + 0.05]
    be_y = np.r_[lats - 0.05, lats[-1] + 0.05]
    s, _, _ = np.histogram2d(la.ravel(), lo.ravel(), [be_y, be_x], weights=campo.ravel())
    n, _, _ = np.histogram2d(la.ravel(), lo.ravel(), [be_y, be_x])
    with np.errstate(invalid='ignore'):
        return s / n


def main():
    obs, lons, lats = imerg()
    LO, LA = np.meshgrid(lons, lats)
    horas = sorted(obs)
    glm = pd.read_csv(GLM, parse_dates=['t_utc'])
    mod = {}
    for m, _ in MEMBROS:
        f = nc.Dataset(os.path.join(AQUI, 'wrf', 'ensemble', m, 'recorte_d01_1222.nc'))
        hh = [b''.join(t).decode()[11:16] for t in f['Times'][:]]
        mod[m] = (hh, f['RAINC'][:] + f['RAINNC'][:], f['RAINC'][:], f['XLAT'][0], f['XLONG'][0])
    la, lo = mod['E0_controle'][3], mod['E0_controle'][4]
    # d02 em lat/lon e regioes na grade do IMERG
    d02 = (lo[D02[0], D02[0]], lo[D02[1], D02[1]], la[D02[0], D02[0]], la[D02[1], D02[1]])
    dentro_d01 = np.isfinite(na_grade(np.ones_like(la), la, lo, lons, lats))
    em_d02 = (LO >= d02[0]) & (LO <= d02[1]) & (LA >= d02[2]) & (LA <= d02[3])
    oeste = dentro_d01 & ~em_d02 & (LO < d02[0]) & (LA > -30) & (LA < -25)
    fora = dentro_d01 & ~em_d02

    print(f'd02 ~ lon {d02[0]:.2f}..{d02[1]:.2f}, lat {d02[2]:.2f}..{d02[3]:.2f}; celulas IMERG: oeste {oeste.sum()}, fora do d02 {fora.sum()}')
    print('janela      regiao     IMERG med/p99   E0 med/p99 (RAINC med)   E3 med/p99 (RAINC med)   flashes GLM   r(IMERG,E0) r(IMERG,E3)')
    fig, axs = plt.subplots(len(JANELAS), 3, figsize=(17, 11), constrained_layout=True)
    for r, (a, b) in enumerate(JANELAS):
        ta, tb = datetime(2026, 8, 29, int(a[:2])), datetime(2026, 8, 29, int(b[:2]))
        o = sum(obs[t] for t in horas if ta <= t < tb)
        g = glm[(glm.t_utc >= ta) & (glm.t_utc < tb)]
        campos = {'IMERG': o}
        rc = {}
        for m, _ in MEMBROS:
            hh, tot, conv, mla, mlo = mod[m]
            campos[m] = na_grade(tot[hh.index(b)] - tot[hh.index(a)], mla, mlo, lons, lats)
            rc[m] = na_grade(conv[hh.index(b)] - conv[hh.index(a)], mla, mlo, lons, lats)
        for nome, reg in (('oeste', oeste), ('fora d02', fora)):
            ok = reg & np.isfinite(o)
            nfl = int(((g.lon >= lons.min()) & (g.lat >= -30) & (g.lat <= -25) & (g.lon < d02[0])).sum()) if nome == 'oeste' else len(g)
            txt = [f'{a}-{b}  {nome:9s}  {np.nanmean(o[ok]):5.2f}/{np.nanpercentile(o[ok], 99):5.1f}']
            for m, _ in MEMBROS:
                c = campos[m]
                txt.append(f'{np.nanmean(c[ok]):5.2f}/{np.nanpercentile(c[ok], 99):5.1f} ({np.nanmean(rc[m][ok]):4.2f})')
            cor = [np.corrcoef(o[ok], campos[m][ok])[0, 1] for m, _ in MEMBROS]
            print('   '.join(txt), f'  {nfl:8d}', '  '.join(f'{c:+.2f}' for c in cor))
        for c, (nome, campo) in enumerate(campos.items()):
            ax = axs[r, c]
            cs = ax.contourf(LO, LA, np.where(dentro_d01, campo, np.nan), NIVEIS, cmap='YlGnBu', extend='max')
            if nome == 'IMERG':
                h, ye, xe = np.histogram2d(g.lat, g.lon, [np.arange(-30.5, -24.9, 0.2), np.arange(-58, -45.9, 0.2)])
                ax.contour(0.5 * (xe[1:] + xe[:-1]), 0.5 * (ye[1:] + ye[:-1]), h, [20], colors='r', linewidths=0.8)
                ax.set_title(f'IMERG Late {a}-{b} UTC (vermelho: ≥ 20 flashes GLM / 0,2°)', fontsize=10)
            else:
                ax.contour(LO, LA, np.where(dentro_d01, rc[nome], np.nan), [5], colors='r', linewidths=0.6)
                ax.set_title(f'{dict(MEMBROS)[nome]} {a}-{b} UTC (vermelho: RAINC ≥ 5 mm)', fontsize=10)
            contornos(ax, 'America_do_Sul.shp', color='0.6', lw=0.5)
            contornos(ax, 'BR_Estados.shp', color='0.4', lw=0.6)
            caixa(ax, lo, la, D02[0], D02[0], D02[1], D02[1], color='k', lw=1.0, ls='--')
            ax.set_xlim(lo.min(), lo.max())
            ax.set_ylim(la.min(), la.max())
            ax.set_aspect(1 / np.cos(np.radians(27.5)))
        fig.colorbar(cs, ax=axs[r, :], shrink=0.7, label='mm')
    fig.suptitle('Chuva acumulada na grade de 0,1° (modelo: média dos pontos do d01 9 km). Tracejado: d02. GLM só cobre 58–46° W, 25–30,5° S')
    fig.savefig(os.path.join(OUT, 'chuva_obs_x_d01.png'), dpi=95)
    plt.close(fig)

    # serie horaria na faixa oeste
    fig, ax = plt.subplots(figsize=(10, 4.5), constrained_layout=True)
    th = [datetime(2026, 8, 29, h) for h in range(12, 22)]
    ob = [np.nanmean((obs[t] + obs[t.replace(minute=30)])[oeste]) for t in th]
    ax.plot([f'{t:%H}' for t in th], ob, 'k-o', label='IMERG')
    for m, rot in MEMBROS:
        hh, tot, _, mla, mlo = mod[m]
        ax.plot([f'{t:%H}' for t in th],
                [np.nanmean(na_grade(tot[hh.index(f'{t.hour + 1:02d}:00')] - tot[hh.index(f'{t:%H}:00')], mla, mlo,
                                     lons, lats)[oeste]) for t in th], '-o', label=rot)
    fl = [int(((glm.t_utc >= t) & (glm.t_utc < t.replace(hour=t.hour + 1)) & (glm.lon < d02[0]) & (glm.lat >= -30)
               & (glm.lat <= -25)).sum()) for t in th]
    ax2 = ax.twinx()
    ax2.bar([f'{t:%H}' for t in th], fl, color='r', alpha=0.2, label='flashes GLM')
    ax2.set_ylabel('flashes GLM na faixa / h')
    ax.set_xlabel('hora UTC (início)')
    ax.set_ylabel('chuva média na faixa (mm/h)')
    ax.set_title(f'Faixa a oeste do d02 (lon < {d02[0]:.1f}, 25–30° S, dentro do d01)')
    ax.legend(loc='upper left')
    print('flashes GLM por hora na faixa oeste:', dict(zip([f'{t:%H}' for t in th], fl)))
    print('IMERG mm/h na faixa oeste:', [round(float(x), 2) for x in ob])
    fig.savefig(os.path.join(OUT, 'chuva_obs_oeste_horaria.png'), dpi=100)


if __name__ == '__main__':
    main()
