"""
Baixa os magnetometros usados no indice Jz do projeto do RS para o caso de
Florianopolis (agosto e inicio de setembro de 2026).

  Embrace MagNet (INPE): arquivos diarios stnDDmmm.YYm, 1 min
      -> clima_espacial/dados/magnetometros_2026/
  INTERMAGNET (GIN/BGS): PIL, LAS, TRW, VSS, mensal IAGA-2002
      -> clima_espacial/dados/intermagnet/  (<OBS>_<YYYYMM>_iaga.min)

Mesmo formato e mesmos nomes que 40_qa_rede.py e 42_jz_reconstrucao.py leem.
Nada e sobrescrito: arquivo que ja existe nao e baixado de novo.

Uso: python clima_espacial/baixar_magnetometros.py --ini 2026-08-01 --fim 2026-09-10
"""
import argparse
import pathlib
import time

import pandas as pd
import requests

AQUI = pathlib.Path(__file__).resolve().parent
EMBRACE = ["ARA", "EUS", "SLZ", "STM", "PVE", "CXP", "JAT", "TCM", "SJC",
           "VSS", "MED", "SMS", "RGA", "CHI"]
INTERMAGNET = ["PIL", "LAS", "TRW", "VSS"]
MES = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
UA = {"User-Agent": "Mozilla/5.0"}


def embrace(ini, fim, pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    resumo = {}
    for est in EMBRACE:
        ok = 0
        for dia in pd.date_range(ini, fim, freq="D"):
            nome = f"{est.lower()}{dia.day:02d}{MES[dia.month - 1]}.{dia.year % 100:02d}m"
            fr = pasta / nome
            if fr.exists():
                ok += 1
                continue
            url = f"https://embracedata.inpe.br/magnetometer/{est}/{dia.year}/{nome}"
            for tentativa in range(3):
                try:
                    r = requests.get(url, timeout=60, headers=UA)
                    if r.status_code == 200 and len(r.content) > 200:
                        fr.write_bytes(r.content)
                        ok += 1
                    break
                except requests.RequestException:
                    time.sleep(5)
        resumo[est] = ok
        print(f"  Embrace {est}: {ok} dias", flush=True)
    return resumo


def intermagnet(ini, fim, pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    for obs in INTERMAGNET:
        for mes in pd.period_range(ini, fim, freq="M"):
            fr = pasta / f"{obs}_{mes.year}{mes.month:02d}_iaga.min"
            if fr.exists():
                print(f"  INTERMAGNET {obs} {mes}: ja existe", flush=True)
                continue
            txt = None
            for estado in ("definitive", "quasi-def", "adjusted", "reported"):
                url = ("https://imag-data.bgs.ac.uk/GIN_V1/GINServices?Request=GetData"
                       f"&Format=iaga2002&observatoryIagaCode={obs}&samplesPerDay=Minute"
                       f"&dataStartDate={mes.year}-{mes.month:02d}-01"
                       f"&dataDuration={mes.days_in_month}&publicationState={estado}")
                try:
                    r = requests.get(url, timeout=180, headers=UA)
                except requests.RequestException as e:
                    print(f"  INTERMAGNET {obs} {mes} ({estado}): erro {e}", flush=True)
                    continue
                cand = r.content.decode("latin-1", errors="ignore")
                if r.status_code == 200 and "DATE" in cand and cand.count("\n") > 100:
                    txt = cand
                    print(f"  INTERMAGNET {obs} {mes}: {estado}", flush=True)
                    break
            if txt:
                fr.write_text(txt, encoding="utf-8")
            else:
                print(f"  INTERMAGNET {obs} {mes}: sem dado", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ini", default="2026-08-01")
    ap.add_argument("--fim", default="2026-09-10")
    a = ap.parse_args()
    intermagnet(a.ini, a.fim, AQUI / "dados" / "intermagnet")
    embrace(a.ini, a.fim, AQUI / "dados" / "magnetometros_2026")


if __name__ == "__main__":
    main()
