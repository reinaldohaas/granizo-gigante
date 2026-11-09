# -*- coding: utf-8 -*-
"""Tecnica de Rosenfeld (perfil T-r_e) nas celulas de 29/08/2026, com o script do projeto do RS.

Usa clima_espacial_amas/scripts/13_rosenfeld_celulas.py sem mudar o metodo (reflectancia de 3,9 um a partir de
C07 e C14 com o angulo zenital solar, r_e proxy por pixel, nucleos < -55 C ancorados nos raios, frente x
traseira). Adaptacoes, so de leitura:
  - arquivo noaa-goes19 (GOES-East desde 2025) em vez de noaa-goes16;
  - abre os arquivos com netCDF4 (aqui nao ha h5netcdf);
  - raios lidos de satelite/glm_pontos_sc.csv (ja baixados) em vez do arquivo da AWS;
  - dia 29/08/2026, 10 a 21 UTC, caixa de SC e Misiones.
A tecnica so vale de dia (angulo zenital solar < 78 graus). Em 29/08 o sol nasce ~09:50 UTC na Ilha e ~10:15
no oeste e se poe as 20:58 na Ilha: as celulas da madrugada e a da Ilha (nascida as 20:10) ficam fora.

Uso: python satelite/rosenfeld_29ago.py
Saidas: satelite/rosenfeld/O1_29ago/ (curva_reT, celulas_tabela, figuras)
"""
import os
import sys

import numpy as np
import pandas as pd

RS = r'C:\Users\haas\github\clima_espacial_amas\scripts'
AQUI = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(RS, '13_rosenfeld_celulas.py')

GLM = pd.read_csv(os.path.join(AQUI, 'glm_pontos_sc.csv'), parse_dates=['t_utc'])


def le_glm_local(fs, when, cx, jan_min):
    t0, t1 = pd.Timestamp(when) - pd.Timedelta(minutes=jan_min), pd.Timestamp(when) + pd.Timedelta(minutes=jan_min)
    g = GLM[(GLM.t_utc >= t0) & (GLM.t_utc <= t1)
            & (GLM.lat >= cx['latmin']) & (GLM.lat <= cx['latmax']) & (GLM.lon >= cx['lonmin']) & (GLM.lon <= cx['lonmax'])]
    return g.lat.values, g.lon.values


def main():
    sys.path.insert(0, RS)
    src = open(SRC, encoding='utf-8').read()
    trocas = [('BUCKET="noaa-goes16"', 'BUCKET="noaa-goes19"'),
              ('engine="h5netcdf")\n        prm=', 'engine="netcdf4")\n        prm='),
              ('HORAS_UT=list(range(11,24))', 'HORAS_UT=list(range(10,22))'),
              ('Nada lido — confira acesso ao bucket noaa-goes16', 'Nada lido — confira acesso ao bucket noaa-goes19')]
    for a, b in trocas:
        if a not in src:
            raise SystemExit(f'trecho nao encontrado: {a}')
        src = src.replace(a, b)
    ns = {'__name__': 'rosenfeld_rs', '__file__': SRC}
    exec(compile(src, SRC, 'exec'), ns)
    ns['_le_glm'] = le_glm_local
    ns['ONDAS'] = {'O1_29ago': ('2026-08-29', '2026-08-29')}
    ns['CAIXA'] = dict(latmin=-30.0, latmax=-25.0, lonmin=-56.5, lonmax=-47.0)
    for f in ('_fig_celulas', '_fig_reT'):
        ns[f].__globals__['CAIXA'] = ns['CAIXA']
    sys.argv = ['rosenfeld', '--onda', 'O1_29ago', '--passo', '1', '--outdir', AQUI]
    ns['main'].__globals__.update(ONDAS=ns['ONDAS'], CAIXA=ns['CAIXA'], _le_glm=le_glm_local)
    ns['main']()


if __name__ == '__main__':
    main()
