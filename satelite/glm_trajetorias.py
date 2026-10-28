# -*- coding: utf-8 -*-
"""Trajetorias das celulas eletricamente ativas sobre SC em 29/08/2026, a partir dos flashes do GLM.

Celula = aglomerado de flashes num intervalo de 10 min: grade de 0,1 grau, celas com >= MIN_FL flashes,
vizinhanca 8. Rastreio: o aglomerado continua a trajetoria aberta mais proxima a menos de MAX_KM, com ate
20 min de intervalo, penalizando quem volta contra o rumo anterior. Trajetorias de 1 h ou mais sao mantidas.

Os municipios com granizo (imprensa e Defesa Civil) sao localizados pelo centroide no shapefile do IBGE.

Saidas (satelite/):
  glm_trajetorias.csv    uma linha por trajetoria (inicio, fim, duracao, distancia, velocidade, rumo, flashes)
  glm_celulas.csv        os aglomerados de cada intervalo, com o id da trajetoria
  glm_trajetorias.png    mapa: densidade de flashes do dia, trajetorias coloridas pela hora, municipios
"""
import csv
import math
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapefile
from scipy import ndimage

AQUI = os.path.dirname(os.path.abspath(__file__))
SHP = os.path.join(AQUI, '..', 'shp_ibge')
GRADE = (-58.0, -46.0, -30.5, -25.0)       # lon0, lon1, lat0, lat1
D, PASSO = 0.1, '10min'
MIN_FL, MAX_KM, MAX_GAP_MIN, MIN_DUR_H = 5, 45.0, 20, 1.0
INI, FIM = pd.Timestamp('2026-08-28 18:00'), pd.Timestamp('2026-08-30 06:00')

# relatos de granizo: municipio, quando (texto da fonte), hora UTC aproximada para o grafico
RELATOS = [
    ('Abelardo Luz', 'madrugada 29/08', 7), ('Ipuaçu', 'madrugada 29/08', 7), ('Bom Jesus', 'madrugada 29/08', 7),
    ('Entre Rios', 'madrugada 29/08', 7), ('Ouro Verde', 'madrugada 29/08', 7),
    ('Joaçaba', 'alerta 07:12 local', 10), ('Campos Novos', 'alerta 07:12 local', 10),
    ('Lages', '29–31/08, sem hora', None), ('Bom Retiro', '29–31/08, sem hora', None),
    ('Biguaçu', '~18h local', 21), ('Florianópolis', '22:00–23:00 UTC', 22),
]


def municipios():
    r = shapefile.Reader(os.path.join(SHP, 'SC_Municipios_2022.shp'), encoding='utf-8')
    campos = [f[0] for f in r.fields[1:]]
    col = next(c for c in campos if c.upper().startswith('NM_MUN'))
    cent = {}
    for rec, shp in zip(r.records(), r.shapes()):
        p = np.array(shp.points)
        cent[rec[campos.index(col)]] = (p[:, 0].mean(), p[:, 1].mean())
    return cent


def contornos(ax, arquivo, **kw):
    for s in shapefile.Reader(os.path.join(SHP, arquivo)).shapes():
        p = np.array(s.points)
        for a, b in zip(s.parts, list(s.parts[1:]) + [len(p)]):
            ax.plot(p[a:b, 0], p[a:b, 1], **kw)


def km(la1, lo1, la2, lo2):
    dx = (lo2 - lo1) * 111.32 * math.cos(math.radians(0.5 * (la1 + la2)))
    dy = (la2 - la1) * 110.57
    return math.hypot(dx, dy), dx, dy


