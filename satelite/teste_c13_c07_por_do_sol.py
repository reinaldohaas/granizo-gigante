# -*- coding: utf-8 -*-
"""
A subida do C13-C07 sob topos frios entre 21:00 e 21:30 UTC (resumo I-SSTS) e efeito da celula ou do por do sol?

O C07 (3,9 um) recebe radiacao solar refletida de dia; a noite so emite. Por isso, sob topo de gelo frio, C13-C07
fica perto de 0 (ou negativo) de dia e positivo a noite, em qualquer nuvem. Em Florianopolis, em 29/08, o sol se poe
por volta de 20:58 UTC, e o terminador anda para oeste (~21:15 UTC em -53 graus).

Teste: para cada varredura de 20:00 a 23:30 UTC, todos os pixels com C13 <= -50 C num dominio largo (SC e mar) sao
divididos em "celula do granizo" (ate RAIO_KM da trajetoria do nucleo no radar Morro da Igreja) e "controle" (o resto).
Compara-se o C13-C07 dos dois grupos em funcao do horario e do angulo zenital solar (SZA) de cada pixel, e a anomalia
da celula em relacao a mediana do controle no mesmo intervalo de SZA e de C13.

Saidas em satelite/teste_por_do_sol/: tabela_c13_c07.csv, c13_c07_x_sza.png, c13_c07_x_horario.png.
Usa as funcoes de download/reamostragem de gerar_goes_ir.py (mesmos arquivos ABI-L2-CMIPF do GOES-19 no AWS).
"""
import csv
import datetime as dt
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import s3fs

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from gerar_goes_ir import campo, listar_abi  # noqa: E402  (fica na raiz do projeto)

SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'teste_por_do_sol')
INICIO, FIM = dt.datetime(2026, 8, 29, 20, 0), dt.datetime(2026, 8, 29, 23, 30)
LONS = np.arange(-54.0, -46.0 + 1e-9, 0.02)
LATS = np.arange(-25.0, -30.0 - 1e-9, -0.02)
FRIO = -50.0          # topo frio, como no resumo
RAIO_KM = 35.0        # celula + bigorna + paralaxe do GOES (~10-15 km para topo de 12 km nesta latitude)

# trajetoria do nucleo do granizo no MaxCAPPI do Morro da Igreja (radar/comparar_wrf_radar.py)
TRAJ = [(dt.datetime(2026, 8, 29, 20, 36), -27.56, -49.93), (dt.datetime(2026, 8, 29, 21, 16), -27.58, -49.42),
        (dt.datetime(2026, 8, 29, 21, 36), -27.58, -49.20), (dt.datetime(2026, 8, 29, 22, 16), -27.50, -48.61),
        (dt.datetime(2026, 8, 29, 22, 36), -27.41, -48.32)]


def posicao(t):
    """Centro da celula no instante t (interpolado; extrapolado com a ultima velocidade fora da trajetoria)."""
    s = np.array([(p[0] - TRAJ[0][0]).total_seconds() for p in TRAJ])
    x = (t - TRAJ[0][0]).total_seconds()
    if x <= s[0] or x >= s[-1]:
        i = 0 if x <= s[0] else -2
        f = (x - s[i]) / (s[i + 1] - s[i])
        return (TRAJ[i][1] + f * (TRAJ[i + 1][1] - TRAJ[i][1]), TRAJ[i][2] + f * (TRAJ[i + 1][2] - TRAJ[i][2]))
    return float(np.interp(x, s, [p[1] for p in TRAJ])), float(np.interp(x, s, [p[2] for p in TRAJ]))


def zenital(t, LAT, LON):
    """Angulo zenital solar (graus), formulas da NOAA (precisao ~0,1 grau, suficiente aqui)."""
    g = 2 * np.pi / 365 * (t.timetuple().tm_yday - 1 + (t.hour - 12 + t.minute / 60) / 24)
    eqt = 229.18 * (7.5e-5 + 1.868e-3 * np.cos(g) - 3.2077e-2 * np.sin(g) - 1.4615e-2 * np.cos(2 * g)
                    - 4.0849e-2 * np.sin(2 * g))
    dec = (6.918e-3 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 6.758e-3 * np.cos(2 * g)
           + 9.07e-4 * np.sin(2 * g) - 2.697e-3 * np.cos(3 * g) + 1.48e-3 * np.sin(3 * g))
    ha = np.radians((t.hour * 60 + t.minute + eqt + 4 * LON) / 4 - 180)
    la = np.radians(LAT)
    return np.degrees(np.arccos(np.sin(la) * np.sin(dec) + np.cos(la) * np.cos(dec) * np.cos(ha)))


