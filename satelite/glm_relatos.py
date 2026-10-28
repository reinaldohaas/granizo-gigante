# -*- coding: utf-8 -*-
"""Quais celulas com raios (glm_celulas.csv / glm_trajetorias.csv) passaram sobre cada municipio com granizo.

Para cada relato: trajetorias com algum aglomerado a ate RAIO_KM do centroide do municipio dentro da janela
de horario do relato (UTC). Lista a passagem mais proxima, a hora, os flashes no intervalo de 10 min e, da
trajetoria inteira, inicio, fim, distancia e velocidade.

Saida: satelite/glm_relatos.csv
"""
import math
import os

import pandas as pd

from glm_trajetorias import municipios

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIO_KM = 25.0
# municipio, janela UTC (inicio, fim), origem da informacao
RELATOS = [
    ('Abelardo Luz', '2026-08-29 03:00', '2026-08-29 10:00', 'madrugada de 29/08 (ClicRDC)'),
    ('Ipuaçu', '2026-08-29 03:00', '2026-08-29 10:00', 'madrugada de 29/08 (ClicRDC)'),
    ('Bom Jesus', '2026-08-29 03:00', '2026-08-29 10:00', 'madrugada de 29/08 (ClicRDC)'),
    ('Entre Rios', '2026-08-29 03:00', '2026-08-29 10:00', 'madrugada de 29/08 (ClicRDC)'),
    ('Ouro Verde', '2026-08-29 03:00', '2026-08-29 10:00', 'madrugada de 29/08 (ClicRDC)'),
    ('Joaçaba', '2026-08-29 09:30', '2026-08-29 11:30', 'alerta 07:12 local (Defesa Civil)'),
    ('Campos Novos', '2026-08-29 09:30', '2026-08-29 11:30', 'alerta 07:12 local (Defesa Civil)'),
    ('Biguaçu', '2026-08-29 20:00', '2026-08-29 22:30', '~18h local (ND Mais); 22:00–22:30 UTC (resumo)'),
    ('Florianópolis', '2026-08-29 21:30', '2026-08-29 23:30', '22:00–23:00 UTC (resumo)'),
]


def km(la1, lo1, la2, lo2):
    return math.hypot((lo2 - lo1) * 111.32 * math.cos(math.radians(0.5 * (la1 + la2))), (la2 - la1) * 110.57)


def main():
    cel = pd.read_csv(os.path.join(AQUI, 'glm_celulas.csv'), parse_dates=['t'])
    tr = pd.read_csv(os.path.join(AQUI, 'glm_trajetorias.csv')).set_index('id')
    cent = municipios()
    linhas = []
    for nome, a, b, fonte in RELATOS:
        lo, la = cent[nome]
        c = cel[(cel.t >= a) & (cel.t <= b)].copy()
        c['d_km'] = [km(la, lo, y, x) for y, x in zip(c.lat, c.lon)]
        c = c[c.d_km <= RAIO_KM]
        if c.empty:
            linhas.append(dict(municipio=nome, fonte=fonte, passagem='nenhuma célula a ≤ 25 km'))
            continue
        for tid, g in c.dropna(subset=['traj']).groupby('traj'):
            p = g.loc[g.d_km.idxmin()]
            t = tr.loc[int(tid)]
            linhas.append(dict(municipio=nome, fonte=fonte, traj=int(tid), passagem=f"{p.t:%d/%m %H:%M}",
                               dist_km=round(p.d_km), flashes_10min=int(p.flashes), traj_inicio=t.inicio,
                               traj_lon0=t.lon0, traj_lat0=t.lat0, traj_fim=t.fim, traj_dist_km=t.dist_km,
                               traj_vel_m_s=t.vel_m_s, traj_rumo=t.rumo_graus, traj_flashes=t.flashes))
        if c.traj.isna().all():
            p = c.loc[c.d_km.idxmin()]
            linhas.append(dict(municipio=nome, fonte=fonte, passagem=f"{p.t:%d/%m %H:%M} (célula sem trajetória ≥ 1 h)",
                               dist_km=round(p.d_km), flashes_10min=int(p.flashes)))
    out = pd.DataFrame(linhas)
    out.to_csv(os.path.join(AQUI, 'glm_relatos.csv'), index=False)
    pd.set_option('display.width', 250)
    pd.set_option('display.max_columns', 20)
    print(out.to_string(index=False))


if __name__ == '__main__':
    main()
