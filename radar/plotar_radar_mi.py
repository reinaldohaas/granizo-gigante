# -*- coding: utf-8 -*-
"""Quadros MaxCAPPI do radar Morro da Igreja (DECEA/REDEMET) em 29-30/08/2026 e trajetoria dos nucleos intensos.

Os PNG da REDEMET sao imagens em lat/lon regular (limites em quadros.csv), sem legenda nem dBZ. A escala de cores
vai de azul (fraco) a verde, amarelo, laranja, vermelho e magenta; aqui "nucleo intenso" = pixel vermelho/magenta
(R >= 200 e G <= 140), aproximadamente >= 50 dBZ na escala usual da REDEMET (nao calibrado).

Saidas (radar/figuras/): mi_quadros_2056_0016.png (painel) e mi_trajetoria_nucleos.png (swath colorido pelo horario).
"""
import csv
import os
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import shapefile
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA = os.path.join(AQUI, 'mi', 'maxcappi')
SAIDA = os.path.join(AQUI, 'figuras')
SHP = os.path.join(AQUI, '..', 'shp_ibge')

# relatos de superficie (resumo I-SSTS): local, lat, lon, horario UTC
RELATOS = [('Biguaçu', -27.494, -48.655, '~22:00-22:30'),
           ('Jurerê', -27.440, -48.500, '~22:00-22:30'),
           ('Canasvieiras', -27.428, -48.462, '~22:00-22:30'),
           ('Cach. Bom Jesus', -27.430, -48.425, '22:50'),
           ('Ingleses', -27.435, -48.395, '22:40-23:00')]


def quadros():
    with open(os.path.join(PASTA, 'quadros.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            t = datetime.strptime(r['data_utc'], '%Y-%m-%d %H:%M:%S')
            ext = [float(r['lon_min']), float(r['lon_max']), float(r['lat_min']), float(r['lat_max'])]
            yield t, os.path.join(PASTA, r['arquivo']), ext


def contornos(ax, arquivo, **kw):
    for s in shapefile.Reader(os.path.join(SHP, arquivo)).shapes():
        p = np.array(s.points)
        for a, b in zip(s.parts, list(s.parts[1:]) + [len(p)]):
            ax.plot(p[a:b, 0], p[a:b, 1], **kw)


def base(ax, janela):
    contornos(ax, 'SC_Municipios_2022.shp', color='0.8', lw=0.3)
    contornos(ax, 'BR_Estados.shp', color='0.3', lw=0.8)
    for nome, la, lo, _ in RELATOS:
        ax.plot(lo, la, 'k^', ms=4)
    ax.plot(-49.471816, -28.128373, 'ks', ms=4)
    ax.set_xlim(janela[:2]); ax.set_ylim(janela[2:]); ax.set_aspect(1 / np.cos(np.radians(-27.5)))


def nucleo(rgba):
    r, g, a = rgba[..., 0].astype(int), rgba[..., 1].astype(int), rgba[..., 3]
    return (a > 0) & (r >= 200) & (g <= 140)


def main():
    os.makedirs(SAIDA, exist_ok=True)
    todos = list(quadros())

    # painel 20:56 .. 00:16, zoom na Grande Florianopolis / Vale do Tijucas
    janela = (-50.2, -48.0, -28.3, -26.6)
    sel = [q for q in todos if datetime(2026, 8, 29, 20, 50) <= q[0] <= datetime(2026, 8, 30, 0, 20)][:11]
    fig, axs = plt.subplots(3, 4, figsize=(16, 11), constrained_layout=True)
    for ax, (t, arq, ext) in zip(axs.flat, sel):
        ax.imshow(np.array(Image.open(arq).convert('RGBA')), extent=ext, origin='upper', interpolation='nearest')
        base(ax, janela)
        ax.set_title(t.strftime('%d/%m %H:%M UTC'), fontsize=10)
    for ax in axs.flat[len(sel):]:
        ax.axis('off')
    axs.flat[-1].text(0, 0.5, 'MaxCAPPI Morro da Igreja (DECEA/REDEMET)\n▲ relatos de granizo\n■ radar (Urubici)\n'
                      'cores da REDEMET, sem calibração em dBZ', fontsize=10, va='center')
    fig.savefig(os.path.join(SAIDA, 'mi_quadros_2056_0016.png'), dpi=130)

    # trajetoria dos nucleos intensos 18:00 .. 04:00, colorida pelo horario, em toda SC
    janela = (-53.8, -48.0, -29.6, -25.9)
    sel = [q for q in todos if datetime(2026, 8, 29, 18) <= q[0] <= datetime(2026, 8, 30, 4)]
    t0 = sel[0][0]
    horas = np.full((400, 400), np.nan)
    for t, arq, ext in sel:
        m = nucleo(np.array(Image.open(arq).convert('RGBA')))
        horas[m & np.isnan(horas)] = (t - t0).total_seconds() / 3600
    fig, ax = plt.subplots(figsize=(13, 8.5), constrained_layout=True)
    im = ax.imshow(np.ma.masked_invalid(horas), extent=ext, origin='upper', cmap='turbo', interpolation='nearest',
                   vmin=0, vmax=(sel[-1][0] - t0).total_seconds() / 3600)
    base(ax, janela)
    for nome, la, lo, h in RELATOS[::2]:
        ax.annotate(f'{nome} {h}', (lo, la), xytext=(4, 6), textcoords='offset points', fontsize=7)
    cb = fig.colorbar(im, ax=ax, shrink=0.8)
    cb.set_label(f'horas após {t0:%d/%m %H:%M} UTC (1ª vez com núcleo vermelho/magenta)')
    ax.set_title('Núcleos intensos (vermelho/magenta, ~≥50 dBZ) no MaxCAPPI do Morro da Igreja, 29/08 18 UTC – 30/08 04 UTC')
    fig.savefig(os.path.join(SAIDA, 'mi_trajetoria_nucleos.png'), dpi=130)


if __name__ == '__main__':
    main()
