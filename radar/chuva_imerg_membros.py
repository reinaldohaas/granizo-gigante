# -*- coding: utf-8 -*-
"""Chuva observada (IMERG Late V07) x chuva do d02 (3 km) das nove rodadas, com o radar e o GOES ao lado, 29/08/2026.

Um painel 3 x 4 por janela de tempo:
  (1) IMERG acumulado na janela (0,1 grau);
  (2) radar Morro da Igreja: maior intensidade de cor do MaxCAPPI na janela (quadros a cada 20 min). Os PNG da
      REDEMET nao tem legenda; a rampa ciano-azul-verde-amarelo-laranja-vermelho vira um indice ordinal 0-1,
      e o vermelho (indice >= ~0,9) e o "nucleo intenso" de plotar_radar_mi.py (~>= 50 dBZ, nao calibrado);
  (3) GOES-19 C13: menor temperatura de brilho na janela (varreduras a cada 30 min), com contorno de -60 C, e a
      densidade de flashes do GLM (contorno de >= 20 flashes por celula de 0,1 grau);
  (4-12) RAINNC do d02 (sem cumulus) de cada rodada, levado a grade do IMERG pela media dos pontos em cada celula.
A area comum e o recorte do d02 (~51,0-46,4 W, 29,5-25,5 S); tracejado: d03.
Entradas: satelite/imerg/*.HDF5, radar/mi/maxcappi/, satelite/glm_pontos_sc.csv, recorte_trajetorias_d02/d03.nc,
GOES do AWS (cache em radar/figuras/cache_goes_c13_d02, um .npy por varredura).
Saidas: radar/figuras/chuva_imerg_membros/chuva_<janela>.png e estatisticas.csv (por janela e rodada: media, p99,
correlacao espacial com o IMERG, area >= 10 mm, centroide da chuva >= 10 mm e distancia ao centroide do IMERG).
"""
import csv
import datetime as dt
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np
import pandas as pd
import s3fs
from matplotlib.colors import ListedColormap
from PIL import Image

from chuva_obs_x_d01 import imerg, na_grade
from plotar_radar_mi import AQUI, PASTA, SAIDA, contornos

sys.path.insert(0, os.path.join(AQUI, '..'))
from gerar_goes_ir import campo, listar_abi  # noqa: E402  (fica na raiz do projeto)

OUT = os.path.join(SAIDA, 'chuva_imerg_membros')
CACHE = os.path.join(SAIDA, 'cache_goes_c13_d02')
RODADAS = [('22/10', os.path.join('wrf', 'recorte_trajetorias_d02.nc'))] + [
    (m, os.path.join('wrf', 'ensemble', m, 'recorte_trajetorias_d02.nc'))
    for m in ('E0_controle', 'E1_mynn', 'E2_inicio06', 'E3_gf_d01', 'F1_gf_mynn', 'F2_gf_inicio06',
              'F3_gf_skebs1', 'F4_gf_skebs2')]
GF = {'E3_gf_d01', 'F1_gf_mynn', 'F2_gf_inicio06', 'F3_gf_skebs1', 'F4_gf_skebs2'}
JANELAS = ((dt.datetime(2026, 8, 29, 18), dt.datetime(2026, 8, 30, 0)),
           (dt.datetime(2026, 8, 29, 20), dt.datetime(2026, 8, 29, 23)),
           (dt.datetime(2026, 8, 30, 0), dt.datetime(2026, 8, 30, 2)))
NIVEIS = [1, 5, 10, 20, 40, 60, 80]
ILHA = (-27.6, -48.5)
GLON = np.arange(-51.0, -46.4 + 1e-9, 0.02)
GLAT = np.arange(-25.46, -29.52 - 1e-9, -0.02)
# rampa de cores do MaxCAPPI, do mais fraco ao mais forte (cores lidas dos quadros de 29-30/08)
RAMPA = np.array([(114, 255, 255), (0, 236, 240), (1, 107, 247), (0, 10, 246), (0, 138, 114), (0, 253, 1),
                  (0, 148, 0), (13, 150, 0), (217, 239, 0), (254, 252, 0), (255, 135, 0), (254, 5, 0),
                  (200, 0, 1)], float)


