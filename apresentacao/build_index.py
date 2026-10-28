# -*- coding: utf-8 -*-
"""Gera apresentacao/index.html: a pagina interativa do evento de granizo de 29/08/2026 em SC.

Le apenas o que as analises do projeto ja produziram e embute os dados no HTML (um unico arquivo):
  satelite/glm_celulas.csv, glm_trajetorias.csv, glm_relatos.csv   rastreio por raios (GLM)
  satelite/resumo_evento.csv                                         GOES-19 e GLM sobre a Ilha
  radar/estado_nucleos.csv, radar/wrf_d02_objetos.csv                radar MI e WRF d02
  clima_espacial/...                                                 aerossol, indices, neutrons, Jz
  viz_granizo_v2/saida/granizo_3d_pico_sudeste.png                   vista 3D (vira JPEG embutido)

Uso: python apresentacao/build_index.py   ->  apresentacao/index.html
"""
import base64
import io
import json
import os

import netCDF4
import numpy as np
import pandas as pd
import shapefile
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(AQUI, '..')
CAIXA = (-58.0, -46.0, -30.5, -25.0)


def caminho(*a):
    return os.path.join(P, *a)


def contornos():
    """Fronteiras (paises e estados) recortadas na caixa, simplificadas a ~0,02 grau."""
    linhas = []
    for arq in ('America_do_Sul.shp', 'BR_Estados.shp'):
        for s in shapefile.Reader(caminho('shp_ibge', arq)).shapes():
            p = np.array(s.points)
            for a, b in zip(s.parts, list(s.parts[1:]) + [len(p)]):
                seg = p[a:b]
                dentro = ((seg[:, 0] > CAIXA[0] - 0.5) & (seg[:, 0] < CAIXA[1] + 0.5)
                          & (seg[:, 1] > CAIXA[2] - 0.5) & (seg[:, 1] < CAIXA[3] + 0.5))
                if not dentro.any():
                    continue
                out, ult = [], None
                for x, y in seg:
                    if ult is None or abs(x - ult[0]) + abs(y - ult[1]) > 0.02:
                        out.append([round(float(x), 3), round(float(y), 3)])
                        ult = (x, y)
                linhas.append(out)
    return linhas


def municipios(nomes):
    r = shapefile.Reader(caminho('shp_ibge', 'SC_Municipios_2022.shp'), encoding='utf-8')
    out = {}
    for rec, shp in zip(r.records(), r.shapes()):
        if rec[1] in nomes:
            p = np.array(shp.points)
            out[rec[1]] = [round(float(p[:, 0].mean()), 3), round(float(p[:, 1].mean()), 3)]
    return out


def dominio_d02():
    with netCDF4.Dataset(caminho('run_wrf', 'wrfout_d02_2026-08-29_12_00_00')) as d:
        la, lo = np.array(d['XLAT'][0]), np.array(d['XLONG'][0])
    borda = np.concatenate([np.c_[lo[0], la[0]], np.c_[lo[:, -1], la[:, -1]],
                            np.c_[lo[-1, ::-1], la[-1, ::-1]], np.c_[lo[::-1, 0], la[::-1, 0]]])
    return [[round(float(x), 3), round(float(y), 3)] for x, y in borda[::5]]


