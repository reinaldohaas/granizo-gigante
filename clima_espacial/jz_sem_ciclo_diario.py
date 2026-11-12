# -*- coding: utf-8 -*-
"""Jz da rede sem o ciclo diario (Sq), para reavaliar o "maior de 27 dias as 12-18 UTC".

A serie original (jz_rede_14_estacoes_2026.py) tira so uma mediana movel de 1440 min, que nao remove a
variacao diaria regular das correntes ionosfericas (Sq), maxima perto do meio-dia local (~15 UTC).
Aqui o ciclo diario e estimado de dois jeitos e subtraido:
  A) mediana, por horario UTC, de todos os dias da serie;
  B) media, por horario UTC, dos 5 dias mais calmos pelo Kp (soma diaria) na janela com Kp.
Para cada dia: media de 12-18 UTC e de 18-24 UTC, bruta e sem o ciclo, e a posicao de 29/08.
Tambem o desvio padrao entre dias por horario, para dar a anomalia em unidades de variabilidade.

Uso: python clima_espacial/jz_sem_ciclo_diario.py
Saidas: clima_espacial/resultados/jz_sem_ciclo_diario.csv e .txt (sem figura: o matplotlib do py312 cai com erro nativo)
"""
from pathlib import Path

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

AQUI = Path(__file__).resolve().parent
RES = AQUI / 'resultados'
DIA = pd.Timestamp('2026-08-29')


def janelas(s, nome):
    d = s.to_frame('v')
    d['dia'] = d.index.normalize()
    h = d.index.hour
    a = d[(h >= 12) & (h < 18)].groupby('dia').v.mean().rename(f'{nome}_12_18')
    b = d[(h >= 18)].groupby('dia').v.mean().rename(f'{nome}_18_24')
    return pd.concat([a, b], axis=1)


def posicao(col, dias, maior_em_modulo=True):
    x = dias[col].dropna()
    chave = x.abs() if maior_em_modulo else x
    rank = int((chave > chave.loc[DIA]).sum()) + 1
    return x.loc[DIA], x.median(), rank, len(x)


def main():
    jz = pd.read_csv(AQUI / 'dados' / 'jz' / 'rede_14_estacoes_currents_20260801_20260910.csv',
                     parse_dates=['datetime']).set_index('datetime')['Jz_nA_m2']
    esp = pd.read_csv(RES / 'series_espaciais_20260815_20260905.csv', parse_dates=['tempo']).set_index('tempo')

    tod = jz.index.hour * 60 + jz.index.minute
    tab = jz.to_frame('jz')
    tab['tod'] = tod
    tab['dia'] = jz.index.normalize()
    largo = tab.pivot_table(index='dia', columns='tod', values='jz')
    completos = largo.dropna(thresh=int(0.9 * largo.shape[1])).index

    # A) mediana por horario, todos os dias completos
    sq_a = largo.loc[completos].median()
    # B) 5 dias mais calmos pelo Kp
    kp = esp['Kp'].resample('1D').sum(min_count=6)
    kp = kp[kp.index.isin(completos)]
    calmos = kp.nsmallest(5).index
    sq_b = largo.loc[calmos].mean()
    dp = largo.loc[completos].std()

    anom_a = jz - sq_a.reindex(tod).values
    anom_b = jz - sq_b.reindex(tod).values
    z = anom_a / dp.reindex(tod).values

    dias = pd.concat([janelas(jz, 'bruto'), janelas(anom_a, 'sem_ciclo_A'),
                      janelas(anom_b, 'sem_ciclo_B'), janelas(z, 'z_A')], axis=1)
    dias = dias.loc[dias.index.isin(completos)]
    dias.to_csv(RES / 'jz_sem_ciclo_diario.csv', float_format='%.3f')

    linhas = ['Jz da rede (nA/m2): 29/08 contra os outros dias, antes e depois de tirar o ciclo diario',
              f'dias completos: {len(completos)} ({completos.min():%d/%m} a {completos.max():%d/%m})',
              f'dias calmos pelo Kp (metodo B): {", ".join(f"{d:%d/%m}" for d in calmos)}',
              '',
              f'{"serie":<22}{"29/08":>9}{"mediana":>10}{"posicao":>10}  (posicao pelo modulo; 1 = maior)']
    for col in dias.columns:
        v, med, r, n = posicao(col, dias)
        linhas.append(f'{col:<22}{v:9.2f}{med:10.2f}{r:>6d}/{n}')
    # mesma janela de 27 dias da afirmacao original (15/08 a 10/09)
    j27 = dias.loc['2026-08-15':'2026-09-10']
    linhas += ['', f'so 15/08 a 10/09 ({len(j27)} dias), como na afirmacao original:']
    for col in ['bruto_12_18', 'sem_ciclo_A_12_18', 'sem_ciclo_B_12_18', 'z_A_12_18']:
        x = j27[col]
        r = int((x.abs() > abs(x.loc[DIA])).sum()) + 1
        linhas.append(f'{col:<22}{x.loc[DIA]:9.2f}{x.median():10.2f}{r:>6d}/{len(x)}')
    linhas += ['', f'ciclo diario A, 12-18 UTC: media {sq_a[(sq_a.index >= 720) & (sq_a.index < 1080)].mean():.2f}; '
               f'18-24 UTC: {sq_a[sq_a.index >= 1080].mean():.2f}; 00-12 UTC: {sq_a[sq_a.index < 720].mean():.2f}']
    txt = '\n'.join(linhas)
    (RES / 'jz_sem_ciclo_diario.txt').write_text(txt, encoding='utf-8')
    print(txt)


if __name__ == '__main__':
    main()
