"""
Series de clima espacial em torno do granizo de Florianopolis (29/08/2026).

Reaproveita as funcoes de download do projeto do RS
(C:\\Users\\haas\\github\\clima_espacial_amas\\scripts\\toro_01_series_espaciais.py):
NMDB, Kp (GFZ), Dst (WDC Kyoto), Ey e AE (OMNI). O cache fica aqui
(clima_espacial/dados/), nao no repositorio do RS.

Uso (python com pandas, requests, matplotlib):
    python clima_espacial/baixar_series_espaciais.py --ini 2026-08-15 --fim 2026-09-05
Saida: clima_espacial/resultados/series_espaciais_<ini>_<fim>.csv (horario)
"""
import argparse
import pathlib

import pandas as pd

AQUI = pathlib.Path(__file__).resolve().parent
RS = pathlib.Path(r"C:\Users\haas\github\clima_espacial_amas\scripts\toro_01_series_espaciais.py")
NMDB_ESTACOES = [("OULU", 0.81), ("IRK3", 3.64), ("JUNG1", 4.49), ("MXCO", 8.28)]


def carregar_funcoes_rs():
    """Executa o modulo do RS sem o arquivo de caso (marcos de 2024) e com cache local."""
    src = RS.read_text(encoding="utf-8")
    src = src.replace('caso = _mod("toro_00_caso.py", "caso")',
                      'class caso:\n    MARCOS_SOLARES = []\n    SISMOS_UT = []')
    ns = {"__file__": str(RS), "__name__": "series_rs"}
    exec(compile(src, str(RS), "exec"), ns)
    ns["D_NMDB"] = AQUI / "dados" / "nmdb"
    ns["D_GEO"] = AQUI / "dados" / "geomag"
    for d in (ns["D_NMDB"], ns["D_GEO"]):
        d.mkdir(parents=True, exist_ok=True)
    return ns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ini", default="2026-08-15")
    ap.add_argument("--fim", default="2026-09-05")
    a = ap.parse_args()
    f = carregar_funcoes_rs()

    series = {}
    tentativas = [("Kp", lambda: f["kp_gfz"](a.ini, a.fim)),
                  ("Dst_nT", lambda: f["dst_kyoto"](a.ini, a.fim)),
                  ("Ey_mV_m", lambda: f["omni_var"](35, "Ey", a.ini, a.fim)),
                  ("AE_nT", lambda: f["omni_var"](41, "AE", a.ini, a.fim))]
    tentativas += [(f"GCR_{e}_pct", lambda e=e: f["nmdb"](e, a.ini, a.fim))
                   for e, _ in NMDB_ESTACOES]
    for nome, fn in tentativas:
        try:
            df = fn()
            series[nome] = df.set_index("tempo")["v"]
            print(f"  {nome:14s} {len(df):5d} valores  {df.tempo.min()} .. {df.tempo.max()}")
        except Exception as e:
            print(f"  {nome:14s} FALHOU: {e}")

    tab = pd.DataFrame(series).sort_index()
    tab = tab.resample("1h").mean()
    if "Kp" in tab:
        tab["Kp"] = tab["Kp"].ffill(limit=2)
    out = AQUI / "resultados"
    out.mkdir(exist_ok=True)
    arq = out / f"series_espaciais_{a.ini.replace('-', '')}_{a.fim.replace('-', '')}.csv"
    tab.to_csv(arq, float_format="%.3f")
    print("->", arq)


if __name__ == "__main__":
    main()
