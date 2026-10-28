# -*- coding: utf-8 -*-
"""Mosaico radar Morro da Igreja x as nove rodadas WRF (22/10, E0-E3, F1-F4), 29/08/2026 20:30-23:40 UTC, a cada 10 min.

Um quadro por horario, 2 x 5 paineis na janela de lado_a_lado.py: o MaxCAPPI mais proximo e o REFD_MAX do d03 de cada
rodada, com UP_HELI_MAX >= 75 m2 s-2 (preto) e HAILCAST_DIAM_MAX >= 20 mm (magenta). No titulo, o maior HAILCAST do
quadro dentro da janela. Moldura magenta: membros com granizo a ate 25 km dos relatos (hc_ilha > 0 em
resumo_ensemble.csv).
Saidas: radar/figuras/mosaico_ensemble/mosaico_AAAAMMDD_HHMM.jpg e mosaico_ensemble.gif.
"""
import csv
import datetime as dt
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
from PIL import Image

import comparar_wrf_radar
from comparar_wrf_radar import radar, recorte_d03
from lado_a_lado import FIM, INI, JANELA
from plotar_radar_mi import AQUI, RELATOS, SAIDA, base

RODADAS = [('', '22/10 controle'), ('E0_controle', 'E0 controle, d03 a oeste'), ('E1_mynn', 'E1 MYNN'),
           ('E2_inicio06', 'E2 início 06Z'), ('E3_gf_d01', 'E3 Grell-Freitas d01'), ('F1_gf_mynn', 'F1 GF + MYNN'),
           ('F2_gf_inicio06', 'F2 GF + início 06Z'), ('F3_gf_skebs1', 'F3 GF + SKEBS 1'),
           ('F4_gf_skebs2', 'F4 GF + SKEBS 2')]


def com_granizo():
    with open(os.path.join(SAIDA, 'resumo_ensemble.csv'), encoding='utf-8') as g:
        return {('' if r['rodada'] == '22/10' else r['rodada']) for r in csv.DictReader(g) if float(r['hc_ilha']) > 0}


def main():
    saida = os.path.join(SAIDA, 'mosaico_ensemble')
    os.makedirs(saida, exist_ok=True)
    comparar_wrf_radar.INI, comparar_wrf_radar.FIM = INI - dt.timedelta(minutes=20), FIM + dt.timedelta(minutes=20)
    quadros = radar()
    granizo = com_granizo()
    wrf = {}
    for m, _ in RODADAS:
        f = nc.Dataset(recorte_d03(m))
        tw = [dt.datetime.strptime(b''.join(t).decode(), '%Y-%m-%d_%H:%M:%S') for t in f['Times'][:]]
        wrf[m] = (f, f['XLAT'][0], f['XLONG'][0], tw)

    jpgs = []
    t = INI
    while t <= FIM:
        fig, axs = plt.subplots(2, 5, figsize=(20, 5.4), constrained_layout=True)
        tr, a, ext, _, _ = min(quadros, key=lambda q: abs(q[0] - t))
        axs[0, 0].imshow(a, extent=ext, origin='upper', interpolation='nearest')
        axs[0, 0].set_title(f'Radar Morro da Igreja {tr:%H:%M}', fontsize=11, fontweight='bold')
        for ax, (m, rotulo) in zip(axs.flat[1:], RODADAS):
            f, la, lo, tw = wrf[m]
            i = min(range(len(tw)), key=lambda k: abs(tw[k] - t))
            hc = f['HAILCAST_DIAM_MAX'][i]
            im = ax.pcolormesh(lo, la, np.ma.masked_less(f['REFD_MAX'][i], 20), cmap='turbo', vmin=20, vmax=65)
            ax.contour(lo, la, f['UP_HELI_MAX'][i], [75], colors='k', linewidths=0.9)
            ax.contour(lo, la, hc, [20], colors='magenta', linewidths=1.3)
            ax.plot([lo.min(), lo.max(), lo.max(), lo.min(), lo.min()],
                    [la.min(), la.min(), la.max(), la.max(), la.min()], color='0.4', lw=0.8, ls='--')
            hmax = float(hc[(lo >= JANELA[0]) & (lo <= JANELA[1]) & (la >= JANELA[2]) & (la <= JANELA[3])].max())
            ax.set_title(f'{rotulo}  {tw[i]:%H:%M}\nHAILCAST máx. {hmax:.0f} mm', fontsize=10,
                         color='#b5127f' if m in granizo else 'k', fontweight='bold' if m in granizo else 'normal')
            if m in granizo:
                for s in ax.spines.values():
                    s.set_edgecolor('#b5127f')
                    s.set_linewidth(3)
        for ax in axs.flat:
            base(ax, JANELA)
            ax.set_xticks([])
            ax.set_yticks([])
            for _, y, x, _ in RELATOS:
                ax.plot(x, y, 'v', ms=6, mfc='yellow', mec='k', zorder=6)
        fig.colorbar(im, ax=axs, shrink=0.6, pad=0.01, label='REFD_MAX WRF (dBZ)')
        fig.suptitle(f'29/08/2026 {t:%H:%M} UTC   WRF d03: REFD_MAX; UH ≥ 75 m² s⁻² (preto); HAILCAST ≥ 20 mm (magenta)'
                     f'   ▼ relatos   --- limite do d03   moldura magenta: granizo perto da Ilha', fontsize=12)
        jpg = os.path.join(saida, f'mosaico_{t:%Y%m%d_%H%M}.jpg')
        fig.savefig(jpg, dpi=80, pil_kwargs={'quality': 82})
        plt.close(fig)
        jpgs.append(jpg)
        print(jpg)
        t += dt.timedelta(minutes=10)

    imgs = [Image.open(p).convert('P', palette=Image.ADAPTIVE) for p in jpgs]
    imgs[0].save(os.path.join(saida, 'mosaico_ensemble.gif'), save_all=True, append_images=imgs[1:], duration=900, loop=0)


if __name__ == '__main__':
    main()