def imagem_jpeg(arq, largura=1600):
    im = Image.open(arq).convert('RGB')
    im = im.resize((largura, int(im.height * largura / im.width)), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, 'JPEG', quality=82, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()


def serie(s, nd=3):
    s = s.dropna()
    return {'t': [t.strftime('%Y-%m-%dT%H:%M') for t in s.index], 'v': [round(float(v), nd) for v in s.values]}


def main():
    d = {}
    # rastreio por raios
    cel = pd.read_csv(caminho('satelite', 'glm_celulas.csv'), parse_dates=['t'])
    d['celulas'] = [[c.t.strftime('%Y-%m-%dT%H:%M'), round(c.lon, 3), round(c.lat, 3), int(c.flashes),
                     (None if pd.isna(c.traj) else int(c.traj))] for c in cel.itertuples()]
    tr = pd.read_csv(caminho('satelite', 'glm_trajetorias.csv'))
    d['trajetorias'] = tr.to_dict(orient='records')
    rel = pd.read_csv(caminho('satelite', 'glm_relatos.csv'))
    d['relatos_glm'] = rel.where(rel.notna(), None).to_dict(orient='records')
    nomes = ['Abelardo Luz', 'Ipuaçu', 'Bom Jesus', 'Entre Rios', 'Ouro Verde', 'Joaçaba', 'Campos Novos',
             'Biguaçu', 'Florianópolis', 'Lages', 'Bom Retiro', 'São José do Cedro', 'Princesa', 'Quilombo',
             'Campo Erê']
    d['municipios'] = municipios(nomes)
    d['contornos'] = contornos()
    d['d02'] = dominio_d02()

    # radar MI e WRF d02
    rn = pd.read_csv(caminho('radar', 'estado_nucleos.csv'), parse_dates=['t'])
    d['radar'] = [[r.t.strftime('%Y-%m-%dT%H:%M'), round(r.lon, 3), round(r.lat, 3)] for r in rn.itertuples()]
    wo = pd.read_csv(caminho('radar', 'wrf_d02_objetos.csv'))
    d['wrf'] = [[r.t.replace('_', 'T'), r.lon, r.lat, r.hailcast_max_mm] for r in wo.itertuples()]

    # GOES-19 sobre a Ilha
    sat = pd.read_csv(caminho('satelite', 'resumo_evento.csv'))
    d['goes'] = {'t': [x.replace('Z', '') for x in sat.utc], 'tb_ilha': sat.min_norte_ilha_C.tolist(),
                 'tb_dominio': sat.min_d03_C.tolist(), 'flashes': sat.flashes_glm_10min.tolist()}

    # semana anterior
    ce = caminho('clima_espacial')
    esp = pd.read_csv(os.path.join(ce, 'resultados', 'series_espaciais_20260815_20260905.csv'),
                      index_col=0, parse_dates=True).loc['2026-08-22':'2026-08-31']
    d['kp'] = serie(esp.Kp.resample('3h').first(), 2)
    d['dst'] = serie(esp.Dst_nT, 0)
    d['ey'] = serie(esp.Ey_mV_m, 2)
    nm = {}
    for st in ('OULU', 'DOMC'):
        x = pd.read_csv(os.path.join(ce, 'dados', 'neutrons', f'{st}_h1_20260810_20260905.csv'),
                        parse_dates=['Timestamp']).set_index('Timestamp')['CorrectedCountRate[cts/min]']
        x.index = x.index.tz_localize(None)
        nm[st] = serie((100 * (x / x.loc['2026-08-22':'2026-08-24'].mean() - 1)).loc['2026-08-22':'2026-08-31'], 2)
    d['neutrons'] = nm
    jz = pd.read_csv(os.path.join(ce, 'dados', 'jz', 'rede_14_estacoes_currents_20260801_20260910.csv'),
                     parse_dates=['datetime']).set_index('datetime')['Jz_nA_m2']
    d['jz'] = serie(jz.loc['2026-08-22':'2026-08-31'].resample('30min').mean(), 1)
    m2 = pd.read_csv(os.path.join(ce, 'resultados', 'merra2_aod_diario_20260810_20260905.csv'),
                     index_col=0, parse_dates=True)
    m2.index = m2.index + pd.Timedelta(hours=12)
    cams = pd.read_csv(os.path.join(ce, 'resultados', 'cams_aod_20260810_20260905.csv'), index_col=0,
                       parse_dates=True)
    d['aod'] = {'m2_total': serie(m2.sc_aod_total), 'm2_fumaca': serie(m2.sc_aod_fumaca),
                'cams_total': serie(cams.sc_aod550), 'cams_fumaca': serie(cams.sc_omaod550 + cams.sc_bcaod550)}
    clim = pd.read_csv(os.path.join(ce, 'resultados', 'merra2_aod_mes08_1980_2026.csv'), index_col=0)
    d['clima_aod'] = {'ano': [int(a) for a in clim.index], 'total': clim.sc_aod_total.round(3).tolist(),
                      'fumaca': clim.sc_aod_fumaca.round(3).tolist()}

    d['img3d'] = imagem_jpeg(caminho('viz_granizo_v2', 'saida', 'granizo_3d_pico_sudeste.png'))

    modelo = open(os.path.join(AQUI, 'index_modelo.html'), encoding='utf-8').read()
    img = d.pop('img3d')
    html = modelo.replace('/*__DADOS__*/{}', json.dumps(d, ensure_ascii=False, separators=(',', ':')))
    html = html.replace('__IMG3D__', img)
    # corpo para o Artifact (o publicador poe o esqueleto) e documento completo para abrir localmente / GitHub Pages
    with open(os.path.join(AQUI, 'index_artifact.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    doc = ('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n</head>\n<body>\n'
           + html + '\n</body>\n</html>\n')
    with open(os.path.join(AQUI, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(doc)
    print('->', os.path.join(AQUI, 'index.html'), f'{len(doc) / 1e6:.2f} MB')


if __name__ == '__main__':
    main()
