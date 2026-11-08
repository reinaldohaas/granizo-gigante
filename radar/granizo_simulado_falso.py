# -*- coding: utf-8 -*-
"""O Grell-Freitas acerta a Ilha a custa de por granizo em muitos lugares?

Para cada rodada (22/10, E0-E3, F1-F4), no d03 de 18 UTC de 29/08 a 02 UTC de 30/08:
  - area total com HAILCAST >= 20 mm em algum momento (km2);
  - fracao dessa area que fica a mais de 25 km de qualquer nucleo do radar Morro da Igreja (~>= 50 dBZ)
    observado a +-20 min: granizo simulado onde o radar nao viu celula forte (candidato a alarme falso);
  - se ha granizo a <= 25 km dos relatos da Ilha (acerto).
Sem relatos de granizo espalhados nao da para confirmar alarme falso; isto mede so a coerencia com o radar.

Saida: radar/granizo_simulado_falso.csv
"""
import math
import os

import netCDF4
import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
RODADAS = [('22/10 (KF)', os.path.join(AQUI, 'wrf'))] + [
    (f'{m} ({"GF" if m[0] == "F" or m.startswith("E3") else "KF"})', os.path.join(AQUI, 'wrf', 'ensemble', m))
    for m in ('E0_controle', 'E1_mynn', 'E2_inicio06', 'E3_gf_d01', 'F1_gf_mynn', 'F2_gf_inicio06', 'F3_gf_skebs1', 'F4_gf_skebs2')]
ILHA = [(-48.655, -27.494), (-48.46, -27.43)]
LIMIAR, RAIO = 20.0, 25.0


def main():
    nuc = pd.read_csv(os.path.join(AQUI, 'nucleos_mi_dia.csv'), parse_dates=['t'])
    linhas = []
    for nome, pasta in RODADAS:
        d = netCDF4.Dataset(os.path.join(pasta, 'recorte_trajetorias_d03.nc'))
        tempos = pd.to_datetime([b''.join(t).decode().replace('_', ' ') for t in d['Times'][:]])
        lat, lon = np.array(d['XLAT'][0]), np.array(d['XLONG'][0])
        cos = math.cos(math.radians(-27.5))
        celula_km2 = 1.0 if lat.shape[1] in (180, 240) else 9.0
        com_granizo = np.zeros(lat.shape, bool)
        sem_radar = np.zeros(lat.shape, bool)
        perto_ilha = np.zeros(lat.shape, bool)
        for x, y in ILHA:
            perto_ilha |= np.hypot((lon - x) * 111.32 * cos, (lat - y) * 110.57) <= RAIO
        acerto = 0.0
        for i, t in enumerate(tempos):
            if not (pd.Timestamp('2026-08-29 18:00') <= t <= pd.Timestamp('2026-08-30 02:00')):
                continue
            hc = np.array(d['HAILCAST_DIAM_MAX'][i])
            m = (hc >= LIMIAR) & (hc < 150)
            if not m.any():
                continue
            com_granizo |= m
            n = nuc[(nuc.t >= t - pd.Timedelta(minutes=20)) & (nuc.t <= t + pd.Timedelta(minutes=20))]
            perto = np.zeros(lat.shape, bool)
            for x, y in zip(n.lon, n.lat):
                perto |= np.hypot((lon - x) * 111.32 * cos, (lat - y) * 110.57) <= RAIO
            sem_radar |= m & ~perto
            if t >= pd.Timestamp('2026-08-29 21:50') and t <= pd.Timestamp('2026-08-29 23:10'):
                acerto = max(acerto, float(np.where(perto_ilha, np.where(hc < 150, hc, 0), 0).max()))
        area = com_granizo.sum() * celula_km2
        linhas.append(dict(rodada=nome, area_granizo_20mm_km2=int(area),
                           fracao_sem_nucleo_radar=round(float(sem_radar.sum() / max(com_granizo.sum(), 1)), 2),
                           granizo_perto_ilha_mm=round(acerto, 1)))
    out = pd.DataFrame(linhas)
    out.to_csv(os.path.join(AQUI, 'granizo_simulado_falso.csv'), index=False)
    print(out.to_string(index=False))


if __name__ == '__main__':
    main()
