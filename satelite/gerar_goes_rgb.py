"""
Produtos noturnos complementares do GOES-19 para o dominio d03 (Floripa).

Reaproveita a maquinaria de gerar_goes_ir.py (recorte, moldura, marcadores) e
acrescenta tres campos que o C13 sozinho nao mostra:

  microfisica  RGB de microfisica noturna, combinacao de canais da receita
               operacional mas com as faixas de G e B ajustadas a esta cena
               (ver MIC_G / MIC_B) — as cores NAO seguem a convencao do
               produto padrao:
                 R = C15 - C13   (12.3 - 10.3 um)   espessura optica
                 G = C13 - C07   (10.3 -  3.9 um)   tamanho de particula
                 B = C13         (10.3 um)          temperatura do topo
               Nuvem alta e espessa, cirrus fino, nevoeiro e ceu limpo saem em
               cores distintas — separacao que nenhum canal isolado da.

  part         Diferenca C13 - C07 (10.3 - 3.9 um). A noite, valores altos
               indicam particulas de gelo pequenas no topo, assinatura de
               corrente ascendente vigorosa: a nuvem cresce rapido demais para
               os cristais se agregarem. E o indicio mais direto de convecao
               intensa disponivel sem radar.

  vapor        Canal C08 (6.2 um), vapor d'agua de niveis altos. Mostra o
               ambiente da tempestade — entradas de ar seco e a circulacao em
               que a celula esta imersa.

Uso:
  python gerar_goes_rgb.py                  # janela padrao (episodio 1)
  python gerar_goes_rgb.py 2100 2330        # recorte de horario (UTC, HHMM)
"""
import os
import sys
import datetime as dt

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

import gerar_goes_ir as base

SAIDA = base.SAIDA

# Episodio 1, com margem antes e depois
INICIO = dt.datetime(2026, 8, 29, 21, 0)
FIM = dt.datetime(2026, 8, 29, 23, 30)

# Faixas da microfisica noturna (R e G em K, B em °C).
#
# A receita operacional usa R -4..2 K, G 0..10 K, B 243..293 K (= -30..20 °C).
# Aqui G e B foram ajustados a esta cena, e por isso as cores NAO seguem a
# convencao do produto padrao:
#
#   G: nesta cena C13-C07 vai de -15 a +4.5 K (mediana -2.5), porque ha muito
#      cirrus semitransparente — em 3.9 um ele deixa passar mais radiacao
#      quente da superficie que em 10.3 um. Com a faixa 0..10 praticamente
#      todo o dominio satura em zero e o canal verde fica morto.
#   B: com topos a -63 C, a faixa que comeca em -30 C zera todo o anvil e a
#      estrutura do topo some.
MIC_R = (-4.0, 2.0)
MIC_G = (-8.0, 4.0)
MIC_B = (-65.0, 20.0)
MIC_NOTA = 'faixas G e B ajustadas a esta cena (ver docstring)'

# Diferenca C13 - C07 nesta cena: p50 -2.5, p99 +2.9, maximo +4.5 K
PART_MIN, PART_MAX = -8.0, 5.0


def normaliza(a, lo, hi):
    return np.clip((a - lo) / (hi - lo), 0, 1)


