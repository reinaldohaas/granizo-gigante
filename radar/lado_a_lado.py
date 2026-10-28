# -*- coding: utf-8 -*-
"""Radar Morro da Igreja x GOES-19 C13 x WRF d03 lado a lado, 29/08/2026 20:30 - 30/08 00:30 UTC, a cada 10 min.

Colunas: (1) MaxCAPPI do Morro da Igreja (DECEA/REDEMET), quadro mais proximo (a cada 20 min, horario no titulo);
(2) GOES-19 ABI C13 (10,3 um) com contorno de -50 C; (3) WRF d03 (rodada de 22/10) REFD_MAX, contorno de
UP_HELI_MAX >= 75 m2 s-2 (preto) e de HAILCAST_DIAM_MAX >= 20 mm (magenta).
Os campos do WRF sao maximos no intervalo de saida (10 min); o radar e o satelite sao instantaneos.
O GOES nao tem correcao de paralaxe (topo de ~12 km desloca ~10-15 km para sudeste nesta posicao).

Saidas em radar/figuras/lado_a_lado/: um PNG por horario e lado_a_lado.gif.
Uso: python lado_a_lado.py [membro]  (membro do ensemble; saidas em radar/figuras/lado_a_lado_<membro>/).
"""
import datetime as dt
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
import s3fs
from PIL import Image

from comparar_wrf_radar import radar, recorte_d03
import comparar_wrf_radar
from plotar_radar_mi import AQUI, RELATOS, base

sys.path.insert(0, os.path.join(AQUI, '..'))
from gerar_goes_ir import campo, listar_abi  # noqa: E402  (fica na raiz do projeto)

SAIDA = os.path.join(AQUI, 'figuras', 'lado_a_lado')
INI, FIM = dt.datetime(2026, 8, 29, 20, 30), dt.datetime(2026, 8, 29, 23, 40)
# faixa da trajetoria (~200 x 110 km): do nascimento da celula (20:36, -27,56 / -49,93, a oeste do d03) ao mar a
# leste de Ingleses; o pixel do MaxCAPPI e de ~2 km, e numa janela maior a celula vira poucos pixels
JANELA = (-50.1, -48.1, -28.0, -27.0)
LONS = np.arange(JANELA[0], JANELA[1] + 1e-9, 0.01)
LATS = np.arange(JANELA[3], JANELA[2] - 1e-9, -0.01)
CACHE = os.path.join(AQUI, 'figuras', 'cache_goes_c13')   # um .npy por varredura, na grade LONS x LATS


def goes_c13(t):
    """(horario da varredura, C13 em C) mais proxima de t: do cache; senao do AWS, gravando no cache; senao (None, None)."""
    os.makedirs(CACHE, exist_ok=True)
    tem = {dt.datetime.strptime(n[:13], '%Y%m%d_%H%M'): n for n in os.listdir(CACHE) if n.endswith('.npy')}
    perto = [k for k in tem if abs(k - t) <= dt.timedelta(minutes=5)]
    if perto:
        k = min(perto, key=lambda k: abs(k - t))
        return k, np.load(os.path.join(CACHE, tem[k]))
    try:
        fs = s3fs.S3FileSystem(anon=True, config_kwargs={'connect_timeout': 20})
        c13 = listar_abi(fs, t - dt.timedelta(minutes=10), t + dt.timedelta(minutes=10), 'C13')
        k = min(c13, key=lambda k: abs(k - t))
        ir = campo(fs, c13[k], LONS, LATS)
    except Exception as e:  # AWS fora do ar: o quadro sai sem o GOES
        print(f'GOES indisponivel para {t:%H:%M}: {type(e).__name__}')
        return None, None
    np.save(os.path.join(CACHE, f'{k:%Y%m%d_%H%M}.npy'), ir)
    return k, ir


