"""
Figura: a semana anterior ao granizo de Florianopolis (29/08/2026, ~22-23 UTC).

Paineis com eixo de tempo comum e um eixo y cada (nada de eixo duplo):
  a) Kp (GFZ)                       d) raios cosmicos: Oulu e Dome C (% do nivel de 22-24/08)
  b) Dst (WDC Kyoto)                e) Jz da rede de magnetometros (metodo do pesquisador)
  c) Ey = -V x Bz (OMNI)            f) AOD 550 nm na caixa SC: total e fumaca, MERRA-2 e CAMS

Le so o que os outros scripts de clima_espacial/ ja produziram.
Uso: python clima_espacial/figura_semana_anterior.py
"""
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

AQUI = pathlib.Path(__file__).resolve().parent
RES, DAD = AQUI / "resultados", AQUI / "dados"
INI, FIM = pd.Timestamp("2026-08-22"), pd.Timestamp("2026-08-30 12:00")
GRANIZO = (pd.Timestamp("2026-08-29 22:00"), pd.Timestamp("2026-08-29 23:00"))

AZUL, LARANJA = "#2a78d6", "#eb6834"        # slots 1 e 2 da paleta validada
TINTA, TINTA2, GRADE = "#1f1f1e", "#5f5e58", "#e4e3de"


def ler():
    esp = pd.read_csv(RES / "series_espaciais_20260815_20260905.csv", index_col=0, parse_dates=True)
    nm = {}
    for st in ("OULU", "DOMC"):
        d = pd.read_csv(DAD / "neutrons" / f"{st}_h1_20260810_20260905.csv",
                        parse_dates=["Timestamp"]).set_index("Timestamp")
        d.index = d.index.tz_localize(None)
        s = d["CorrectedCountRate[cts/min]"]
        nm[st] = 100 * (s / s.loc["2026-08-22":"2026-08-24"].mean() - 1)
    jz = pd.read_csv(DAD / "jz" / "rede_14_estacoes_currents_20260801_20260910.csv",
                     parse_dates=["datetime"]).set_index("datetime")["Jz_nA_m2"]
    m2 = pd.read_csv(RES / "merra2_aod_diario_20260810_20260905.csv", index_col=0, parse_dates=True)
    cams = pd.read_csv(RES / "cams_aod_20260810_20260905.csv", index_col=0, parse_dates=True)
    cams["sc_fumaca"] = (cams["sc_omaod550"]
                         + cams["sc_bcaod550"])
    return esp, nm, jz, m2, cams


def estilo(ax, rotulo):
    ax.set_ylabel(rotulo, color=TINTA2, fontsize=9)
    ax.grid(axis="y", color=GRADE, linewidth=0.6)
    ax.grid(axis="x", visible=False)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color("#c9c8c1")
    ax.tick_params(colors=TINTA2, labelsize=8.5, length=3)
    ax.axvspan(*GRANIZO, color="#c9c8c1", alpha=0.55, lw=0, zorder=0)


