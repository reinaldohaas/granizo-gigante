# -*- coding: utf-8 -*-
"""Figura limpa das trajetorias com granizo relatado (GLM), para apresentacao.

As quatro trajetorias que passaram sobre municipios com granizo (glm_relatos.csv) em cor, por episodio;
as demais trajetorias de 1 h ou mais em cinza claro, como contexto. Rotulo direto em cada trajetoria.
Saida: satelite/fig_trajetorias_episodios.png (16:9)
"""
import math
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from glm_trajetorias import contornos, municipios

AQUI = os.path.dirname(os.path.abspath(__file__))
EPISODIOS = [((65, 81), '#2a78d6', 'Madrugada · oeste'), ((107,), '#eb6834', 'Manhã · Meio-Oeste'),
             ((185,), '#13895f', 'Fim de tarde · Grande Florianópolis')]
MUN = ['Abelardo Luz', 'Ipuaçu', 'Bom Jesus', 'Entre Rios', 'Ouro Verde', 'Joaçaba', 'Campos Novos',
       'Biguaçu', 'Florianópolis']


def main():
    cel = pd.read_csv(os.path.join(AQUI, 'glm_celulas.csv'), parse_dates=['t']).dropna(subset=['traj'])
    tr = pd.read_csv(os.path.join(AQUI, 'glm_trajetorias.csv')).set_index('id')
    fig, ax = plt.subplots(figsize=(16, 9), constrained_layout=True)
    contornos(ax, 'America_do_Sul.shp', color='#8a96a6', lw=0.8)
    contornos(ax, 'BR_Estados.shp', color='#5d6b7c', lw=1.0)
    for tid, g in cel.groupby('traj'):
        if tr.loc[int(tid), 'dist_km'] >= 60:
            ax.plot(g.lon, g.lat, '-', color='#c9d0d8', lw=0.9, zorder=1)
    for ids, cor, nome in EPISODIOS:
        for tid in ids:
            g = cel[cel.traj == tid].sort_values('t')
            t = tr.loc[tid]
            ax.plot(g.lon, g.lat, '-', color=cor, lw=4, zorder=3, solid_capstyle='round')
            ax.plot(g.lon.iloc[-1], g.lat.iloc[-1], '>', color=cor, ms=11, zorder=4)
            ax.plot(g.lon.iloc[0], g.lat.iloc[0], 'o', color=cor, ms=8, zorder=4)
            ax.annotate(f"{tid}  {t.inicio[6:]} UTC", (g.lon.iloc[0], g.lat.iloc[0]),
                        xytext=(-8, -24) if tid == 185 else (-8, 8),
                        textcoords='offset points', ha='right', fontsize=13, color='#14202e', weight='bold')
    cent = municipios()
    for n in MUN:
        lo, la = cent[n]
        ax.plot(lo, la, '^', color='#b5127f', ms=10, mec='white', mew=0.8, zorder=5)
    for n, dx, dy in [('Joaçaba', 6, 6), ('Campos Novos', 6, -14), ('Biguaçu', -6, 8), ('Florianópolis', 6, -14),
                      ('Abelardo Luz', 0, 9), ('Ipuaçu', -8, -16)]:
        lo, la = cent[n]
        ax.annotate(n, (lo, la), xytext=(dx, dy), textcoords='offset points', fontsize=12, color='#5a0a4a',
                    ha='left' if dx >= 0 else 'right')
    hs = [plt.Line2D([], [], color=c, lw=4, label=n) for _, c, n in EPISODIOS]
    hs += [plt.Line2D([], [], color='#c9d0d8', lw=1.5, label='outras células com raios (≥ 1 h, ≥ 60 km)'),
           plt.Line2D([], [], marker='^', ls='', color='#b5127f', ms=10, label='granizo relatado')]
    ax.legend(handles=hs, loc='lower left', fontsize=12, frameon=True, framealpha=0.92)
    ax.set_xlim(-56.5, -47.2)
    ax.set_ylim(-29.4, -25.6)
    ax.set_aspect(1 / math.cos(math.radians(-27.5)))
    ax.tick_params(labelsize=11)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    fig.savefig(os.path.join(AQUI, 'fig_trajetorias_episodios.png'), dpi=120, facecolor='white')
    print('->', os.path.join(AQUI, 'fig_trajetorias_episodios.png'))


if __name__ == '__main__':
    main()
