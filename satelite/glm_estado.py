# -*- coding: utf-8 -*-
"""Flashes do GLM (GOES-19) sobre Santa Catarina e arredores, para rastrear as celulas de 29/08/2026.

Os radares do DECEA nao alcancam o oeste de SC neste dia (Santiago sem eco, Morro da Igreja fora de alcance),
entao a trajetoria das celulas desde o oeste vem dos raios.

Mesmo principio de clima_espacial_amas/scripts/75_baixa_glm.py: cada granulo de 20 s e lido na memoria,
filtrado na caixa e descartado; so os pontos ficam. Diferencas: balde noaa-goes19 (GOES-East desde 2025),
leitura com netCDF4 (memory=) em vez de xarray/h5netcdf, e downloads em paralelo.
Retomavel: horas completas ficam em glm_horas_lidas.txt e sao puladas.

Uso: python satelite/glm_estado.py --ini "2026-08-29 00" --fim "2026-08-30 06"
Saida: satelite/glm_pontos_sc.csv  (t_utc, lon, lat, energia_J)
"""
import argparse
import datetime as dt
import os
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import netCDF4
import numpy as np
import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
BUCKET = "https://noaa-goes19.s3.amazonaws.com"
CAIXA = (-58.0, -30.5, -46.0, -25.0)          # lon0, lat0, lon1, lat1
SAIDA = os.path.join(AQUI, "glm_pontos_sc.csv")
LIDAS = os.path.join(AQUI, "glm_horas_lidas.txt")
HDF5 = threading.Lock()
SES = requests.Session()
SES.headers.update({"User-Agent": "floripa-granizo/glm"})


def lista(dia_hora):
    pref = "GLM-L2-LCFA/%s/%03d/%02d/" % (dia_hora.year, dia_hora.timetuple().tm_yday, dia_hora.hour)
    chaves, token = [], None
    while True:
        p = {"list-type": "2", "prefix": pref}
        if token:
            p["continuation-token"] = token
        r = SES.get(BUCKET, params=p, timeout=60)
        r.raise_for_status()
        raiz = ET.fromstring(r.content)
        ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        chaves += [c.find("s3:Key", ns).text for c in raiz.findall("s3:Contents", ns)]
        if raiz.find("s3:IsTruncated", ns).text != "true":
            return chaves
        token = raiz.find("s3:NextContinuationToken", ns).text


def le(chave):
    for _ in range(3):
        try:
            r = SES.get("%s/%s" % (BUCKET, chave), timeout=120)
            r.raise_for_status()
            with HDF5, netCDF4.Dataset("g", memory=r.content) as d:  # HDF5 nao e thread-safe
                if "flash_lat" not in d.variables:
                    return []
                la = d["flash_lat"][:].astype(float)
                lo = d["flash_lon"][:].astype(float)
                en = d["flash_energy"][:].astype(float) if "flash_energy" in d.variables else np.full(la.shape, np.nan)
                tv = d["flash_time_offset_of_first_event"]
                tt = netCDF4.num2date(tv[:], tv.units, only_use_cftime_datetimes=False,
                                      only_use_python_datetimes=True)
                m = (lo >= CAIXA[0]) & (lo <= CAIXA[2]) & (la >= CAIXA[1]) & (la <= CAIXA[3])
                return [("%s" % t.strftime("%Y-%m-%d %H:%M:%S"), round(float(x), 4), round(float(y), 4), float(e))
                        for t, x, y, e in zip(np.asarray(tt)[m], lo[m], la[m], en[m])]
        except Exception:
            continue
    raise RuntimeError(chave)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ini", default="2026-08-29 00")
    ap.add_argument("--fim", default="2026-08-30 06")
    ap.add_argument("--threads", type=int, default=16)
    a = ap.parse_args()
    t0 = dt.datetime.strptime(a.ini, "%Y-%m-%d %H")
    t1 = dt.datetime.strptime(a.fim, "%Y-%m-%d %H")
    lidas = set(open(LIDAS).read().split()) if os.path.exists(LIDAS) else set()
    novo = not os.path.exists(SAIDA)
    with open(SAIDA, "a", encoding="utf-8") as f, ThreadPoolExecutor(a.threads) as pool:
        if novo:
            f.write("t_utc,lon,lat,energia_J\n")
        h = t0
        while h <= t1:
            tag = h.strftime("%Y%m%d%H")
            if tag in lidas:
                h += dt.timedelta(hours=1)
                continue
            chaves = [c for c in lista(h) if c.endswith(".nc")]
            try:
                res = list(pool.map(le, chaves))
            except RuntimeError as e:
                print(f"{tag}: falhou {e}; hora sera refeita", flush=True)
                h += dt.timedelta(hours=1)
                continue
            n = 0
            for pts in res:
                for p in pts:
                    f.write("%s,%s,%s,%.3e\n" % p)
                    n += 1
            f.flush()
            with open(LIDAS, "a") as g:
                g.write(tag + "\n")
            print(f"{tag}: {len(chaves)} granulos, {n} flashes na caixa", flush=True)
            h += dt.timedelta(hours=1)


if __name__ == "__main__":
    main()
