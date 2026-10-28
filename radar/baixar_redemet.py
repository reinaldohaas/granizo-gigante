# -*- coding: utf-8 -*-
"""Baixa imagens MaxCAPPI/CAPPI dos radares do DECEA (API REDEMET) para o evento de 29-30/08/2026.

Uso:  set REDEMET_KEY=...   (a chave nao fica gravada em arquivo)
      python baixar_redemet.py [tipo] [radar ...]      ex.: python baixar_redemet.py maxcappi mi cn sg

Usa o curl.exe do Windows: o certificado do DECEA (cadeia ICP-Brasil) nao esta no bundle do curl/Python do msys.
Grava radar/<radar>/<tipo>/AAAAMMDD_HHMMSS.png e radar/<radar>/<tipo>/quadros.csv (horario, limites, url).
"""
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

CURL = r'C:\Windows\System32\curl.exe'
API = 'https://api-redemet.decea.mil.br/produtos/radar/{tipo}?api_key={key}&data={data}&area={area}&anima=15'
INICIO, FIM = datetime(2026, 8, 29, 12), datetime(2026, 8, 30, 6)
AQUI = os.path.dirname(os.path.abspath(__file__))


def baixar(url, destino=None):
    cmd = [CURL, '-s', '-f', '-m', '120', '-A', 'Mozilla/5.0', url]
    if destino:
        cmd[1:1] = ['-o', destino]
    for _ in range(4):  # o servidor do DECEA derruba conexoes de vez em quando (curl rc=56)
        r = subprocess.run(cmd, capture_output=True)
        if not r.returncode:
            return r.stdout
    raise RuntimeError(f'curl rc={r.returncode}')


def main():
    key = os.environ['REDEMET_KEY']
    tipo = sys.argv[1] if len(sys.argv) > 1 else 'maxcappi'
    radares = sys.argv[2:] or ['mi']
    for area in radares:
        pasta = os.path.join(AQUI, area, tipo)
        os.makedirs(pasta, exist_ok=True)
        quadros = {}
        h = INICIO
        while h <= FIM:
            resp = json.loads(baixar(API.format(tipo=tipo, key=key, data=h.strftime('%Y%m%d%H'), area=area)))
            for grupo in resp['data']['radar']:
                for r in grupo:
                    if r['localidade'] == area and r['path']:
                        quadros[r['data']] = r
            h += timedelta(hours=1)
        with open(os.path.join(pasta, 'quadros.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['data_utc', 'arquivo', 'lon_min', 'lon_max', 'lat_min', 'lat_max', 'lat_center', 'lon_center', 'url'])
            for data in sorted(quadros):
                r = quadros[data]
                nome = datetime.strptime(data, '%Y-%m-%d %H:%M:%S').strftime('%Y%m%d_%H%M%S') + '.png'
                destino = os.path.join(pasta, nome)
                if not os.path.exists(destino):
                    baixar(r['path'], destino)
                w.writerow([data, nome, r['lon_min'], r['lon_max'], r['lat_min'], r['lat_max'],
                            r['lat_center'], r['lon_center'], r['path']])
        print(f'{area} {tipo}: {len(quadros)} quadros em {pasta}')


if __name__ == '__main__':
    main()