def _arco():
    comp = np.linalg.norm(RAMPA[1:] - RAMPA[:-1], axis=1)
    return np.r_[0, np.cumsum(comp)] / comp.sum()


def cmap_radar():
    """A propria rampa da REDEMET como mapa de cores do indice 0-1."""
    x = np.linspace(0, 1, 256)
    return ListedColormap(np.stack([np.interp(x, _arco(), RAMPA[:, k]) for k in range(3)], 1) / 255)


def indice_cor(rgb):
    """Posicao (0-1, por comprimento de arco) de cada cor na rampa do MaxCAPPI; nan fora dela."""
    seg = RAMPA[1:] - RAMPA[:-1]
    comp = np.linalg.norm(seg, axis=1)
    acum = np.r_[0, np.cumsum(comp)]
    melhor_d = np.full(rgb.shape[0], np.inf)
    melhor_s = np.zeros(rgb.shape[0])
    for k in range(len(seg)):
        t = np.clip(((rgb - RAMPA[k]) @ seg[k]) / comp[k] ** 2, 0, 1)
        d = np.linalg.norm(rgb - (RAMPA[k] + t[:, None] * seg[k]), axis=1)
        m = d < melhor_d
        melhor_d[m], melhor_s[m] = d[m], acum[k] + t[m] * comp[k]
    out = melhor_s / acum[-1]
    out[melhor_d > 30] = np.nan
    return out


def radar_max(a, b):
    """(maior indice de cor na janela [a, b), extent, quantos quadros)."""
    q = pd.read_csv(os.path.join(PASTA, 'quadros.csv'), parse_dates=['data_utc'])
    q = q[(q.data_utc >= a) & (q.data_utc < b)]
    mx, ext = None, None
    for _, r in q.iterrows():
        im = np.array(Image.open(os.path.join(PASTA, r.arquivo)).convert('RGBA'))
        idx = np.full(im.shape[:2], np.nan)
        ok = im[..., 3] > 0
        idx[ok] = indice_cor(im[ok][:, :3].astype(float))
        mx = idx if mx is None else np.fmax(mx, idx)
        ext = [r.lon_min, r.lon_max, r.lat_min, r.lat_max]
    return mx, ext, len(q)


def goes_min(a, b):
    """Menor C13 (C) entre as varreduras de 30 em 30 min em [a, b) na grade GLON x GLAT, com cache."""
    os.makedirs(CACHE, exist_ok=True)
    fs, menor, n = None, None, 0
    t = a
    while t < b:
        p = os.path.join(CACHE, f'{t:%Y%m%d_%H%M}.npy')
        if not os.path.exists(p):
            try:
                fs = fs or s3fs.S3FileSystem(anon=True, config_kwargs={'connect_timeout': 20})
                c13 = listar_abi(fs, t - dt.timedelta(minutes=5), t + dt.timedelta(minutes=5), 'C13')
                k = min(c13, key=lambda k: abs(k - t))
                np.save(p, campo(fs, c13[k], GLON, GLAT))
            except Exception as e:  # AWS fora do ar: segue sem a varredura
                print(f'GOES indisponivel para {t:%d %H:%M}: {type(e).__name__}')
        if os.path.exists(p):
            c = np.load(p)
            menor = c if menor is None else np.minimum(menor, c)
            n += 1
        t += dt.timedelta(minutes=30)
    return menor, n


def centroide(campo, LO, LA, limiar=10.0):
    m = np.isfinite(campo) & (campo >= limiar)
    if not m.any():
        return np.nan, np.nan
    w = campo[m]
    return float((LO[m] * w).sum() / w.sum()), float((LA[m] * w).sum() / w.sum())


def km(lo0, la0, lo1, la1):
    return 111.2 * np.hypot((lo1 - lo0) * np.cos(np.radians(27.5)), la1 - la0)


