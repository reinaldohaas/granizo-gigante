# -*- coding: utf-8 -*-
"""Trajetorias dos nucleos intensos em toda Santa Catarina, 29/08/2026, juntando dois radares do DECEA.

  sg = Santiago (RS): cobre o oeste de SC (ate -50,8)
  mi = Morro da Igreja (SC): cobre o centro e o leste (desde -53,7)

Mesma definicao de nucleo de plotar_radar_mi.py: pixel vermelho/magenta do MaxCAPPI da REDEMET
(R >= 200 e G <= 140, ~>= 50 dBZ, sem calibracao). Pixels que aparecem em mais de 40% dos quadros sao
tratados como eco fixo (terreno) e descartados.

Rastreio: em cada quadro os pixels de nucleo sao agrupados (vizinhanca 8) num mosaico lat/lon de 0,02 grau;
cada grupo vira um centroide. Grupos de quadros consecutivos (ate 40 min) se ligam ao mais proximo a menos
de 60 km, preferindo a direcao do deslocamento anterior. Trajetorias com 3 ou mais quadros sao mantidas.

Saidas (radar/figuras/ e radar/):
  estado_trajetorias.png       mosaico dos nucleos colorido pelo horario + trajetorias numeradas
  estado_trajetorias.csv       uma linha por trajetoria: inicio, fim, duracao, distancia, velocidade, rumo
  estado_nucleos.csv           todos os centroides por quadro
"""
import csv
import math
import os
from datetime import datetime, timedelta

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy import ndimage

from plotar_radar_mi import base, nucleo, RELATOS

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, 'figuras')
INI, FIM = datetime(2026, 8, 29, 12), datetime(2026, 8, 30, 4)
GRADE = (-54.0, -48.0, -29.6, -25.8)          # lon0, lon1, lat0, lat1 (SC)
D = 0.02                                       # grau
NX = int(round((GRADE[1] - GRADE[0]) / D))
NY = int(round((GRADE[3] - GRADE[2]) / D))
JANELA_MIN = 12                                # quadros dos dois radares a ate 12 min viram um so instante
MAX_KM, MAX_GAP = 60.0, timedelta(minutes=40)
MIN_PIX = 3                                    # grupo minimo (pixels de 0,02 grau)