def main():
    os.makedirs(SAIDA, exist_ok=True)
    fs = s3fs.S3FileSystem(anon=True)
    c07, c13 = listar_abi(fs, INICIO, FIM, 'C07'), listar_abi(fs, INICIO, FIM, 'C13')
    tempos = sorted(set(c07) & set(c13))
    print(f'{len(tempos)} varreduras com C07 e C13')
    with ThreadPoolExecutor(max_workers=6) as ex:
        t07 = list(ex.map(lambda t: campo(fs, c07[t], LONS, LATS), tempos))
        t13 = list(ex.map(lambda t: campo(fs, c13[t], LONS, LATS), tempos))

    LON, LAT = np.meshgrid(LONS, LATS)
    linhas, pts = [], []
    for t, a07, a13 in zip(tempos, t07, t13):
        btd, sza = a13 - a07, zenital(t, LAT, LON)
        la0, lo0 = posicao(t)
        dist = np.hypot((LAT - la0) * 111.2, (LON - lo0) * 111.2 * np.cos(np.radians(la0)))
        frio = a13 <= FRIO
        cel, ctl = frio & (dist <= RAIO_KM), frio & (dist > RAIO_KM + 20)
        sza_c = float(np.median(sza[cel])) if cel.any() else np.nan
        est = lambda m, f: f(btd[m]) if m.any() else np.nan
        # o resumo usou o MAXIMO de C13-C07 sob topos <= -50 C; aqui vao mediana, p95 e maximo dos dois grupos
        linhas.append([t.strftime('%H:%M'), cel.sum(), ctl.sum(), est(cel, np.median), est(ctl, np.median),
                       np.min(a13[cel]) if cel.any() else np.nan, sza_c, la0, lo0,
                       est(cel, lambda v: np.percentile(v, 95)), est(ctl, lambda v: np.percentile(v, 95)),
                       est(cel, np.max), est(ctl, np.max)])
        for g, m in (('celula', cel), ('controle', ctl)):
            pts += [(t, g, s, b, c) for s, b, c in zip(sza[m], btd[m], a13[m])]

    with open(os.path.join(SAIDA, 'tabela_c13_c07.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['utc', 'n_celula', 'n_controle', 'btd_med_celula_K', 'btd_med_controle_K', 'c13_min_celula_C',
                    'sza_med_celula', 'lat_celula', 'lon_celula', 'btd_p95_celula_K', 'btd_p95_controle_K',
                    'btd_max_celula_K', 'btd_max_controle_K'])
        w.writerows([[l[0], l[1], l[2]] + [f'{v:.2f}' for v in l[3:]] for l in linhas])
    print('utc   n_cel  n_ctl  med_cel med_ctl  p95_cel p95_ctl  max_cel max_ctl  C13min  SZAcel')
    for l in linhas:
        print(f'{l[0]}  {l[1]:5d} {l[2]:6d}  {l[3]:6.2f} {l[4]:6.2f}  {l[9]:6.2f} {l[10]:6.2f}  '
              f'{l[11]:6.2f} {l[12]:6.2f}  {l[5]:6.1f}  {l[6]:6.1f}')

    # anomalia da celula: BTD - mediana do controle no mesmo intervalo de SZA (1 grau) e de C13 (5 C)
    P = np.array([(s, b, c, g == 'celula') for _, g, s, b, c in pts])
    ctl = P[~P[:, 3].astype(bool)]
    cel = P[P[:, 3].astype(bool)]
    chave = lambda s, c: (np.floor(s), np.floor(c / 5))
    ref = {}
    for s, b, c, _ in ctl:
        ref.setdefault(chave(s, c), []).append(b)
    anom = [b - np.median(ref[chave(s, c)]) for s, b, c, _ in cel if len(ref.get(chave(s, c), [])) >= 30]
    print(f'anomalia da celula (BTD - mediana do controle com mesmo SZA e C13): mediana {np.median(anom):.2f} K, '
          f'p10..p90 {np.percentile(anom, 10):.2f}..{np.percentile(anom, 90):.2f} K, n = {len(anom)} pixels')

    bins = np.arange(70, 112, 1.0)
    fig, ax = plt.subplots(figsize=(9, 5.5), constrained_layout=True)
    for g, cor, M in (('controle (outros topos ≤ −50 °C)', '0.5', ctl), ('célula do granizo', 'C3', cel)):
        idx = np.digitize(M[:, 0], bins)
        x = [bins[i - 1] + 0.5 for i in range(1, len(bins)) if (idx == i).sum() >= 20]
        q = [np.percentile(M[idx == i, 1], [25, 50, 75]) for i in range(1, len(bins)) if (idx == i).sum() >= 20]
        if q:
            q = np.array(q)
            ax.fill_between(x, q[:, 0], q[:, 2], color=cor, alpha=0.25)
            ax.plot(x, q[:, 1], color=cor, lw=2, label=g)
    ax.axvline(90, color='k', ls='--', lw=0.8)
    ax.text(90.3, ax.get_ylim()[1] * 0.95, 'pôr do sol (SZA 90°)', fontsize=8, va='top')
    ax.set_xlabel('ângulo zenital solar no pixel (graus)')
    ax.set_ylabel('C13 − C07 (K), mediana e quartis')
    ax.set_title('GOES-19, 29/08/2026 20:00–23:30 UTC, pixels com C13 ≤ −50 °C')
    ax.legend()
    fig.savefig(os.path.join(SAIDA, 'c13_c07_x_sza.png'), dpi=130)

    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    h = [dt.datetime.strptime(l[0], '%H:%M') for l in linhas]
    ax.plot(h, [l[4] for l in linhas], 'o-', color='0.5', label='controle (mediana)')
    ax.plot(h, [l[3] for l in linhas], 's-', color='C3', label='célula do granizo (mediana)')
    ax.axvline(dt.datetime(1900, 1, 1, 20, 58), color='k', ls='--', lw=0.8)
    ax.text(dt.datetime(1900, 1, 1, 21, 0), ax.get_ylim()[0], ' pôr do sol em Florianópolis', fontsize=8, va='bottom')
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%H:%M'))
    ax.set_ylabel('C13 − C07 (K) sob topos ≤ −50 °C')
    ax.set_xlabel('UTC, 29/08/2026')
    ax.legend()
    fig.savefig(os.path.join(SAIDA, 'c13_c07_x_horario.png'), dpi=130)


if __name__ == '__main__':
    main()