def main():
    os.makedirs(OUT, exist_ok=True)
    obs, lons, lats = imerg()
    LO, LA = np.meshgrid(lons, lats)
    glm = pd.read_csv(os.path.join(AQUI, '..', 'satelite', 'glm_pontos_sc.csv'), parse_dates=['t_utc'])
    mod = {}
    for nome, p in RODADAS:
        f = nc.Dataset(os.path.join(AQUI, p))
        tt = [dt.datetime.strptime(b''.join(t).decode(), '%Y-%m-%d_%H:%M:%S') for t in f['Times'][:]]
        mod[nome] = (tt, f['RAINNC'][:], f['XLAT'][0], f['XLONG'][0])
    la2, lo2 = mod['E0_controle'][2], mod['E0_controle'][3]
    area = np.isfinite(na_grade(np.ones_like(la2), la2, lo2, lons, lats))
    d3 = nc.Dataset(os.path.join(AQUI, 'wrf', 'ensemble', 'E0_controle', 'recorte_trajetorias_d03.nc'))
    l3a, l3o = d3['XLAT'][0], d3['XLONG'][0]
    borda3 = (np.r_[l3o[0, :], l3o[:, -1], l3o[-1, ::-1], l3o[::-1, 0]],
              np.r_[l3a[0, :], l3a[:, -1], l3a[-1, ::-1], l3a[::-1, 0]])
    caixa = (lo2.min(), lo2.max(), la2.min(), la2.max())
    cmap_r = cmap_radar()
    arco = _arco()

    linhas = []
    for a, b in JANELAS:
        rot = f'{a:%d/%m %H:%M}–{b:%H:%M} UTC'
        o = sum(obs[t] for t in obs if a <= t < b)
        nmeia = sum(1 for t in obs if a <= t < b)
        o = np.where(area, o, np.nan)
        fig, axs = plt.subplots(3, 4, figsize=(20, 14.5))
        fig.subplots_adjust(left=0.03, right=0.97, top=0.92, bottom=0.08, wspace=0.28, hspace=0.22)
        axs = axs.ravel()
        cs = axs[0].contourf(LO, LA, o, NIVEIS, cmap='YlGnBu', extend='max')
        axs[0].set_title(f'IMERG Late ({nmeia} meias horas)\nmédia {np.nanmean(o):.1f} mm, máx {np.nanmax(o):.0f} mm',
                         fontsize=10)
        cxo, cyo = centroide(o, LO, LA)

        rx, ext, nq = radar_max(a, b)
        im = axs[1].imshow(rx, extent=ext, origin='upper', cmap=cmap_r, vmin=0, vmax=1, interpolation='nearest')
        axs[1].set_title(f'Radar Morro da Igreja: cor máxima\ndo MaxCAPPI ({nq} quadros, não calibrado)', fontsize=10)
        cb = fig.colorbar(im, ax=axs[1], shrink=0.8, ticks=arco[[3, 5, 9, 11]])
        cb.ax.set_yticklabels(['azul', 'verde', 'amarelo', 'vermelho\n(~≥ 50 dBZ)'], fontsize=8)

        gm, ng = goes_min(a, b)
        if gm is not None:
            ig = axs[2].imshow(gm, extent=[GLON[0], GLON[-1], GLAT[-1], GLAT[0]], origin='upper', cmap='gray_r',
                               vmin=-80, vmax=20)
            axs[2].contour(GLON, GLAT, gm, [-60], colors='c', linewidths=0.8)
            fig.colorbar(ig, ax=axs[2], shrink=0.8, label='°C')
        g = glm[(glm.t_utc >= a) & (glm.t_utc < b)]
        h, ye, xe = np.histogram2d(g.lat, g.lon, [np.r_[lats - 0.05, lats[-1] + 0.05], np.r_[lons - 0.05, lons[-1] + 0.05]])
        axs[2].contour(lons, lats, h, [20, 200], colors=['orange', 'r'], linewidths=[0.8, 1.2])
        axs[2].set_title(f'GOES-19 C13 mínimo ({ng} varreduras, ciano −60 °C)\nGLM ≥ 20 (laranja) e ≥ 200 (vermelho) '
                         f'flashes/0,1°', fontsize=10)

        for k, (nome, (tt, rn, mla, mlo)) in enumerate(mod.items()):
            ax = axs[3 + k]
            if a not in tt or b not in tt:
                ax.set_visible(False)
                continue
            c = na_grade(rn[tt.index(b)] - rn[tt.index(a)], mla, mlo, lons, lats)
            c = np.where(area, c, np.nan)
            ax.contourf(LO, LA, c, NIVEIS, cmap='YlGnBu', extend='max')
            ok = np.isfinite(o) & np.isfinite(c)
            r = np.corrcoef(o[ok], c[ok])[0, 1]
            cx, cy = centroide(c, LO, LA)
            dist = km(cxo, cyo, cx, cy)
            ax.plot(cx, cy, 'm+', ms=12, mew=2)
            ax.set_title(f'{nome} ({"GF" if nome in GF else "KF"} no d01)\nmédia {np.nanmean(c):.1f} mm, máx {np.nanmax(c):.0f} mm, '
                         f'r = {r:+.2f}, Δcentroide {dist:.0f} km', fontsize=10)
            linhas.append({'janela': f'{a:%d%H}-{b:%d%H}', 'rodada': nome, 'cu_d01': 'GF' if nome in GF else 'KF',
                           'media_mm': round(float(np.nanmean(c)), 2), 'p99_mm': round(float(np.nanpercentile(c[ok], 99)), 1),
                           'max_mm': round(float(np.nanmax(c)), 1), 'r_imerg': round(float(r), 2),
                           'area_10mm_celulas': int((c[ok] >= 10).sum()),
                           'centroide_lon': round(cx, 2), 'centroide_lat': round(cy, 2),
                           'dist_centroide_imerg_km': round(float(dist), 0)})
        linhas.append({'janela': f'{a:%d%H}-{b:%d%H}', 'rodada': 'IMERG', 'cu_d01': '',
                       'media_mm': round(float(np.nanmean(o)), 2), 'p99_mm': round(float(np.nanpercentile(o[area], 99)), 1),
                       'max_mm': round(float(np.nanmax(o)), 1), 'r_imerg': 1.0,
                       'area_10mm_celulas': int((o[area] >= 10).sum()),
                       'centroide_lon': round(cxo, 2), 'centroide_lat': round(cyo, 2), 'dist_centroide_imerg_km': 0})
        for ax in axs:
            if not ax.get_visible():
                continue
            contornos(ax, 'BR_Estados.shp', color='0.3', lw=0.7)
            contornos(ax, 'America_do_Sul.shp', color='0.5', lw=0.5)
            ax.plot(*borda3, 'k--', lw=0.8)
            ax.plot(ILHA[1], ILHA[0], 'r*', ms=10, mec='k')
            ax.plot(cxo, cyo, 'mx', ms=10, mew=2)
            ax.set_xlim(caixa[:2])
            ax.set_ylim(caixa[2:])
            ax.set_aspect(1 / np.cos(np.radians(27.5)))
            ax.tick_params(labelsize=8)
        cax = fig.add_axes([0.3, 0.035, 0.4, 0.012])
        fig.colorbar(cs, cax=cax, orientation='horizontal', label='chuva acumulada na janela (mm), IMERG e rodadas')
        fig.suptitle(f'Chuva {rot}: IMERG x d02 (3 km) das nove rodadas na grade de 0,1°, com radar e GOES\n'
                     f'× magenta: centroide da chuva ≥ 10 mm do IMERG; + magenta: o da rodada; ★ Ilha; tracejado: d03',
                     fontsize=12)
        fig.savefig(os.path.join(OUT, f'chuva_{a:%d%H}_{b:%d%H}.png'), dpi=85)
        plt.close(fig)
        print(f'{rot}: IMERG média {np.nanmean(o):.1f} mm, max {np.nanmax(o):.0f}; radar {nq} quadros; GOES {ng}')

    with open(os.path.join(OUT, 'estatisticas.csv'), 'w', newline='', encoding='utf-8') as g:
        w = csv.DictWriter(g, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    print(pd.DataFrame(linhas).to_string(index=False))


if __name__ == '__main__':
    main()
