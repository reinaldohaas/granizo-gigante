# -*- coding: utf-8 -*-
"""Resumo dos perfis T-r_e (Rosenfeld) de 29/08/2026 em grupos, contra o caso do RS (mesmo script, mesmos criterios).

Grupos de 29/08: 11 UTC (sol baixo, angulo zenital ~75-80 graus), 12-19 UTC com raios, 12-19 UTC sem raios.
RS: ondas O1 (toros 01-04/05) e O2 (surto 06-08/05) de clima_espacial_amas.
Mediana do r_e proxy por faixa de temperatura do topo, celula inteira; faixa sombreada = quartis entre celulas.

Saidas: satelite/rosenfeld_resumo.csv e radar/figuras/rosenfeld_resumo.png
"""
import glob
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
RS = r'C:\Users\haas\github\clima_espacial_amas\resultados\rosenfeld_celulas'


def le(arq_curva):
    c = pd.read_csv(arq_curva)
    c = c[c.metade == 'inteira']
    pasta = os.path.dirname(arq_curva)
    t = pd.concat([pd.read_csv(f) for f in glob.glob(os.path.join(pasta, 'celulas_tabela*.csv'))])
    return c.merge(t[['celula', 'quando', 'eletrificada']], on=['celula', 'quando'])


def main():
    ev = le(os.path.join(AQUI, 'rosenfeld_celulas', 'O1_29ago', 'curva_reT_O1_29ago.csv'))
    hora = ev.quando.str[11:13].astype(int)
    rs = pd.concat([le(f) for f in glob.glob(os.path.join(RS, 'O[12]_*', 'curva_reT_*.csv'))])
    grupos = {
        '29/08, 11 UTC (sol baixo)': ev[hora == 11],
        '29/08, 12–19 UTC, com raios': ev[(hora >= 12) & (hora <= 19) & (ev.eletrificada == 1)],
        '29/08, 12–19 UTC, sem raios (mar)': ev[(hora >= 12) & (hora <= 19) & (ev.eletrificada == 0)],
        'RS, maio de 2024, com raios': rs[rs.eletrificada == 1],
    }
    cores = ['#9a9a9a', '#c0392b', '#2e86c1', '#222222']
    linhas = []
    fig, ax = plt.subplots(figsize=(6.4, 6))
    for (nome, g), cor in zip(grupos.items(), cores):
        q = g.groupby('T_bin').re_proxy_med.quantile([.25, .5, .75]).unstack()
        n = g.groupby('T_bin').size()
        q = q[n >= 3]
        estilo = '--' if nome.startswith('RS') else '-'
        ax.plot(q[0.5], q.index, estilo, color=cor, lw=2.2, marker='o', ms=4,
                label=f'{nome} ({g.groupby(["celula", "quando"]).ngroups} perfis)')
        ax.fill_betweenx(q.index, q[0.25], q[0.75], color=cor, alpha=.12)
        for T, r in q.iterrows():
            linhas.append(dict(grupo=nome, T_bin=T, re_p25=r[0.25], re_med=r[0.5], re_p75=r[0.75], n=int(n[T])))
    ax.axvline(14, color='#888', lw=1, ls=':')
    ax.text(13.85, -68, '14 µm: início da\nchuva (Rosenfeld)', fontsize=8, color='#555', va='top', ha='right')
    ax.invert_yaxis()
    ax.set_ylim(-15, -70)
    ax.set_xlabel('r_e proxy (µm), reflectância de 3,9 µm')
    ax.set_ylabel('Temperatura do topo (°C)')
    ax.set_title('Perfis T–r_e: 29/08/2026 × caso do RS', fontsize=11)
    ax.grid(alpha=.3)
    ax.legend(fontsize=8, loc='lower right')
    fig.tight_layout()
    fig.savefig(os.path.join(AQUI, '..', 'radar', 'figuras', 'rosenfeld_resumo.png'), dpi=150)
    pd.DataFrame(linhas).to_csv(os.path.join(AQUI, 'rosenfeld_resumo.csv'), index=False, float_format='%.2f')
    print(pd.DataFrame(linhas).pivot(index='T_bin', columns='grupo', values='re_med').round(1).to_string())


if __name__ == '__main__':
    main()
