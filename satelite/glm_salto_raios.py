# -*- coding: utf-8 -*-
"""As celulas com granizo tiveram mais raios que as outras, ou um salto de raios antes do granizo?

1) Ranking: para cada trajetoria de 1 h ou mais (glm_trajetorias.csv), o maximo de flashes em 10 min e o total;
   posicao das trajetorias com granizo relatado (65, 81, 107, 185) entre todas.
2) Salto de raios (metodo 2-sigma de Schultz et al. 2009, adaptado a 10 min): DFRDT = variacao da taxa entre
   intervalos; ha salto quando DFRDT passa de 2 desvios-padrao dos 5 intervalos anteriores.
   Mostra a serie e os saltos das quatro trajetorias, com a hora da passagem sobre os municipios.

Saidas: satelite/glm_ranking.csv, satelite/glm_salto_raios.csv, satelite/glm_salto_raios.png
"""
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
COM_GRANIZO = {65: '22:00', 81: '06:50', 107: '10:00', 185: '22:10'}
PASSAGEM = {65: '2026-08-29 08:10', 81: '2026-08-29 06:50', 107: '2026-08-29 10:00', 185: '2026-08-29 22:10'}


def main():
    cel = pd.read_csv(os.path.join(AQUI, 'glm_celulas.csv'), parse_dates=['t']).dropna(subset=['traj'])
    cel['traj'] = cel.traj.astype(int)
    g = cel.groupby('traj').flashes
    rk = pd.DataFrame({'max_10min': g.max(), 'total': g.sum(), 'intervalos': g.size()})
    rk['pct_max'] = rk.max_10min.rank(pct=True).round(3) * 100
    rk['pct_total'] = rk.total.rank(pct=True).round(3) * 100
    rk.to_csv(os.path.join(AQUI, 'glm_ranking.csv'))
    print('trajetorias:', len(rk), '| mediana do maximo em 10 min:', rk.max_10min.median())
    print(rk.loc[list(COM_GRANIZO)].to_string())

    linhas = []
    fig, axs = plt.subplots(2, 2, figsize=(14, 7), constrained_layout=True, sharey=False)
    for ax, tid in zip(axs.flat, COM_GRANIZO):
        s = cel[cel.traj == tid].set_index('t').flashes.sort_index()
        s = s.resample('10min').sum()
        dfrdt = s.diff()
        lim = dfrdt.rolling(5).std().shift(1) * 2
        salto = (dfrdt > lim) & (s >= 20)
        for t in s.index:
            linhas.append(dict(traj=tid, t=t, flashes=int(s[t]), dfrdt=dfrdt[t], limite=lim[t], salto=bool(salto[t])))
        ax.bar(s.index, s.values, width=0.006, color='#2a78d6')
        ax.plot(s.index[salto], s[salto], 'v', color='#b5127f', ms=9, label='salto (2σ)')
        ax.axvline(pd.Timestamp(PASSAGEM[tid]), color='#1f1f1e', ls='--', lw=1.2, label='passagem sobre os relatos')
        ax.set_title(f'trajetória {tid}: flashes por 10 min')
        ax.legend(fontsize=8)
        ax.tick_params(axis='x', labelrotation=30, labelsize=8)
    pd.DataFrame(linhas).to_csv(os.path.join(AQUI, 'glm_salto_raios.csv'), index=False)
    fig.savefig(os.path.join(AQUI, 'glm_salto_raios.png'), dpi=120)
    sal = pd.DataFrame(linhas)
    for tid in COM_GRANIZO:
        x = sal[(sal.traj == tid) & sal.salto]
        print(tid, 'saltos em:', ', '.join(f'{t:%H:%M}' for t in x.t) or 'nenhum')


if __name__ == '__main__':
    main()
