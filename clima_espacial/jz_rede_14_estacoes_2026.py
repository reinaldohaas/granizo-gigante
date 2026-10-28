"""
Jz da rede de magnetometros pelo metodo do pesquisador
(clima_espacial_amas/scripts/calcular_rede_completa_14_estacoes_jz.py),
aplicado ao periodo do granizo de Florianopolis.

O calculo e o MESMO do original (inversao por minimos quadrados com as estacoes
ativas, linha de base = mediana movel de 1440 min, passo de 15 min). So mudam:
periodo, pasta dos dados (Embrace baixado em clima_espacial/dados/magnetometros_2026),
sufixo do ano no nome dos arquivos e pastas de saida. O original nao e alterado.

Unidade: o original multiplica (1/mu0)*rot(B) [A/m2] por 1e9, o que da nA/m2,
embora a coluna se chame Jz_pA_m2. A saida aqui mantem o nome da coluna do
original para comparacao direta e acrescenta Jz_nA_m2 com o mesmo valor.

Uso: python clima_espacial/jz_rede_14_estacoes_2026.py --ini 2026-08-01 --fim 2026-09-10
"""
import argparse
import pathlib

import matplotlib
matplotlib.use("Agg")

AQUI = pathlib.Path(__file__).resolve().parent
ORIGINAL = pathlib.Path(r"C:\Users\haas\github\clima_espacial_amas\scripts"
                        r"\calcular_rede_completa_14_estacoes_jz.py")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ini", default="2026-08-01")
    ap.add_argument("--fim", default="2026-09-10")
    a = ap.parse_args()
    y0, m0, d0 = (int(x) for x in a.ini.split("-"))
    y1, m1, d1 = (int(x) for x in a.fim.split("-"))
    yy = f"{y0 % 100:02d}"
    saida = AQUI / "resultados"
    csv_out = AQUI / "dados" / "jz" / f"rede_14_estacoes_currents_{a.ini.replace('-', '')}_{a.fim.replace('-', '')}.csv"
    csv_out.parent.mkdir(parents=True, exist_ok=True)

    src = ORIGINAL.read_text(encoding="utf-8")
    trocas = [
        ('os.path.join(BASE_DIR, "dados/magnetometros_2024")', repr(str(AQUI / "dados" / "magnetometros_2026"))),
        ('os.path.join(BASE_DIR, "resultados/graficos")', repr(str(saida))),
        ("datetime.date(2024, 1, 1)", f"datetime.date({y0}, {m0}, {d0})"),
        ("datetime.date(2024, 12, 31)", f"datetime.date({y1}, {m1}, {d1})"),
        ('.24m")', f'.{yy}m")'),
        ("start='2024-01-01', end='2024-12-31 23:59'", f"start='{a.ini}', end='{a.fim} 23:59'"),
        ('os.path.join(BASE_DIR, "dados/jz/rede_completa_14_estacoes_currents_2024.csv")', repr(str(csv_out))),
        ('"rede_completa_14_estacoes_jz_2024.png"', f'"rede_14_estacoes_jz_{a.ini}_{a.fim}.png"'),
        # arquivos Embrace de 2026 com cabecalho em latin-1 (ex.: SANTAREM com acento)
        ("open(filepath, 'r', encoding='utf-8')", "open(filepath, 'r', encoding='latin-1')"),
    ]
    for velho, novo in trocas:
        if velho not in src:
            raise SystemExit(f"trecho nao encontrado no original: {velho}")
        src = src.replace(velho, novo)
    ns = {"__name__": "__main__", "__file__": str(ORIGINAL)}
    try:
        exec(compile(src, str(ORIGINAL), "exec"), ns)
    except Exception as e:  # a figura do original tem marcos de 2024; o CSV ja foi salvo antes
        if not csv_out.exists():
            raise
        print("  aviso na figura do original:", e)

    import pandas as pd
    df = pd.read_csv(csv_out, parse_dates=["datetime"])
    df["Jz_nA_m2"] = df["Jz_pA_m2"]
    df.to_csv(csv_out, index=False)
    print("->", csv_out)


if __name__ == "__main__":
    main()
