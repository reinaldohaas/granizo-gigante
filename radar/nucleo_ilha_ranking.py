# -*- coding: utf-8 -*-
"""O nucleo de radar da celula da Ilha foi mais intenso que os das outras celulas de 29/08?

MaxCAPPI do Morro da Igreja (sem calibracao em dBZ). Classes de cor da REDEMET:
  vermelho = R >= 200, G <= 140, B < 150   (~50-60 dBZ)
  magenta  = R >= 200, G <= 140, B >= 150  (o topo da escala, ~60 dBZ ou mais)
Cada quadro: nucleos = grupos conexos de pixels vermelhos ou magenta (>= 3 pixels); para cada um, area total
e area magenta. O nucleo da Ilha e o que esta a ate 25 km de Biguacu ou do norte da Ilha as 22:16 e 22:36.
Posicao dele entre todos os nucleos do dia (08 UTC de 29/08 a 06 UTC de 30/08), em area magenta e total.

Saida: radar/nucleos_mi_dia.csv e resumo no terminal.
"""
import csv
import math
import os
from datetime import datetime

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA = os.path.join(AQUI, 'mi', 'maxcappi')
ILHA = [(-48.655, -27.494), (-48.46, -27.43)]


def km(lo1, la1, lo2, la2):
    return math.hypot((lo2 - lo1) * 111.32 * math.cos(math.radians(la1)), (la2 - la1) * 110.57)


def main():
    linhas = []
    for r in csv.DictReader(open(os.path.join(PASTA, 'quadros.csv'), encoding='utf-8')):
        t = datetime.strptime(r['data_utc'], '%Y-%m-%d %H:%M:%S')
        ext = [float(r[k]) for k in ('lon_min', 'lon_max', 'lat_min', 'lat_max')]
        a = np.array(Image.open(os.path.join(PASTA, r['arquivo'])).convert('RGBA')).astype(int)
        R, G, B, A = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
        nuc = (A > 0) & (R >= 200) & (G <= 140)
        mag = nuc & (B >= 150)
        lab, n = ndimage.label(nuc, structure=np.ones((3, 3)))
        ny, nx = nuc.shape
        dx = (ext[1] - ext[0]) / nx * 111.32 * math.cos(math.radians(-28))
        dy = (ext[3] - ext[2]) / ny * 110.57
        for c in range(1, n + 1):
            k = lab == c
            if k.sum() < 3:
                continue
            jj, ii = np.nonzero(k)
            lo = ext[0] + (ii.mean() + 0.5) / nx * (ext[1] - ext[0])
            la = ext[3] - (jj.mean() + 0.5) / ny * (ext[3] - ext[2])
            linhas.append(dict(t=t, lon=round(lo, 3), lat=round(la, 3), area_km2=round(k.sum() * dx * dy, 1),
                               magenta_km2=round((k & mag).sum() * dx * dy, 1),
                               ilha=t.strftime('%H:%M') in ('22:16', '22:36') and min(km(x, y, lo, la) for x, y in ILHA) <= 25))
    df = pd.DataFrame(linhas)
    df.to_csv(os.path.join(AQUI, 'nucleos_mi_dia.csv'), index=False)
    print(len(df), 'nucleos em', df.t.nunique(), 'quadros')
    for col in ('magenta_km2', 'area_km2'):
        df['pct_' + col] = df[col].rank(pct=True) * 100
    print(df[df.ilha][['t', 'lon', 'lat', 'area_km2', 'magenta_km2', 'pct_area_km2', 'pct_magenta_km2']].round(1).to_string(index=False))
    print('nucleos com alguma area magenta:', int((df.magenta_km2 > 0).sum()), 'de', len(df))
    print('maiores areas magenta do dia:')
    print(df.sort_values('magenta_km2', ascending=False).head(8)[['t', 'lon', 'lat', 'area_km2', 'magenta_km2']].to_string(index=False))


if __name__ == '__main__':
    main()