def desenhar_microfisica(c07, c13, c15, lons, lats, quando, municipios, destino):
    rgb = np.dstack([
        normaliza(c15 - c13, *MIC_R),
        normaliza(c13 - c07, *MIC_G),
        normaliza(c13, *MIC_B),
    ])

    fig, ax = plt.subplots(figsize=(9, 8.4), dpi=150)
    ax.imshow(rgb, origin='upper', extent=[lons[0], lons[-1], lats[-1], lats[0]],
              interpolation='bilinear', zorder=1)

    marca, cor = base.rotulo_episodio(quando)
    base.marcar_relatos(ax, quando)
    base.moldura(ax, lons, lats, municipios, cor='#ffffff')
    local = quando - dt.timedelta(hours=3)
    ax.set_title(f"GOES-19 — microfísica noturna (RGB)  —  {quando:%d/%m/%Y %H:%M} UTC "
                 f"({local:%H:%M} local){marca}\n"
                 f"R = C15−C13   G = C13−C07   B = C13   |   {MIC_NOTA}",
                 fontsize=10, color=cor)
    fig.tight_layout()
    fig.savefig(destino, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def desenhar_particula(c07, c13, lons, lats, quando, municipios, destino):
    dif = c13 - c07

    fig, ax = plt.subplots(figsize=(9, 8.4), dpi=150)
    im = ax.imshow(dif, origin='upper', cmap='magma',
                   norm=Normalize(PART_MIN, PART_MAX),
                   extent=[lons[0], lons[-1], lats[-1], lats[0]],
                   interpolation='bilinear', zorder=1)

    cs = ax.contour(lons, lats, c13, levels=[-60, -50], colors='#00ffff',
                    linewidths=[1.3, 0.7], linestyles=['-', '--'], zorder=4)
    ax.clabel(cs, fmt='%d °C', fontsize=7)

    marca, cor = base.rotulo_episodio(quando)
    base.marcar_relatos(ax, quando)
    base.moldura(ax, lons, lats, municipios, cor='#ffffff')
    local = quando - dt.timedelta(hours=3)
    ax.set_title(f"GOES-19 C13−C07 (10.3−3.9 µm) — tamanho de partícula no topo  —  "
                 f"{quando:%d/%m/%Y %H:%M} UTC ({local:%H:%M} local){marca}\n"
                 f"claro = gelo pequeno, ascendente vigorosa"
                 f"   |   contorno: C13 em −60/−50 °C",
                 fontsize=10, color=cor)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label('C13 − C07 (K)')
    fig.tight_layout()
    fig.savefig(destino, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def desenhar_vapor(c08, lons, lats, quando, municipios, destino):
    fig, ax = plt.subplots(figsize=(9, 8.4), dpi=150)
    im = ax.imshow(c08, origin='upper', cmap='BrBG',
                   norm=Normalize(-60, -20),
                   extent=[lons[0], lons[-1], lats[-1], lats[0]],
                   interpolation='bilinear', zorder=1)

    marca, cor = base.rotulo_episodio(quando)
    base.marcar_relatos(ax, quando)
    base.moldura(ax, lons, lats, municipios)
    local = quando - dt.timedelta(hours=3)
    ax.set_title(f"GOES-19 C08 (6.2 µm) — vapor d'água em níveis altos  —  "
                 f"{quando:%d/%m/%Y %H:%M} UTC ({local:%H:%M} local){marca}\n"
                 f"escuro = ar seco   claro = ar úmido / topo alto"
                 f"   |   ▼ = relato de granizo",
                 fontsize=10, color=cor)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label('Temperatura de brilho (°C)')
    fig.tight_layout()
    fig.savefig(destino, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def main():
    inicio, fim = INICIO, FIM
    if len(sys.argv) > 2:
        d = INICIO.date()
        inicio = dt.datetime.combine(d, dt.time(int(sys.argv[1][:2]), int(sys.argv[1][2:])))
        fim = dt.datetime.combine(d, dt.time(int(sys.argv[2][:2]), int(sys.argv[2][2:])))

    import s3fs
    import geopandas as gpd

    lons = np.arange(base.LON_MIN, base.LON_MAX + base.PASSO / 2, base.PASSO)
    lats = np.arange(base.LAT_MAX, base.LAT_MIN - base.PASSO / 2, -base.PASSO)
    municipios = (gpd.read_file(base.SHP_MUN).to_crs(4326)
                  .cx[base.LON_MIN:base.LON_MAX, base.LAT_MIN:base.LAT_MAX])

    fs = s3fs.S3FileSystem(anon=True)
    canais = {c: base.listar_abi(fs, inicio, fim, c)
              for c in ('C07', 'C08', 'C13', 'C15')}
    momentos = sorted(set.intersection(*(set(v) for v in canais.values())))

    print(f"{len(momentos)} varreduras entre {inicio:%d/%m %H:%M} e {fim:%H:%M} UTC")

    for i, quando in enumerate(momentos, 1):
        alvos = {
            'microfisica': os.path.join(SAIDA, f"goes19_microfisica_{quando:%Y%m%d_%H%M}z.png"),
            'part': os.path.join(SAIDA, f"goes19_particula_{quando:%Y%m%d_%H%M}z.png"),
            'vapor': os.path.join(SAIDA, f"goes19_vapor_{quando:%Y%m%d_%H%M}z.png"),
        }
        if all(os.path.exists(p) for p in alvos.values()):
            print(f"  [{i}/{len(momentos)}] {quando:%H:%M}z ja existe")
            continue

        c13 = base.campo(fs, canais['C13'][quando], lons, lats)
        c07 = base.campo(fs, canais['C07'][quando], lons, lats)
        c15 = base.campo(fs, canais['C15'][quando], lons, lats)
        c08 = base.campo(fs, canais['C08'][quando], lons, lats)

        if not os.path.exists(alvos['microfisica']):
            desenhar_microfisica(c07, c13, c15, lons, lats, quando, municipios,
                                 alvos['microfisica'])
        if not os.path.exists(alvos['part']):
            desenhar_particula(c07, c13, lons, lats, quando, municipios, alvos['part'])
        if not os.path.exists(alvos['vapor']):
            desenhar_vapor(c08, lons, lats, quando, municipios, alvos['vapor'])

        dif = c13 - c07
        frio = c13 <= -50
        print(f"  [{i}/{len(momentos)}] {quando:%H:%M}z  C13 min {c13.min():6.1f} C  "
              f"C13−C07 max {dif.max():5.1f} K  "
              f"(sob C13≤−50: {np.nanmax(dif[frio]) if frio.any() else float('nan'):5.1f} K)")

    return 0


if __name__ == '__main__':
    sys.exit(main())
