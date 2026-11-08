# -*- coding: utf-8 -*-
"""Por que so o Grell-Freitas no d01 (9 km) poe a celula da Ilha no lugar? E0 (Kain-Fritsch) x E3 (Grell-Freitas).

Recortes do d01 de 12 a 22 UTC de 29/08 (radar/wrf/d01/<membro>/recorte_d01_1222.nc). Hipotese testada: o KF
dispara conveccao parametrizada cedo, consome a instabilidade e altera o jato e a convergencia em baixos niveis
perto de onde a celula da Ilha nasceu (50,1 W / 27,5 S, 20:10 UTC pelos raios; 20:36 pelo radar).

Calcula por hora, para cada membro:
  - chuva convectiva (RAINC) e explicita (RAINNC) acumuladas na faixa do corredor (52-49,5 W, 28-27 S);
  - no ponto de nascimento: theta-e em 850 hPa, theta-e a 2 m, vento em 850 hPa e pressao a superficie.
Saidas: radar/d01_kf_vs_gf.csv e radar/figuras/d01_kf_vs_gf.png (series + mapa da diferenca de theta-e 850 as 19 UTC)
"""
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import netCDF4
import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
MEMBROS = {'E0 · Kain-Fritsch': 'E0_controle', 'E3 · Grell-Freitas': 'E3_gf_d01'}
PONTO = (-50.14, -27.53)
FAIXA = (-52.0, -49.5, -28.0, -27.0)


def theta_e(t_k, q, p_pa):
    """Theta-e aproximado (Bolton 1980), q em kg/kg."""
    e = q * p_pa / 100 / (0.622 + q)
    tl = 2840 / (3.5 * np.log(t_k) - np.log(np.maximum(e, 1e-3)) - 4.805) + 55
    return t_k * (1000 / (p_pa / 100)) ** (0.2854 * (1 - 0.28 * q)) * np.exp((3.376 / tl - 0.00254) * q * 1e3 * (1 + 0.81 * q))


def em_850(campo, p):
    """Interpola linearmente em log p um campo 3D (nz, ny, nx) para 850 hPa."""
    lp = np.log(p)
    alvo = np.log(85000.0)
    k = np.clip((lp > alvo).sum(axis=0), 1, p.shape[0] - 1)
    k0 = k - 1
    a0 = np.take_along_axis(lp, k0[None], 0)[0]
    a1 = np.take_along_axis(lp, k[None], 0)[0]
    f0 = np.take_along_axis(campo, k0[None], 0)[0]
    f1 = np.take_along_axis(campo, k[None], 0)[0]
    w = np.clip((alvo - a0) / (a1 - a0), 0, 1)
    return f0 + (f1 - f0) * w


def ler(m):
    d = netCDF4.Dataset(os.path.join(AQUI, 'wrf', 'd01', m, 'recorte_d01_1222.nc'))
    tempos = pd.to_datetime([b''.join(t).decode().replace('_', ' ') for t in d['Times'][:]])
    lat, lon = np.array(d['XLAT'][0]), np.array(d['XLONG'][0])
    j, i = np.unravel_index(np.argmin((lat - PONTO[1]) ** 2 + (lon - PONTO[0]) ** 2), lat.shape)
    faixa = (lon >= FAIXA[0]) & (lon <= FAIXA[1]) & (lat >= FAIXA[2]) & (lat <= FAIXA[3])
    linhas, the850 = [], {}
    for n, t in enumerate(tempos):
        p = np.array(d['P'][n]) + np.array(d['PB'][n])
        tk = (np.array(d['T'][n]) + 300) * (p / 1e5) ** 0.2857
        q = np.array(d['QVAPOR'][n])
        te = theta_e(tk, q, p)
        te850 = em_850(te, p)
        u = 0.5 * (np.array(d['U'][n])[:, :, :-1] + np.array(d['U'][n])[:, :, 1:])
        v = 0.5 * (np.array(d['V'][n])[:, :-1, :] + np.array(d['V'][n])[:, 1:, :])
        u850, v850 = em_850(u, p), em_850(v, p)
        t2, q2, ps = np.array(d['T2'][n]), np.array(d['Q2'][n]), np.array(d['PSFC'][n])
        te2 = theta_e(t2, q2, ps)
        the850[t] = te850
        linhas.append(dict(t=t, rainc_faixa_mm=float(np.array(d['RAINC'][n])[faixa].mean()),
                           rainnc_faixa_mm=float(np.array(d['RAINNC'][n])[faixa].mean()),
                           thetae850_K=float(te850[j, i]), thetae2m_K=float(te2[j, i]),
                           vento850_m_s=float(np.hypot(u850[j, i], v850[j, i])),
                           dir850_graus=float((np.degrees(np.arctan2(u850[j, i], v850[j, i])) + 180) % 360),
                           psfc_hPa=float(ps[j, i] / 100)))
    return pd.DataFrame(linhas).set_index('t'), lat, lon, the850


def main():
    res, campos = {}, {}
    for nome, m in MEMBROS.items():
        res[nome], lat, lon, campos[nome] = ler(m)
    tab = pd.concat(res, axis=1).round(2)
    tab.to_csv(os.path.join(AQUI, 'd01_kf_vs_gf.csv'))
    pd.set_option('display.width', 250)
    print(tab.to_string())

    fig, axs = plt.subplots(1, 3, figsize=(18, 5.2), constrained_layout=True)
    cores = {'E0 · Kain-Fritsch': '#eb6834', 'E3 · Grell-Freitas': '#2a78d6'}
    for nome, df in res.items():
        h = df.index.hour
        axs[0].plot(h, df.rainc_faixa_mm, '-o', color=cores[nome], label=f'{nome}: convectiva (RAINC)')
        axs[0].plot(h, df.rainnc_faixa_mm, '--', color=cores[nome], label=f'{nome}: explícita (RAINNC)')
        axs[1].plot(h, df.thetae850_K, '-o', color=cores[nome], label=nome)
    axs[0].set_title('Chuva acumulada desde 12 UTC, média na faixa 52–49,5°W / 28–27°S')
    axs[0].set_xlabel('hora UTC, 29/08')
    axs[0].set_ylabel('mm')
    axs[0].legend(fontsize=8)
    axs[1].set_title('θe em 850 hPa no ponto de nascimento da célula da Ilha')
    axs[1].set_xlabel('hora UTC, 29/08')
    axs[1].set_ylabel('K')
    axs[1].legend(fontsize=9)
    t19 = [t for t in campos['E0 · Kain-Fritsch'] if t.hour == 19][0]
    dif = campos['E3 · Grell-Freitas'][t19] - campos['E0 · Kain-Fritsch'][t19]
    im = axs[2].pcolormesh(lon, lat, dif, cmap='RdBu_r', vmin=-8, vmax=8, shading='auto')
    fig.colorbar(im, ax=axs[2], shrink=0.85, label='θe 850 hPa: E3 − E0 (K)')
    axs[2].plot(*PONTO, 'k*', ms=14)
    axs[2].set_xlim(-58, -44)
    axs[2].set_ylim(-32, -23)
    axs[2].set_title('Diferença de θe em 850 hPa às 19 UTC (★ nascimento da célula)')
    sys_path = os.path.join(AQUI, '..', 'satelite')
    import sys
    sys.path.insert(0, sys_path)
    from glm_trajetorias import contornos
    contornos(axs[2], 'BR_Estados.shp', color='0.3', lw=0.6)
    fig.savefig(os.path.join(AQUI, 'figuras', 'd01_kf_vs_gf.png'), dpi=120)


if __name__ == '__main__':
    main()
