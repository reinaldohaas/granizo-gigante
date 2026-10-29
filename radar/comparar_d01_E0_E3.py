# -*- coding: utf-8 -*-
"""d01 (9 km) do E0_controle (Kain-Fritsch) x E3_gf_d01 (Grell-Freitas), 29/08/2026 12-22 UTC.

Com feedback = 1, o d01 dentro do d02 (indices 35-85, ninho sem cumulus) recebe o d02; a diferenca entre os membros
nasce fora dele, na convecção parametrizada, e entra no d02 pelas bordas. Por isso:
  1) chuva convectiva (RAINC) e explicita (RAINNC) hora a hora, no d01 todo e fora do d02 (tabela do LEIA e mais);
  2) mapas de chuva 12-18 e 18-21 UTC dos dois membros, com o d02 e o d03 marcados;
  3) E3 - E0 as 18 e 20 UTC: T2, Q2 e vento a 10 m; theta-e e vento em 850 hPa;
  4) CAPE e CIN de parcela de camada misturada (50 hPa) as 18 UTC;
  5) perfil medio no ar que entra pela borda oeste do d02 (theta-e, q, vento) ao longo do dia.
Entradas: radar/wrf/ensemble/<membro>/recorte_d01_1222.nc. Saidas em radar/figuras/d01_E0_E3/.
"""
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np

from plotar_radar_mi import AQUI, SAIDA, contornos