def quadros(radar):
    pasta = os.path.join(AQUI, radar, 'maxcappi')
    with open(os.path.join(pasta, 'quadros.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            t = datetime.strptime(r['data_utc'], '%Y-%m-%d %H:%M:%S')
            if INI <= t <= FIM:
                ext = [float(r[k]) for k in ('lon_min', 'lon_max', 'lat_min', 'lat_max')]
                yield t, os.path.join(pasta, r['arquivo']), ext


def mascara_grade(arq, ext):
    """Nucleos do quadro levados ao mosaico de 0,02 grau (pixel -> centro em lat/lon)."""
    a = np.array(Image.open(arq).convert('RGBA'))
    m = nucleo(a)
    ny, nx = m.shape
    jj, ii = np.nonzero(m)
    lon = ext[0] + (ii + 0.5) / nx * (ext[1] - ext[0])
    lat = ext[3] - (jj + 0.5) / ny * (ext[3] - ext[2])
    g = np.zeros((NY, NX), bool)
    ix = ((lon - GRADE[0]) / D).astype(int)
    iy = ((GRADE[3] - lat) / D).astype(int)
    ok = (ix >= 0) & (ix < NX) & (iy >= 0) & (iy < NY)
    g[iy[ok], ix[ok]] = True
    return g


def km(la1, lo1, la2, lo2):
    dx = (lo2 - lo1) * 111.32 * math.cos(math.radians(0.5 * (la1 + la2)))
    dy = (la2 - la1) * 110.57
    return math.hypot(dx, dy), dx, dy


def main():
    os.makedirs(SAIDA, exist_ok=True)
    # 1) mosaico por instante: frames dos dois radares agrupados em janelas de 12 min
    frames = sorted([(t, r, arq, ext) for r in ('sg', 'mi') for t, arq, ext in quadros(r)])
    instantes = []
    for t, r, arq, ext in frames:
        g = mascara_grade(arq, ext)
        if instantes and (t - instantes[-1][0]) <= timedelta(minutes=JANELA_MIN):
            instantes[-1][1] |= g
            instantes[-1][2].add(r)
        else:
            instantes.append([t, g, {r}])
    pilha = np.array([g for _, g, _ in instantes])
    fixo = pilha.mean(axis=0) > 0.4
    print(f'{len(instantes)} instantes; pixels de eco fixo descartados: {int(fixo.sum())}')

    # 2) centroides
    lon_c = GRADE[0] + (np.arange(NX) + 0.5) * D
    lat_c = GRADE[3] - (np.arange(NY) + 0.5) * D
    nucleos = []
    primeira = np.full((NY, NX), np.nan)
    for k, (t, g, rad) in enumerate(instantes):
        g = g & ~fixo
        h = (t - INI).total_seconds() / 3600
        primeira[g & np.isnan(primeira)] = h
        lab, n = ndimage.label(g, structure=np.ones((3, 3)))
        for c in range(1, n + 1):
            jj, ii = np.nonzero(lab == c)
            if jj.size < MIN_PIX:
                continue
            nucleos.append(dict(k=k, t=t, lat=float(lat_c[jj].mean()), lon=float(lon_c[ii].mean()),
                                pix=int(jj.size), radares='+'.join(sorted(rad))))

    # 3) rastreio guloso: cada nucleo continua a trajetoria aberta mais proxima
    trajs = []
    for nu in sorted(nucleos, key=lambda x: x['t']):
        melhor, dmin = None, MAX_KM
        for tr in trajs:
            ult = tr[-1]
            if ult['t'] >= nu['t'] or nu['t'] - ult['t'] > MAX_GAP:
                continue
            d, dx, dy = km(ult['lat'], ult['lon'], nu['lat'], nu['lon'])
            if len(tr) >= 2:  # penaliza quem anda contra o rumo anterior
                _, px, py = km(tr[-2]['lat'], tr[-2]['lon'], ult['lat'], ult['lon'])
                if px * dx + py * dy < 0:
                    d *= 1.5
            if d < dmin:
                melhor, dmin = tr, d
        if melhor is not None and all(x['t'] != nu['t'] for x in melhor):
            melhor.append(nu)
        else:
            trajs.append([nu])
    trajs = [tr for tr in trajs if len(tr) >= 3]
    trajs.sort(key=lambda tr: tr[0]['t'])

    linhas = []
    for i, tr in enumerate(trajs, 1):
        a, b = tr[0], tr[-1]
        dist, dx, dy = km(a['lat'], a['lon'], b['lat'], b['lon'])
        dur = (b['t'] - a['t']).total_seconds()
        rumo = (math.degrees(math.atan2(dx, dy)) + 360) % 360  # para onde vai
        linhas.append(dict(id=i, inicio=f"{a['t']:%d/%m %H:%M}", lat0=round(a['lat'], 2), lon0=round(a['lon'], 2),
                           fim=f"{b['t']:%d/%m %H:%M}", lat1=round(b['lat'], 2), lon1=round(b['lon'], 2),
                           quadros=len(tr), duracao_h=round(dur / 3600, 2), dist_km=round(dist),
                           vel_m_s=round(dist * 1000 / dur, 1) if dur else 0, rumo_graus=round(rumo),
                           pix_max=max(x['pix'] for x in tr)))
    with open(os.path.join(AQUI, 'estado_trajetorias.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    with open(os.path.join(AQUI, 'estado_nucleos.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['k', 't', 'lat', 'lon', 'pix', 'radares'])
        w.writeheader()
        w.writerows(nucleos)
    for l in linhas:
        print(l)

    # 4) figura
    fig, ax = plt.subplots(figsize=(14, 8.4), constrained_layout=True)
    im = ax.imshow(np.ma.masked_invalid(primeira), extent=GRADE, origin='upper', cmap='viridis',
                   interpolation='nearest', vmin=0, vmax=(FIM - INI).total_seconds() / 3600, alpha=0.85)
    base(ax, (GRADE[0], GRADE[1], GRADE[2] + 0.2, GRADE[3]))
    for l, tr in zip(linhas, trajs):
        if l['dist_km'] < 40:
            continue
        ax.plot([x['lon'] for x in tr], [x['lat'] for x in tr], '-', color='#1f1f1e', lw=1.2)
        ax.plot(tr[-1]['lon'], tr[-1]['lat'], '>', color='#1f1f1e', ms=5)
        ax.annotate(f"{l['id']}  {l['inicio'][6:]}", (tr[0]['lon'], tr[0]['lat']), xytext=(-4, 5),
                    textcoords='offset points', fontsize=8, ha='right', color='#1f1f1e')
    for nome, la, lo, _ in RELATOS:
        ax.plot(lo, la, '^', color='#c4129f', ms=6)
    ax.plot(-54.930257, -29.225213, 's', color='0.2', ms=5)
    ax.plot(-49.471816, -28.128373, 's', color='0.2', ms=5)
    cb = fig.colorbar(im, ax=ax, shrink=0.8)
    cb.set_label(f'horas após {INI:%d/%m %H:%M} UTC (1ª vez com núcleo)')
    ax.set_title('Núcleos intensos (~≥50 dBZ) no mosaico Santiago + Morro da Igreja, 29/08 12 UTC – 30/08 04 UTC\n'
                 'linhas: trajetórias com 40 km ou mais (número e hora de início); ▲ relatos na Grande Florianópolis',
                 fontsize=11)
    fig.savefig(os.path.join(SAIDA, 'estado_trajetorias.png'), dpi=130)
    print('->', os.path.join(SAIDA, 'estado_trajetorias.png'))


if __name__ == '__main__':
    main()