def main():
    f = pd.read_csv(os.path.join(AQUI, 'glm_pontos_sc.csv'), parse_dates=['t_utc'])
    f = f[(f.t_utc >= INI) & (f.t_utc <= FIM)].drop_duplicates()
    print(len(f), 'flashes', f.t_utc.min(), '..', f.t_utc.max())
    nx = int(round((GRADE[1] - GRADE[0]) / D))
    ny = int(round((GRADE[3] - GRADE[2]) / D))
    f['ix'] = ((f.lon - GRADE[0]) / D).astype(int).clip(0, nx - 1)
    f['iy'] = ((GRADE[3] - f.lat) / D).astype(int).clip(0, ny - 1)
    f['bin'] = f.t_utc.dt.floor(PASSO)

    celulas = []
    for t, g in f.groupby('bin'):
        h = np.zeros((ny, nx), int)
        np.add.at(h, (g.iy.values, g.ix.values), 1)
        lab, n = ndimage.label(h >= MIN_FL, structure=np.ones((3, 3)))
        for c in range(1, n + 1):
            k = lab == c
            sel = k[g.iy.values, g.ix.values]
            celulas.append(dict(t=t, lon=float(g.lon.values[sel].mean()), lat=float(g.lat.values[sel].mean()),
                                flashes=int(sel.sum()), area_celas=int(k.sum())))
    print(len(celulas), 'aglomerados')

    trajs = []
    for c in sorted(celulas, key=lambda x: x['t']):
        melhor, dmin = None, MAX_KM
        for tr in trajs:
            u = tr[-1]
            gap = (c['t'] - u['t']).total_seconds() / 60
            if gap <= 0 or gap > MAX_GAP_MIN:
                continue
            d, dx, dy = km(u['lat'], u['lon'], c['lat'], c['lon'])
            if len(tr) >= 2:
                _, px, py = km(tr[-2]['lat'], tr[-2]['lon'], u['lat'], u['lon'])
                if px * dx + py * dy < 0:
                    d *= 1.5
            if d < dmin and all(x['t'] != c['t'] for x in tr):
                melhor, dmin = tr, d
        (melhor.append(c) if melhor is not None else trajs.append([c]))
    trajs = [tr for tr in trajs if (tr[-1]['t'] - tr[0]['t']).total_seconds() / 3600 >= MIN_DUR_H]
    trajs.sort(key=lambda tr: tr[0]['t'])

    linhas = []
    for i, tr in enumerate(trajs, 1):
        for c in tr:
            c['traj'] = i
        a, b = tr[0], tr[-1]
        dist, dx, dy = km(a['lat'], a['lon'], b['lat'], b['lon'])
        dur = (b['t'] - a['t']).total_seconds()
        linhas.append(dict(id=i, inicio=f"{a['t']:%d/%m %H:%M}", lon0=round(a['lon'], 2), lat0=round(a['lat'], 2),
                           fim=f"{b['t']:%d/%m %H:%M}", lon1=round(b['lon'], 2), lat1=round(b['lat'], 2),
                           duracao_h=round(dur / 3600, 1), dist_km=round(dist), vel_m_s=round(dist * 1000 / dur, 1),
                           rumo_graus=round((math.degrees(math.atan2(dx, dy)) + 360) % 360),
                           flashes=sum(x['flashes'] for x in tr)))
    pd.DataFrame(linhas).to_csv(os.path.join(AQUI, 'glm_trajetorias.csv'), index=False)
    pd.DataFrame(celulas).to_csv(os.path.join(AQUI, 'glm_celulas.csv'), index=False)
    for l in linhas:
        print(l)

    # figura
    cent = municipios()
    fig, ax = plt.subplots(figsize=(14, 8.2), constrained_layout=True)
    dens = np.zeros((ny, nx))
    np.add.at(dens, (f.iy.values, f.ix.values), 1)
    ax.imshow(np.ma.masked_less(dens, 1), extent=GRADE, origin='upper', cmap='Greys', norm=matplotlib.colors.LogNorm(),
              alpha=0.55, interpolation='nearest')
    contornos(ax, 'BR_Estados.shp', color='0.35', lw=0.8)
    cmap = plt.get_cmap('viridis')
    h0, h1 = INI, FIM
    for l, tr in zip(linhas, trajs):
        if l['dist_km'] < 60:
            continue
        xs, ys = [c['lon'] for c in tr], [c['lat'] for c in tr]
        cor = cmap(((tr[0]['t'] - h0) / (h1 - h0)))
        ax.plot(xs, ys, '-', color=cor, lw=2.2)
        ax.plot(xs[-1], ys[-1], '>', color=cor, ms=6)
        ax.annotate(str(l['id']), (xs[0], ys[0]), xytext=(-3, 3), textcoords='offset points', fontsize=8, ha='right')
    for nome, quando, _ in RELATOS:
        if nome in cent:
            lo, la = cent[nome]
            ax.plot(lo, la, '^', color='#c4129f', ms=7, mec='white', mew=0.6)
            ax.annotate(f'{nome} ({quando})', (lo, la), xytext=(4, -10), textcoords='offset points', fontsize=7.5,
                        color='#5a0a4a')
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=matplotlib.colors.Normalize(0, (h1 - h0).total_seconds() / 3600))
    cb = fig.colorbar(sm, ax=ax, shrink=0.8)
    cb.set_label(f'início da trajetória, horas após {h0:%d/%m %H:%M} UTC')
    ax.set_xlim(-56.5, -47.0)
    ax.set_ylim(-30.0, -25.5)
    ax.set_aspect(1 / math.cos(math.radians(-27.5)))
    ax.set_title('Células com raios (GLM, GOES-19) de 28/08 18 UTC a 30/08 06 UTC: trajetórias de 1 h ou mais e 60 km ou mais\n'
                 'cinza: densidade de flashes; ▲ municípios com granizo relatado', fontsize=11)
    fig.savefig(os.path.join(AQUI, 'glm_trajetorias.png'), dpi=130)
    print('->', os.path.join(AQUI, 'glm_trajetorias.png'))


if __name__ == '__main__':
    main()
