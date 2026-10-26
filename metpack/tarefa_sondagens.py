"""
tarefa_sondagens.py - Tarefa de sondagens em Python (mesmo roteiro de tarefa_sondagens.m)

Baseado nos programas de Kerry Emanuel em https://texmex.mit.edu/pub/emanuel/soundings/
(getsounding.m, skewt.m, tcon.m e wyoming.f), na versão Python:
  getsounding_wyoming.py - baixa a sondagem e grava sounding.txt para o wyoming.f
  skewt.py               - diagrama Skew-T de Emanuel: skewt(p, T, UR 0-1)
  tcon_emanuel.py        - roda o wyoming.f e desenha as matrizes de flutuabilidade

Como usar:
  1. Troque as três sondagens em CASOS pelas SUAS (estação e data).
  2. Rode (usa o wyoming.f se houver gfortran; senão, o wyoming.py):
       uv run --with numpy --with matplotlib python metpack/tarefa_sondagens.py
  3. Para cada caso, na pasta emanuel_AAAAMMDD_HH ficam skewt.png e matrizes_emanuel.png,
     e na tela aparecem a fonte dos dados e as CAPE reversível e pseudoadiabática.

Os casos abaixo são apenas o EXEMPLO do tutorial (Porto Alegre, dezembro de 1995).
"""
import os
import shutil
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from getsounding_wyoming import getsounding_wyoming
from skewt import skewt
from tcon_emanuel import tcon_emanuel

CASOS = [
    # regime       estação  (ano, mês, dia, hora UTC)
    ('ESTÁVEL',    83899,   (2026, 8, 26, 12)),
    ('NEUTRA',     83899,   (2026, 8, 31, 0)),
    ('INSTÁVEL',   83899,   (2026, 8, 28, 12)),
]
CORTE_EMANUEL = False   # False = sem o piso artificial de -4 K do wyoming.f original

for regime, est, (a, m, d, h) in CASOS:
    rotulo = f'{regime}: {est} {d:02d}/{m:02d}/{a:04d} {h:02d}Z'
    print(f'\n=== {rotulo} ===')
    pasta = f'emanuel_{a:04d}{m:02d}{d:02d}_{h:02d}'
    os.makedirs(pasta, exist_ok=True)

    data, header, status, fonte = getsounding_wyoming(est, a, m, d, h, pasta_saida=pasta)
    if status != 1:
        print(f'Sem dados para {rotulo}; caso ignorado.')
        continue

    # Skew-T de Emanuel: p (hPa), T (C), umidade relativa (0-1)
    ok = np.all(np.isfinite(data[:, [0, 2, 4]]), axis=1)
    skewt(data[ok, 0], data[ok, 2], data[ok, 4] / 100, title=rotulo, savepath=os.path.join(pasta, 'skewt.png'))

    # Matrizes de flutuabilidade (wyoming.f)
    E = tcon_emanuel(pasta, rotulo, CORTE_EMANUEL)
    c = E['cape']
    i_rev, i_pse = int(np.argmax(c[:, 5])), int(np.argmax(c[:, 6]))
    print(f'Fonte dos dados: {fonte}')
    print(f'CAPE reversível na superfície: {c[0, 5]:.1f} J/kg | máxima: {c[i_rev, 5]:.1f} J/kg (origem {c[i_rev, 0]:.0f} hPa)')
    print(f'CAPE pseudoadiabática na superfície: {c[0, 6]:.1f} J/kg | máxima: {c[i_pse, 6]:.1f} J/kg (origem {c[i_pse, 0]:.0f} hPa)')
    print(f'Figuras: {pasta}/skewt.png e {pasta}/matrizes_emanuel.png')