def main():
    esp, nm, jz, m2, cams = ler()
    fig, axs = plt.subplots(6, 1, figsize=(10, 12.5), sharex=True,
                            gridspec_kw=dict(hspace=0.32))
    fig.patch.set_facecolor("white")
    janela = slice(INI, FIM)

    # a) Kp em barras de 3 h
    kp = esp["Kp"].loc[janela].resample("3h").first()
    axs[0].bar(kp.index + pd.Timedelta(hours=1.5), kp.values, width=0.11, color=AZUL, lw=0)
    axs[0].set_ylim(0, 6)
    estilo(axs[0], "Kp")

    # b) Dst
    axs[1].plot(esp["Dst_nT"].loc[janela], color=AZUL, lw=2)
    axs[1].axhline(0, color="#c9c8c1", lw=0.8)
    estilo(axs[1], "Dst (nT)")

    # c) Ey
    axs[2].plot(esp["Ey_mV_m"].loc[janela], color=AZUL, lw=1.6)
    axs[2].axhline(0, color="#c9c8c1", lw=0.8)
    estilo(axs[2], "Ey = −V×Bz\n(mV/m)")

    # d) raios cosmicos
    for st, cor, nome in (("OULU", AZUL, "Oulu (corte 0,8 GV)"), ("DOMC", LARANJA, "Dome C (corte ~0,1 GV)")):
        s = nm[st].loc[janela]
        axs[3].plot(s, color=cor, lw=1.6, label=nome)
        axs[3].annotate(nome.split(" (")[0], (s.index[-1], s.iloc[-1]), xytext=(4, 0),
                        textcoords="offset points", va="center", fontsize=8.5, color=TINTA)
    axs[3].axhline(0, color="#c9c8c1", lw=0.8)
    axs[3].legend(loc="lower left", bbox_to_anchor=(0, 0.98), ncol=2, fontsize=8, frameon=False)
    estilo(axs[3], "nêutrons\n(% vs 22–24/08)")

    # e) Jz (15 min)
    axs[4].plot(jz.loc[janela], color=AZUL, lw=1.1)
    axs[4].axhline(0, color="#c9c8c1", lw=0.8)
    estilo(axs[4], "Jz rede\n(nA/m²)")
    pico = jz.loc["2026-08-29 09":"2026-08-29 18"]
    axs[4].annotate(f"{pico.min():.0f} nA/m²\n(mín. do dia 29)", (pico.idxmin(), pico.min()),
                    xytext=(-78, 6), textcoords="offset points", fontsize=8.5, color=TINTA,
                    arrowprops=dict(arrowstyle="-", color=TINTA2, lw=0.8))

    # f) aerossol: cor = grandeza (total azul, fumaca laranja); traco = fonte
    for col_m2, col_cams, cor, nome in (("sc_aod_total", "sc_aod550", AZUL, "total"),
                                         ("sc_aod_fumaca", "sc_fumaca", LARANJA, "fumaça")):
        axs[5].plot(m2[col_m2].loc[janela].index + pd.Timedelta(hours=12), m2[col_m2].loc[janela],
                    color=cor, lw=2, marker="o", ms=4.5, label=f"{nome}, MERRA-2 (diário)")
        axs[5].plot(cams[col_cams].loc[janela], color=cor, lw=1.4, ls=(0, (4, 2)),
                    label=f"{nome}, CAMS (00/12 UTC)")
    axs[5].set_ylim(0, None)
    axs[5].legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    estilo(axs[5], "AOD 550 nm\ncaixa SC")

    for ax, letra in zip(axs, "abcdef"):
        ax.text(-0.085, 1.0, letra, transform=ax.transAxes, fontsize=11, fontweight="bold",
                color=TINTA, va="top")
    axs[0].text(GRANIZO[0], 6.05, "granizo", ha="right", va="bottom", fontsize=8.5, color=TINTA2)
    axs[-1].set_xlim(INI, FIM)
    axs[-1].xaxis.set_major_locator(mdates.DayLocator())
    axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    axs[-1].set_xlabel("UTC (2026)", color=TINTA2, fontsize=9)
    fig.suptitle("Semana anterior ao granizo de Florianópolis (29/08/2026)",
                 x=0.07, ha="left", y=0.94, fontsize=13, fontweight="bold", color=TINTA)
    fig.text(0.07, 0.902, "Faixa cinza: granizo, 22–23 UTC de 29/08. Jz: inversão da rede Embrace "
             "(9–10 estações). AOD: média na caixa 25,5–29,5°S / 47,5–54°W.",
             fontsize=8.5, color=TINTA2)
    out = RES / "fig_semana_anterior_granizo.png"
    fig.savefig(out, dpi=170, bbox_inches="tight")
    print("->", out)


if __name__ == "__main__":
    main()