MEMBROS = [('E0_controle', 'E0 Kain-Fritsch'), ('E3_gf_d01', 'E3 Grell-Freitas')]
D02 = (35, 85)                     # indices do d01 ocupados pelo d02 (i_parent_start 36, 151 / 3)
D03 = (35 + 15 // 3, 35 + 45 // 3, 35 + (15 + 240 // 3) // 3, 35 + (45 + 180 // 3) // 3)  # i0, j0, i1, j1 no d01
CELULA = (-27.56, -49.93)          # nascimento no radar, 20:36
OUT = os.path.join(SAIDA, 'd01_E0_E3')
RD, CP, G, K = 287.04, 1004.0, 9.81, 0.2857


def ler(m):
    f = nc.Dataset(os.path.join(AQUI, 'wrf', 'ensemble', m, 'recorte_d01_1222.nc'))
    d = {v: f[v][:].filled(np.nan) if np.ma.isMaskedArray(f[v][:]) else f[v][:] for v in f.variables if v != 'Times'}
    d['horas'] = [b''.join(t).decode()[11:16] for t in f['Times'][:]]
    d['p'] = d['P'] + d['PB']                                   # Pa
    d['tk'] = (d['T'] + 300.0) * (d['p'] / 1e5) ** K
    d['z'] = (d['PH'] + d['PHB']) / G
    d['z'] = 0.5 * (d['z'][:, 1:] + d['z'][:, :-1])             # altura nos niveis de massa
    d['u'] = 0.5 * (d['U'][..., 1:] + d['U'][..., :-1])
    d['v'] = 0.5 * (d['V'][:, :, 1:] + d['V'][:, :, :-1])
    return d


def esat(tk):
    return 611.2 * np.exp(17.67 * (tk - 273.15) / (tk - 29.65))


def theta_e(tk, p, q):
    """Bolton (1980), p em Pa, q em kg/kg."""
    e = q * p / (0.622 + q)
    tl = 2840.0 / (3.5 * np.log(tk) - np.log(np.maximum(e, 1e-3) / 100.0) - 4.805) + 55.0
    r = q / (1 - q)
    return tk * (1e5 / p) ** (0.2854 * (1 - 0.28 * r)) * np.exp((3.376 / tl - 0.00254) * r * 1e3 * (1 + 0.81 * r))


def no_nivel(campo, p, alvo):
    """Interpola campo (nz, ny, nx) para a pressao alvo (Pa), linear em ln p."""
    lp = np.log(p)
    k = np.clip((p > alvo).sum(axis=0), 1, p.shape[0] - 1)        # primeiro nivel acima do alvo
    i = np.indices(k.shape)
    a, b = lp[k - 1, i[0], i[1]], lp[k, i[0], i[1]]
    w = (np.log(alvo) - a) / (b - a)
    return campo[k - 1, i[0], i[1]] * (1 - w) + campo[k, i[0], i[1]] * w


def cape_ml(tk, p, q, z):
    """CAPE e CIN (J/kg) de parcela com a media dos 50 hPa mais baixos; ascensao pseudo-adiabatica por theta-e."""
    camada = p >= (p[0] - 5000.0)
    n = camada.sum(axis=0)
    th = ((tk * (1e5 / p) ** K) * camada).sum(axis=0) / n
    qm = (q * camada).sum(axis=0) / n
    p0 = p[0]
    t0 = th * (p0 / 1e5) ** K
    e = qm * p0 / (0.622 + qm)
    td = 243.5 / (17.67 / np.log(np.maximum(e, 1e-3) / 611.2) - 1) + 273.15
    tlcl = 1 / (1 / (td - 56) + np.log(t0 / td) / 800) + 56
    plcl = p0 * (tlcl / t0) ** (1 / K)
    the = theta_e(t0, p0, qm)
    # temperatura saturada com o theta-e da parcela em cada nivel (bissecao)
    lo, hi = np.full(p.shape, 150.0), np.full(p.shape, 330.0)
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        qs = 0.622 * esat(mid) / (p - 0.378 * esat(mid))
        maior = theta_e(mid, p, qs) > the
        hi = np.where(maior, mid, hi)
        lo = np.where(maior, lo, mid)
    tsat = 0.5 * (lo + hi)
    qsat = 0.622 * esat(tsat) / (p - 0.378 * esat(tsat))
    seco = p >= plcl
    tp = np.where(seco, th * (p / 1e5) ** K, tsat)
    qp = np.where(seco, qm, qsat)
    b = G * (tp * (1 + 0.61 * qp) - tk * (1 + 0.61 * q)) / (tk * (1 + 0.61 * q))
    dz = np.gradient(z, axis=0)
    acima = p >= 10000.0
    cape = np.where((b > 0) & acima, b * dz, 0).sum(axis=0)
    # CIN: negativo entre a superficie e o primeiro nivel flutuante acima do LCL
    flut = (b > 0) & ~seco
    lfc = np.where(flut.any(axis=0), flut.argmax(axis=0), 0)
    nivel = np.arange(p.shape[0])[:, None, None]
    cin = np.where((b < 0) & (nivel < lfc), b * dz, 0).sum(axis=0)
    return cape, cin


def caixa(ax, lo, la, i0, j0, i1, j1, **kw):
    xs = [lo[j0, i0], lo[j0, i1], lo[j1, i1], lo[j1, i0], lo[j0, i0]]
    ys = [la[j0, i0], la[j0, i1], la[j1, i1], la[j1, i0], la[j0, i0]]
    ax.plot(xs, ys, **kw)


def mapa(ax, d, titulo):
    lo, la = d['XLONG'][0], d['XLAT'][0]
    contornos(ax, 'America_do_Sul.shp', color='0.6', lw=0.5)
    contornos(ax, 'BR_Estados.shp', color='0.4', lw=0.6)
    caixa(ax, lo, la, D02[0], D02[0], D02[1], D02[1], color='k', lw=1.0, ls='--')
    caixa(ax, lo, la, *D03, color='k', lw=0.8, ls=':')
    ax.plot(CELULA[1], CELULA[0], '*', ms=12, mfc='yellow', mec='k', zorder=6)
    ax.set_xlim(lo.min(), lo.max())
    ax.set_ylim(la.min(), la.max())
    ax.set_title(titulo, fontsize=10)
    ax.set_aspect(1 / np.cos(np.radians(27.5)))


def main():
    os.makedirs(OUT, exist_ok=True)
    dd = {m: ler(m) for m, _ in MEMBROS}
    h = dd['E0_controle']['horas']
    fora = np.ones((120, 120), bool)
    fora[D02[0]:D02[1] + 1, D02[0]:D02[1] + 1] = False
    lo, la = dd['E0_controle']['XLONG'][0], dd['E0_controle']['XLAT'][0]
    oeste = fora & (lo < -51.0) & (la > -30.0) & (la < -25.0)   # faixa a oeste do d02, latitude do evento

    print('1) chuva acumulada desde 12 UTC (mm). d01: max/media; fora_d02: media; oeste: media a oeste do d02, 25-30 S')
    for m, rot in MEMBROS:
        d = dd[m]
        print(f'  {rot}')
        print('    hora  RAINC max/med   RAINNC max/med   PSFC min  | fora_d02 RAINC RAINNC | oeste RAINC RAINNC')
        for i, t in enumerate(h):
            rc, rn = d['RAINC'][i] - d['RAINC'][0], d['RAINNC'][i] - d['RAINNC'][0]
            print(f'    {t}  {rc.max():6.1f}/{rc.mean():5.2f}  {rn.max():7.1f}/{rn.mean():5.2f}  {d["PSFC"][i].min() / 100:7.1f}'
                  f'  |  {rc[fora].mean():5.2f} {rn[fora].mean():5.2f}  |  {rc[oeste].mean():5.2f} {rn[oeste].mean():5.2f}')

    # 2) mapas de chuva
    fig, axs = plt.subplots(2, 3, figsize=(17, 11), constrained_layout=True)
    niveis = [1, 5, 10, 20, 40, 80]
    for r, (m, rot) in enumerate(MEMBROS):
        d = dd[m]
        tot = d['RAINC'] + d['RAINNC']
        i18, i21 = h.index('18:00'), h.index('21:00')
        for c, (a, b, nome) in enumerate(((0, i18, '12-18 UTC'), (i18, i21, '18-21 UTC'))):
            cs = axs[r, c].contourf(lo, la, tot[b] - tot[a], niveis, cmap='YlGnBu', extend='max')
            axs[r, c].contour(lo, la, d['RAINC'][b] - d['RAINC'][a], [1], colors='r', linewidths=0.6)
            mapa(axs[r, c], d, f'{rot}: chuva total {nome} (vermelho: RAINC ≥ 1 mm)')
        cs2 = axs[r, 2].contourf(lo, la, d['RAINC'][i21] - d['RAINC'][0], niveis, cmap='OrRd', extend='max')
        mapa(axs[r, 2], d, f'{rot}: só RAINC 12-21 UTC')
    fig.colorbar(cs, ax=axs[:, :2], shrink=0.5, label='mm')
    fig.colorbar(cs2, ax=axs[:, 2], shrink=0.5, label='mm')
    fig.suptitle('d01 9 km. Tracejado: d02 (sem cumulus; com feedback o d01 ali é o d02). Pontilhado: d03. ★ nascimento da célula no radar (20:36)')
    fig.savefig(os.path.join(OUT, 'chuva_d01.png'), dpi=100)
    plt.close(fig)

    # 3) diferencas E3 - E0 e 4) CAPE/CIN
    e0, e3 = dd['E0_controle'], dd['E3_gf_d01']
    fig, axs = plt.subplots(2, 4, figsize=(22, 11), constrained_layout=True)
    print('3) E3 - E0 (media | p05..p95) na faixa oeste e no d02')
    reg = {'oeste': oeste, 'd02': ~fora}
    for r, t in enumerate(('18:00', '20:00')):
        i = h.index(t)
        dt2 = e3['T2'][i] - e0['T2'][i]
        dq2 = (e3['Q2'][i] - e0['Q2'][i]) * 1e3
        te = {m: no_nivel(theta_e(d['tk'][i], d['p'][i], d['QVAPOR'][i]), d['p'][i], 85000.0) for m, d in dd.items()}
        dte = te['E3_gf_d01'] - te['E0_controle']
        for nome, campo in (('T2 (K)', dt2), ('Q2 (g/kg)', dq2), ('θe 850 (K)', dte)):
            print(f'  {t} {nome:11s}', '  '.join(f'{k}: {np.nanmean(campo[m]):+.2f} | {np.nanpercentile(campo[m], 5):+.1f}..{np.nanpercentile(campo[m], 95):+.1f}'
                                              for k, m in reg.items()))
        for c, (campo, nome, lim) in enumerate(((dt2, 'T2 (K)', 4), (dq2, 'Q2 (g/kg)', 4), (dte, 'θe 850 hPa (K)', 8))):
            cs = axs[r, c].pcolormesh(lo, la, campo, cmap='RdBu_r', vmin=-lim, vmax=lim)
            if c == 0:
                s = 6
                axs[r, c].quiver(lo[::s, ::s], la[::s, ::s], (e3['U10'][i] - e0['U10'][i])[::s, ::s],
                                 (e3['V10'][i] - e0['V10'][i])[::s, ::s], scale=120, width=0.002)
            mapa(axs[r, c], e0, f'E3 − E0 {t}: {nome}')
            fig.colorbar(cs, ax=axs[r, c], shrink=0.6)
        u = {m: no_nivel(d['u'][i], d['p'][i], 85000.0) for m, d in dd.items()}
        v = {m: no_nivel(d['v'][i], d['p'][i], 85000.0) for m, d in dd.items()}
        cs = axs[r, 3].pcolormesh(lo, la, te['E3_gf_d01'], cmap='turbo', vmin=310, vmax=350)
        s = 6
        for m, cor in (('E0_controle', 'k'), ('E3_gf_d01', 'm')):
            axs[r, 3].quiver(lo[::s, ::s], la[::s, ::s], u[m][::s, ::s], v[m][::s, ::s], color=cor, scale=500, width=0.002)
        mapa(axs[r, 3], e3, f'{t}: θe 850 do E3; vento 850 E0 (preto) e E3 (magenta)')
        fig.colorbar(cs, ax=axs[r, 3], shrink=0.6)
    fig.suptitle('E3 (Grell-Freitas) − E0 (Kain-Fritsch) no d01. Setas no 1º painel: diferença do vento a 10 m')
    fig.savefig(os.path.join(OUT, 'diferencas_d01.png'), dpi=95)
    plt.close(fig)

    print('4) CAPE / CIN de camada misturada (J/kg)')
    fig, axs = plt.subplots(2, 2, figsize=(14, 12), constrained_layout=True)
    for r, (m, rot) in enumerate(MEMBROS):
        d = dd[m]
        for t in ('15:00', '18:00', '20:00'):
            i = h.index(t)
            cape, cin = cape_ml(d['tk'][i], d['p'][i], d['QVAPOR'][i], d['z'][i])
            dist = np.hypot((la - CELULA[0]) * 111.2, (lo - CELULA[1]) * 98.6)
            perto = dist <= 60
            print(f'  {rot} {t}: oeste CAPE med {cape[oeste].mean():5.0f} max {cape[oeste].max():5.0f} | '
                  f'a <= 60 km do nascimento: CAPE med {cape[perto].mean():5.0f} max {cape[perto].max():5.0f}, '
                  f'CIN med {cin[perto].mean():5.0f}')
            if t == '18:00':
                cs = axs[r, 0].pcolormesh(lo, la, cape, cmap='magma_r', vmin=0, vmax=3500)
                mapa(axs[r, 0], d, f'{rot} {t}: CAPE ML50')
                fig.colorbar(cs, ax=axs[r, 0], shrink=0.6, label='J/kg')
                cs = axs[r, 1].pcolormesh(lo, la, cin, cmap='Blues_r', vmin=-300, vmax=0)
                mapa(axs[r, 1], d, f'{rot} {t}: CIN ML50')
                fig.colorbar(cs, ax=axs[r, 1], shrink=0.6, label='J/kg')
    fig.savefig(os.path.join(OUT, 'cape_cin_18utc.png'), dpi=95)
    plt.close(fig)

    # 5) ar que entra pela borda oeste do d02: coluna i = 33-34, j na faixa do d02
    print('5) borda oeste do d02 (media em j 35-85, colunas i 33-34): theta-e e q 850 hPa, u 850 (m/s)')
    fig, axs = plt.subplots(1, 3, figsize=(17, 5), constrained_layout=True)
    for m, rot in MEMBROS:
        d = dd[m]
        serie = []
        for i in range(len(h)):
            te = no_nivel(theta_e(d['tk'][i], d['p'][i], d['QVAPOR'][i]), d['p'][i], 85000.0)
            q8 = no_nivel(d['QVAPOR'][i], d['p'][i], 85000.0) * 1e3
            u8 = no_nivel(d['u'][i], d['p'][i], 85000.0)
            b = (slice(D02[0], D02[1] + 1), slice(33, 35))
            serie.append((te[b].mean(), q8[b].mean(), u8[b].mean()))
        serie = np.array(serie)
        print(f'  {rot}:', '  '.join(f'{t} {a:.1f}/{b:.1f}/{c:.1f}' for t, (a, b, c) in zip(h, serie)))
        for k, nome in enumerate(('θe 850 (K)', 'q 850 (g/kg)', 'u 850 (m/s)')):
            axs[k].plot(h, serie[:, k], marker='o', label=rot)
            axs[k].set_title(f'Borda oeste do d02: {nome}')
    for ax in axs:
        ax.legend()
        ax.tick_params(axis='x', rotation=45)
    fig.savefig(os.path.join(OUT, 'borda_oeste_d02.png'), dpi=100)
    plt.close(fig)


if __name__ == '__main__':
    main()