def main(membro=''):
    saida = f'{SAIDA}_{membro}' if membro else SAIDA
    os.makedirs(saida, exist_ok=True)
    comparar_wrf_radar.INI, comparar_wrf_radar.FIM = INI - dt.timedelta(minutes=20), FIM + dt.timedelta(minutes=20)
    quadros = radar()

    f = nc.Dataset(recorte_d03(membro))
    la, lo = f['XLAT'][0], f['XLONG'][0]
    tw = [dt.datetime.strptime(b''.join(t).decode(), '%Y-%m-%d_%H:%M:%S') for t in f['Times'][:]]

    pngs = []
    t = INI
    while t <= FIM:
        tr, a, ext, _, _ = min(quadros, key=lambda q: abs(q[0] - t))
        i = min(range(len(tw)), key=lambda k: abs(tw[k] - t))
        ts, ir = goes_c13(t)

        fig, axs = plt.subplots(3, 1, figsize=(11, 14), constrained_layout=True)
        axs[0].imshow(a, extent=ext, origin='upper', interpolation='nearest')
        axs[0].set_title(f'Radar Morro da Igreja, MaxCAPPI {tr:%H:%M}', fontsize=10)

        if ir is None:
            ir = np.full((LATS.size, LONS.size), np.nan)
            axs[1].text(0.5, 0.5, 'GOES-19 indisponível (AWS fora do ar)', transform=axs[1].transAxes, ha='center')
        im1 = axs[1].imshow(ir, extent=[LONS[0], LONS[-1], LATS[-1], LATS[0]], origin='upper', cmap='gray_r',
                            vmin=-75, vmax=20)
        if ts is not None:
            axs[1].contour(LONS, LATS, ir, [-60, -50], colors=['red', 'cyan'], linewidths=0.8)
            axs[1].set_title(f'GOES-19 C13 {ts:%H:%M}  (ciano −50 °C, vermelho −60 °C)', fontsize=10)

        im2 = axs[2].pcolormesh(lo, la, np.ma.masked_less(f['REFD_MAX'][i], 20), cmap='turbo', vmin=20, vmax=65)
        axs[2].contour(lo, la, f['UP_HELI_MAX'][i], [75], colors='k', linewidths=1.0)
        axs[2].contour(lo, la, f['HAILCAST_DIAM_MAX'][i], [20], colors='magenta', linewidths=1.2)
        axs[2].plot([lo.min(), lo.max(), lo.max(), lo.min(), lo.min()],
                    [la.min(), la.min(), la.max(), la.max(), la.min()], color='0.4', lw=0.8, ls='--')
        axs[2].set_title(f'WRF {membro or "22/10"} d03 {tw[i]:%H:%M}  REFD_MAX; UH ≥ 75 (preto), HAILCAST ≥ 20 mm (magenta)', fontsize=10)

        for ax in axs:
            base(ax, JANELA)
            ax.tick_params(labelsize=8)
            for nome, y, x, h in RELATOS:
                ax.plot(x, y, 'v', ms=8, mfc='yellow', mec='k', zorder=6)
        fig.colorbar(im1, ax=axs[0], shrink=0.9).ax.set_visible(False)  # so para alinhar o painel do radar
        fig.colorbar(im1, ax=axs[1], shrink=0.9, label='C13 (°C)')
        fig.colorbar(im2, ax=axs[2], shrink=0.9, label='REFD_MAX (dBZ)')
        fig.suptitle(f'29/08/2026  {t:%H:%M} UTC   ▼ relatos de granizo (22:00–23:00 UTC)   --- limite oeste do d03',
                     fontsize=12)
        png = os.path.join(saida, f'lado_a_lado_{t:%Y%m%d_%H%M}.png')
        fig.savefig(png, dpi=90)
        plt.close(fig)
        pngs.append(png)
        print(png)
        t += dt.timedelta(minutes=10)

    imgs = [Image.open(p).convert('P', palette=Image.ADAPTIVE) for p in pngs]
    imgs[0].save(os.path.join(saida, 'lado_a_lado.gif'), save_all=True, append_images=imgs[1:], duration=900, loop=0)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '')
