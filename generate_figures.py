"""
generate_figures.py - Gera figuras científicas para o tutorial de Mesoescala (FSC7116 - UFSC)
Baseado nos métodos de Kerry Emanuel (1994) e MetPy.

Regras de Integridade Científica e Tutoriais:
1. Zero números digitados à mão: todas as métricas são lidas de metpack/metricas.json.
2. Nenhuma interpretação fixada em gráfico: sem caixas/setas/faixas de "tampa", "capping lid", "inversão", "pico".
3. Fundo branco, paleta consistente e acessível a daltônicos para as 3 sondagens:
   - 12/12/1995 (Estável): Azul (#1f77b4)
   - 22/12/1995 (Neutra): Âmbar (#d97706)
   - 24/12/1995 (Instável): Vermelho (#dc2626)
4. Perfis verticais até 200 hPa:
   - Painéis θ, θe, θes com mesmos eixos.
   - N² (frequência de Brunt-Väisälä ao quadrado, mostrando N² < 0) com linha N² = 0.
   - S = -(T/θ)∂θ/∂p em K/hPa com linha S = 0.
5. Matrizes 2D de Emanuel: reversível x pseudoadiabática na mesma escala simétrica (+-15 K), com isolinha de 0 K destacada em preto espesso.
"""

import math
import os
import json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from metpy.units import units
import metpy.calc as mpcalc
from metpy.plots import SkewT, Hodograph

# Configuração global de plotagem: Fundo branco e tipografia limpa
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['axes.edgecolor'] = '#64748b'
plt.rcParams['axes.linewidth'] = 1.0

# Cores padronizadas para as três sondagens
COLOR_12 = '#1f77b4'  # Azul - 12/12 Estável
COLOR_22 = '#d97706'  # Âmbar - 22/12 Neutra
COLOR_24 = '#dc2626'  # Vermelho - 24/12 Instável
COLOR_SENS = '#7c3aed' # Roxo - 24/12 Sensibilidade

def parse_sounding_file(filepath):
    """Lê radiossondagem no formato da Universidade de Wyoming."""
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()

    parts = text.split('-----------------------------------------------------------------------------')
    if len(parts) >= 3:
        header_line = parts[1]
        lines = parts[2].split('</PRE>')[0].splitlines()
    else:
        lines = text.splitlines()
        header_line = ""

    is_speed_ms = ('m/s' in header_line) or ('SPED' in header_line)

    data = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith('</PRE>') or s.startswith('<button') or s.startswith('Station'):
            break
        p = s.split()
        if len(p) >= 11:
            try:
                sped = float(p[7])
                sknt = sped * 1.94384449 if is_speed_ms else sped
                data.append({
                    'p': float(p[0]),
                    'z': float(p[1]),
                    't': float(p[2]),
                    'td': float(p[3]),
                    'rh': float(p[4]),
                    'mixr': float(p[5]),
                    'drct': float(p[6]),
                    'sknt': sknt,
                    'thta': float(p[8]),
                    'thte': float(p[9]),
                    'thtv': float(p[10]),
                })
            except ValueError:
                continue
        elif len(p) >= 9:
            try:
                data.append({
                    'p': float(p[0]),
                    'z': float(p[1]),
                    't': float(p[2]),
                    'td': float(p[3]),
                    'rh': float(p[4]),
                    'mixr': float(p[5]),
                    'drct': np.nan,
                    'sknt': np.nan,
                    'thta': float(p[6]),
                    'thte': float(p[7]),
                    'thtv': float(p[8]),
                })
            except ValueError:
                continue

    df = pd.DataFrame(data).dropna(subset=['p', 'z', 't', 'td'])
    df['drct'] = df['drct'].interpolate().ffill().bfill()
    df['sknt'] = df['sknt'].interpolate().ffill().bfill()
    return df.drop_duplicates(subset=['p']).sort_values('p', ascending=False).reset_index(drop=True)

def load_metrics():
    """Carrega o arquivo mestre de métricas calculadas."""
    with open('metpack/metricas.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# ==============================================================================
# 1. DIAGNÓSTICO INDIVIDUAL DE SKEW-T POR SONDAGEM (COM PARCELA E LCL/LFC/EL)
# ==============================================================================
def generate_individual_skewt(metrics):
    """Gera um diagrama Skew-T de alta resolução individual para cada sondagem."""
    cases = [
        {
            'date': '19951212',
            'm_key': '19951212',
            'title': 'Radiossondagem SBPA — 12/12/1995 12Z (Atmosfera Estável)',
            'color': COLOR_12,
            'out_fig': 'metpack/fig_sounding_1_estavel.png'
        },
        {
            'date': '19951222',
            'm_key': '19951222',
            'title': 'Radiossondagem SBPA — 22/12/1995 12Z (Atmosfera Neutra)',
            'color': COLOR_22,
            'out_fig': 'metpack/fig_sounding_2_neutra.png'
        },
        {
            'date': '19951224',
            'm_key': '19951224_raw',
            'title': 'Radiossondagem SBPA — 24/12/1995 12Z (Atmosfera Instável)',
            'color': COLOR_24,
            'out_fig': 'metpack/fig_sounding_3_instavel.png'
        }
    ]

    for c in cases:
        df = parse_sounding_file(f"metpack/sounding_{c['date']}_12Z.txt")
        if df is None:
            continue

        p = df['p'].values * units.hPa
        T = df['t'].values * units.degC
        Td = df['td'].values * units.degC
        u, v = mpcalc.wind_components(df['sknt'].values * units.knot, df['drct'].values * units.deg)

        m = metrics[c['m_key']]

        # Layout Profissional em Largura Dupla: Skew-T a Esquerda, Hodografo e Indices a Direita
        fig = plt.figure(figsize=(16.5, 10.0), dpi=160)
        rect_skew = [0.06, 0.08, 0.53, 0.84]
        skew = SkewT(fig, rotation=45, rect=rect_skew)

        # Plotagem dos dados observados
        skew.plot(p, T, color='#dc2626', linewidth=2.4, label='Temperatura T (°C)')
        skew.plot(p, Td, color='#16a34a', linewidth=2.4, label='Ponto de Orvalho Td (°C)')

        # Barbelas de vento
        mask_wind = p >= 150 * units.hPa
        skew.plot_barbs(p[mask_wind][::2], u[mask_wind][::2], v[mask_wind][::2], length=6.5, color='#334155')

        # Linhas de referência termodinâmica
        skew.plot_dry_adiabats(t0=np.arange(250, 440, 20) * units.kelvin, alpha=0.28, color='#94a3b8', linewidth=0.85)
        skew.plot_moist_adiabats(t0=np.arange(270, 320, 10) * units.kelvin, alpha=0.28, color='#60a5fa', linewidth=0.85)
        skew.plot_mixing_lines(alpha=0.28, color='#10b981', linewidth=0.85)

        # Trajetória da parcela de superfície
        try:
            prof_sb = mpcalc.parcel_profile(p, T[0], Td[0]).to('degC')
            skew.plot(p, prof_sb, color='#0f172a', linestyle='--', linewidth=2.0, label='Parcela Superfície (SB)')
            skew.shade_cape(p, T, prof_sb, facecolor='#ef4444', alpha=0.25, label='CAPE')
            skew.shade_cin(p, T, prof_sb, facecolor='#3b82f6', alpha=0.25, label='CIN')
        except Exception:
            pass

        # Níveis característicos (LCL, LFC, EL) com prevenção de sobreposição
        lcl_p = m.get('lcl_p_hPa')
        lfc_p = m.get('lfc_p_hPa')
        el_p = m.get('el_p_hPa')

        levels_to_plot = []
        if lcl_p:
            skew.ax.axhline(lcl_p, color='#0284c7', linestyle=':', linewidth=1.4)
            levels_to_plot.append(('LCL', lcl_p, '#0284c7'))
        if lfc_p:
            skew.ax.axhline(lfc_p, color='#b45309', linestyle=':', linewidth=1.4)
            levels_to_plot.append(('LFC', lfc_p, '#b45309'))
        if el_p:
            skew.ax.axhline(el_p, color='#7c3aed', linestyle=':', linewidth=1.4)
            levels_to_plot.append(('EL', el_p, '#7c3aed'))

        # Ordenar por pressão decrescente para tratar sobreposições na vertical
        levels_to_plot.sort(key=lambda item: item[1], reverse=True)
        prev_p = 9999
        for name, p_val, col in levels_to_plot:
            va = 'bottom' if (prev_p - p_val) >= 28 else 'top'
            skew.ax.text(0.02, p_val, f"{name}: {p_val:.0f} hPa", color=col, fontsize=10.0,
                         fontweight='bold', va=va, transform=skew.ax.get_yaxis_transform(),
                         bbox=dict(boxstyle='round,pad=0.22', facecolor='white', alpha=0.9, edgecolor=col, linewidth=0.9))
            prev_p = p_val

        skew.ax.set_ylim(1050, 100)
        skew.ax.set_xlim(-40, 45)
        skew.ax.set_xlabel('Temperatura (°C)', fontsize=12.5, fontweight='bold')
        skew.ax.set_ylabel('Pressão (hPa)', fontsize=12.5, fontweight='bold')
        skew.ax.legend(loc='upper right', fontsize=10.0, framealpha=0.92)

        fig.suptitle(c['title'], fontsize=14.5, fontweight='bold', y=0.965, color='#0f172a')

        # ----------------------------------------------------------------------
        # LADO DIREITO SUPERIOR: HODÓGRAFO POLAR DE MESOESCALA
        # ----------------------------------------------------------------------
        ax_hodo = fig.add_axes([0.64, 0.52, 0.33, 0.40])
        h = Hodograph(ax_hodo, component_range=40.)
        h.add_grid(increment=10, color='#cbd5e1', linewidth=0.85)

        z = df['z'].values * units.meter
        z_agl = (z - z[0])
        h.plot_colormapped(u[mask_wind], v[mask_wind], z_agl[mask_wind],
                           intervals=[0, 1000, 3000, 6000, 12000] * units.meter,
                           colors=['#dc2626', '#16a34a', '#2563eb', '#64748b'])

        # Bunkers Left-Mover (Hemisfério Sul)
        lm_u = m.get('bunkers_lm_u_ms')
        lm_v = m.get('bunkers_lm_v_ms')
        if lm_u is not None and lm_v is not None:
            lm_u_kt = lm_u * 1.94384449
            lm_v_kt = lm_v * 1.94384449
            ax_hodo.plot(lm_u_kt, lm_v_kt, marker='d', markersize=9, color='#d97706',
                         markeredgecolor='#0f172a', label='Bunkers LM (HS)')
            ax_hodo.legend(loc='lower left', fontsize=9.5, framealpha=0.92)

        ax_hodo.set_title('Hodógrafo Polar de Vento Horizontal (kt)', fontsize=12.5, fontweight='bold', color='#1e293b', pad=8)

        # ----------------------------------------------------------------------
        # LADO DIREITO INFERIOR: PAINEL DIAGNÓSTICO DE ÍNDICES (FONTE GRANDE)
        # ----------------------------------------------------------------------
        ax_params = fig.add_axes([0.63, 0.07, 0.35, 0.41])
        ax_params.axis('off')

        # Caixa de fundo estilizada
        from matplotlib.patches import FancyBboxPatch
        box = FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.03,rounding_size=0.03",
                             facecolor="#f8fafc", edgecolor="#94a3b8", linewidth=1.5,
                             transform=ax_params.transAxes)
        ax_params.add_patch(box)

        # Cabeçalho do Painel
        ax_params.text(0.05, 0.93, "PARÂMETROS DIAGNÓSTICOS (MetPy)",
                       fontsize=12, fontweight='bold', color='#0f172a', transform=ax_params.transAxes)
        ax_params.plot([0.05, 0.95], [0.89, 0.89], color='#cbd5e1', linewidth=1.3, transform=ax_params.transAxes)

        # Formatação clara dos dados
        lfc_str = f"{m.get('lfc_p_hPa'):.0f} hPa" if m.get('lfc_p_hPa') is not None else "N/A"
        el_str = f"{m.get('el_p_hPa'):.0f} hPa" if m.get('el_p_hPa') is not None else "N/A"
        k_str = f"{m.get('k_index_C', 0):.1f}°C" if m.get('k_index_C') is not None else "N/A"
        tt_str = f"{m.get('total_totals_C', 0):.1f} K" if m.get('total_totals_C') is not None else "N/A"
        sh_str = f"{m.get('showalter_K', 0):.1f} K" if m.get('showalter_K') is not None else "N/A"
        sw_str = f"{m.get('sweat_index', 0):.1f}" if m.get('sweat_index') is not None else "N/A"
        li_str = f"{m.get('lifted_index_K', 0):.1f} K" if m.get('lifted_index_K') is not None else "N/A"
        dc_em = m.get('emanuel', {}).get('max_dcape_emanuel_Jkg', 0.0) if isinstance(m.get('emanuel'), dict) else 0.0
        dc_metpy = f"{m.get('dcape_metpy_Jkg', 0):.0f} J/kg" if m.get('dcape_metpy_Jkg') is not None else "N/A"

        p_lines = [
            ("Água Precipitável (PW):", f"{m.get('pw_mm', 0):.1f} mm"),
            ("MUCAPE / MUCIN:", f"{m.get('mucape_Jkg', 0):.0f} / {m.get('mucin_Jkg', 0):.0f} J/kg"),
            ("SBCAPE / SBCIN:", f"{m.get('sbcape_Jkg', 0):.0f} / {m.get('sbcin_Jkg', 0):.0f} J/kg"),
            ("LCL (Pressão / Temp.):", f"{m.get('lcl_p_hPa', 0):.0f} hPa ({m.get('lcl_t_C', 0):.1f}°C)"),
            ("LFC / EL:", f"{lfc_str} / {el_str}"),
            ("K-Index / Total Totals:", f"{k_str} / {tt_str}"),
            ("Showalter / SWEAT:", f"{sh_str} / {sw_str}"),
            ("Lifted Index (LI):", f"{li_str}"),
            ("Bulk Shear 0-6 km:", f"{m.get('bulk_shear_0_6km_ms', 0):.1f} m/s ({m.get('bulk_shear_0_6km_kt', 0):.1f} kt)"),
            ("SRH 0-3 km (Left-Mover):", f"{m.get('srh_0_3km_lm_m2s2', 0):.1f} m²/s²"),
            ("Bunkers LM (Vetor):", f"{m.get('bunkers_lm_dir_deg', 0):.0f}° / {m.get('bunkers_lm_spd_kt', 0):.1f} kt"),
            ("DCAPE (MetPy / Emanuel):", f"{dc_metpy} / {dc_em:.1f} J/kg")
        ]

        y_pos = 0.83
        for label_text, val_text in p_lines:
            ax_params.text(0.05, y_pos, label_text, fontsize=11, fontweight='bold', color='#334155',
                           transform=ax_params.transAxes, va='center')
            ax_params.text(0.95, y_pos, val_text, fontsize=11, fontweight='bold', family='monospace',
                           color='#0f172a', transform=ax_params.transAxes, va='center', ha='right')
            y_pos -= 0.065

        plt.savefig(c['out_fig'], dpi=160, bbox_inches='tight')
        if c['date'] == '19951224':
            plt.savefig('metpack/fig_colab_severe_skewt.png', dpi=160, bbox_inches='tight')
        plt.close()
        print(f"Saved Skew-T: {c['out_fig']}")

# ==============================================================================
# 2. COMPARAÇÃO TRÍPLICE DE SKEW-T (PAINEL 3-EM-1)
# ==============================================================================
def generate_tripartite_skewt_panel(metrics):
    """Gera o painel 3-em-1 comparando os Skew-T lado a lado."""
    fig = plt.figure(figsize=(18, 7.5), dpi=150)
    cases_trip = [
        ('sounding_20260826_12Z.txt', '26/08/2026 12Z (Estável)', '20260826'),
        ('sounding_20260831_00Z.txt', '31/08/2026 00Z (Neutra)', '20260831'),
        ('sounding_20260828_12Z.txt', '28/08/2026 12Z (Instável — Granizo Gigante)', '20260828_raw')
    ]

    for i, (fname, title, m_key) in enumerate(cases_trip):
        df = parse_sounding_file(f"metpack/{fname}")
        if df is None:
            continue
        p = df['p'].values * units.hPa
        T = df['t'].values * units.degC
        Td = df['td'].values * units.degC
        u, v = mpcalc.wind_components(df['sknt'].values * units.knot, df['drct'].values * units.deg)

        skew = SkewT(fig, rotation=45, subplot=(1, 3, i + 1))
        skew.plot(p, T, color='#dc2626', linewidth=1.8, label='T')
        skew.plot(p, Td, color='#16a34a', linewidth=1.8, label='Td')

        mask_wind = p >= 150 * units.hPa
        skew.plot_barbs(p[mask_wind][::3], u[mask_wind][::3], v[mask_wind][::3], length=5.5, color='#475569')

        skew.plot_dry_adiabats(t0=np.arange(250, 440, 25) * units.kelvin, alpha=0.25, color='#94a3b8', linewidth=0.7)
        skew.plot_moist_adiabats(t0=np.arange(270, 320, 10) * units.kelvin, alpha=0.25, color='#60a5fa', linewidth=0.7)

        try:
            prof = mpcalc.parcel_profile(p, T[0], Td[0]).to('degC')
            skew.plot(p, prof, color='#0f172a', linestyle='--', linewidth=1.4)
            skew.shade_cape(p, T, prof, facecolor='#ef4444', alpha=0.2)
        except Exception:
            pass

        m = metrics[m_key]
        cap_val = m.get('sbcape_Jkg', 0)
        pw_val = m.get('pw_mm', 0)

        skew.ax.set_ylim(1050, 100)
        skew.ax.set_xlim(-40, 45)
        skew.ax.set_xlabel('Temperatura (°C)', fontsize=10, fontweight='bold')
        if i == 0:
            skew.ax.set_ylabel('Pressão (hPa)', fontsize=10, fontweight='bold')
        else:
            skew.ax.set_ylabel('')
        skew.ax.set_title(f"{title}\nSBCAPE = {cap_val:.0f} J/kg | PW = {pw_val:.1f} mm", fontsize=10.5, fontweight='bold')
        skew.ax.legend(loc='upper right', fontsize=8)

    plt.tight_layout()
    plt.savefig('metpack/fig_3_soundings_complete_analysis.png', dpi=160, bbox_inches='tight')
    plt.close()
    print("Saved tripartite Skew-T comparison: metpack/fig_3_soundings_complete_analysis.png")

# ==============================================================================
# 3. PERFIS DE THETA, THETA-E, THETA-ES (3 PAINÉIS, MESMOS EIXOS, TOPO EM 200 hPa)
# ==============================================================================
def generate_perfis_theta_triplice(metrics):
    """
    Gera a figura com 3 painéis de θ, θe e θes (um por sondagem)
    com estritamente os mesmos eixos e topo em 200 hPa.
    """
    cases = [
        ('19951212', '12/12/1995 12Z (Estável)', COLOR_12),
        ('19951222', '22/12/1995 12Z (Neutra)', COLOR_22),
        ('19951224', '24/12/1995 12Z (Instável)', COLOR_24)
    ]

    fig, axes = plt.subplots(1, 3, figsize=(16, 7), dpi=150)
    fig.suptitle("Perfis de Temperatura Potencial: θ (Seca), θe (Equivalente) e θes (Saturação)\nComparação dos Três Regimes Troposféricos (Superfície até 200 hPa)",
                 fontsize=13, fontweight='bold', color='#0f172a', y=0.98)

    yticks = [1000, 925, 850, 700, 600, 500, 400, 300, 200]

    for i, (date, label, c_border) in enumerate(cases):
        ax = axes[i]
        df = parse_sounding_file(f"metpack/sounding_{date}_12Z.txt")
        if df is None:
            continue

        p = df['p'].values * units.hPa
        T = df['t'].values * units.degC
        Td = df['td'].values * units.degC

        theta = mpcalc.potential_temperature(p, T).to('kelvin')
        theta_e = mpcalc.equivalent_potential_temperature(p, T, Td).to('kelvin')
        theta_es = mpcalc.saturation_equivalent_potential_temperature(p, T).to('kelvin')

        # Filtro até 200 hPa
        mask = p >= 195 * units.hPa
        p_m = p[mask].magnitude
        th_m = theta[mask].magnitude
        the_m = theta_e[mask].magnitude
        thes_m = theta_es[mask].magnitude

        ax.plot(th_m, p_m, color='#1e3a8a', linewidth=2.0, label='θ (Potencial)')
        ax.plot(the_m, p_m, color='#16a34a', linewidth=2.2, label='θe (Equivalente)')
        ax.plot(thes_m, p_m, color='#dc2626', linestyle='--', linewidth=2.0, label='θes (Saturação)')

        ax.set_ylim(1050, 200)
        ax.set_yscale('log')
        ax.set_yticks(yticks)
        ax.set_yticklabels([str(y) for y in yticks])
        ax.set_xlim(275, 395)
        ax.set_xlabel('Temperatura (K)', fontsize=10.5, fontweight='bold')
        if i == 0:
            ax.set_ylabel('Pressão (hPa)', fontsize=10.5, fontweight='bold')
        else:
            ax.set_ylabel('')

        ax.set_title(label, fontsize=11, fontweight='bold', color='#0f172a')
        ax.legend(loc='upper right', fontsize=8.5, framealpha=0.95)
        ax.grid(True, linestyle=':', alpha=0.6, color='#94a3b8')

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    out_fig = 'metpack/fig_perfis_theta_triplice.png'
    plt.savefig(out_fig, dpi=160, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_fig}")

# ==============================================================================
# 4. COMPARAÇÃO TRÍPLICE DE ESTABILIDADE: θe, N², S = -(T/θ)∂θ/∂p E r (TOPO 200 hPa)
# ==============================================================================
def generate_3_soundings_profiles_comparison(metrics):
    """
    Gera a figura de comparação tríplice vertical com:
    - Painel 1: θe (K)
    - Painel 2: N² (frequência de Brunt-Väisälä ao quadrado, ×10⁻⁴ s⁻²)
    - Painel 3: Estabilidade Estática S = -(T/θ)∂θ/∂p em K/hPa
    - Painel 4: Razão de mistura r (g/kg)
    Topo padronizado em 200 hPa, fundo branco e mesma paleta de cores.
    """
    cases = [
        ('19951212', '12/12/1995 (Estável)', COLOR_12, '-'),
        ('19951222', '22/12/1995 (Neutra)', COLOR_22, '--'),
        ('19951224', '24/12/1995 (Instável)', COLOR_24, '-')
    ]

    fig, axes = plt.subplots(1, 4, figsize=(18, 7.5), dpi=150)
    fig.suptitle("Diagnóstico Comparativo Vertical de Estabilidade Troposférica (Superfície até 200 hPa)\nSBPA Porto Alegre: Estável (12/12/1995), Neutra (22/12/1995) e Instável (24/12/1995)",
                 fontsize=13, fontweight='bold', color='#0f172a', y=0.98)

    yticks = [1000, 925, 850, 700, 600, 500, 400, 300, 200]

    for date, label, color, ls in cases:
        df = parse_sounding_file(f"metpack/sounding_{date}_12Z.txt")
        if df is None:
            continue

        p = df['p'].values * units.hPa
        T = df['t'].values * units.degC
        Td = df['td'].values * units.degC
        z = df['z'].values * units.meter

        theta = mpcalc.potential_temperature(p, T).to('kelvin')
        theta_e = mpcalc.equivalent_potential_temperature(p, T, Td).to('kelvin')
        rh = mpcalc.relative_humidity_from_dewpoint(T, Td)
        mixrat = mpcalc.mixing_ratio_from_relative_humidity(p, T, rh).to('g/kg')

        # N² = Brunt-Väisälä ao quadrado (s⁻²)
        N2 = mpcalc.brunt_vaisala_frequency_squared(z, theta)
        n2_vals = N2.to('1/s^2').magnitude * 1e4  # em 10⁻⁴ s⁻²

        # S = -(T/θ) * ∂θ/∂p em K/hPa
        p_hpa = p.to('hPa').magnitude
        T_K = T.to('kelvin').magnitude
        theta_K = theta.to('kelvin').magnitude
        dtheta_dp = np.gradient(theta_K, p_hpa)
        S_K_per_hPa = - (T_K / theta_K) * dtheta_dp

        # Filtro até 200 hPa
        mask = p >= 195 * units.hPa
        p_m = p_hpa[mask]
        the_m = theta_e[mask].magnitude
        n2_m = n2_vals[mask]
        s_m = S_K_per_hPa[mask]
        r_m = mixrat[mask].magnitude

        # 1. Painel θe
        axes[0].plot(the_m, p_m, color=color, linestyle=ls, linewidth=2.2, label=label)

        # 2. Painel N²
        axes[1].plot(n2_m, p_m, color=color, linestyle=ls, linewidth=2.0, label=label)

        # 3. Painel S
        axes[2].plot(s_m, p_m, color=color, linestyle=ls, linewidth=2.0, label=label)

        # 4. Painel r
        axes[3].plot(r_m, p_m, color=color, linestyle=ls, linewidth=2.2, label=label)

    # Configuração dos eixos
    titles = [
        "Temp. Potencial Equivalente\nθe (K)",
        "Freq. Brunt-Väisälä ao Quadrado\nN² (×10⁻⁴ s⁻²)",
        "Estabilidade Estática\nS = −(T/θ)∂θ/∂p (K/hPa)",
        "Razão de Mistura de Vapor\nr (g/kg)"
    ]
    xlabels = [
        "θe (K)",
        "N² (×10⁻⁴ s⁻²)",
        "S (K/hPa)",
        "r (g/kg)"
    ]
    xlims = [
        (305, 385),
        (-2.0, 6.0),
        (-0.05, 0.25),
        (0.0, 24.0)
    ]

    for i, ax in enumerate(axes):
        ax.set_ylim(1050, 200)
        ax.set_yscale('log')
        ax.set_yticks(yticks)
        ax.set_yticklabels([str(y) for y in yticks])
        ax.set_xlabel(xlabels[i], fontsize=10.5, fontweight='bold')
        if i == 0:
            ax.set_ylabel('Pressão (hPa)', fontsize=10.5, fontweight='bold')
        else:
            ax.set_ylabel('')

        ax.set_xlim(xlims[i])
        ax.set_title(title, fontsize=10.5, fontweight='bold')
        ax.legend(loc='upper right', fontsize=8.5, framealpha=0.92)
        ax.grid(True, linestyle=':', alpha=0.6, color='#94a3b8')

        # Linhas de referência física zero em N² e S
        if i == 1 or i == 2:
            ax.axvline(0.0, color='#64748b', linestyle='--', linewidth=1.1, label='Limite Neutro (0)')

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    out_fig = 'metpack/fig_3_soundings_profiles_comparison.png'
    plt.savefig(out_fig, dpi=160, bbox_inches='tight')
    plt.close()
    print(f"Saved tripartite profiles comparison: {out_fig}")

# ==============================================================================
# 5. PERFIS DO CAPÍTULO 2 DE EMANUEL (SBPA 24/12/1995 12Z)
# ==============================================================================
def generate_cap2_thermo_profiles(metrics):
    """Gera perfis termodinâmicos do Cap. 2 de Emanuel com topo em 200 hPa e fundo branco."""
    df = parse_sounding_file('metpack/sounding_20260828_12Z.txt')
    if df is None:
        return

    p = df['p'].values * units.hPa
    z = df['z'].values * units.meter
    T = df['t'].values * units.degC
    Td = df['td'].values * units.degC

    theta = mpcalc.potential_temperature(p, T).to('kelvin')
    theta_e = mpcalc.equivalent_potential_temperature(p, T, Td).to('kelvin')
    theta_es = mpcalc.saturation_equivalent_potential_temperature(p, T).to('kelvin')
    rh = mpcalc.relative_humidity_from_dewpoint(T, Td)
    mixr = mpcalc.mixing_ratio_from_relative_humidity(p, T, rh).to('g/kg').magnitude

    N2 = mpcalc.brunt_vaisala_frequency_squared(z, theta)
    n2_vals = N2.to('1/s^2').magnitude * 1e4

    p_hpa = p.to('hPa').magnitude
    T_K = T.to('kelvin').magnitude
    theta_K = theta.to('kelvin').magnitude
    dtheta_dp = np.gradient(theta_K, p_hpa)
    S_K_per_hPa = - (T_K / theta_K) * dtheta_dp

    # Filtro até 200 hPa
    mask = p >= 195 * units.hPa
    p_m = p_hpa[mask]

    fig, axes = plt.subplots(1, 4, figsize=(18, 7.5), dpi=150)
    fig.suptitle("Perfis Verticais de Estabilidade Termodinâmica (Emanuel 1994, Cap. 2)\nSBFL Florianópolis (83899) — 28/08/2026 12Z (Granizo Gigante) (Superfície até 200 hPa)", 
                 fontsize=13, fontweight='bold', color='#0f172a', y=0.98)

    yticks = [1000, 925, 850, 700, 600, 500, 400, 300, 200]

    # Painel 1: θ, θe, θes
    axes[0].plot(theta[mask].magnitude, p_m, color='#1e3a8a', linewidth=2.0, label='θ (Potencial)')
    axes[0].plot(theta_e[mask].magnitude, p_m, color='#16a34a', linewidth=2.2, label='θe (Equivalente)')
    axes[0].plot(theta_es[mask].magnitude, p_m, color='#dc2626', linestyle='--', linewidth=2.0, label='θes (Saturação)')
    axes[0].set_xlim(285, 390)
    axes[0].set_xlabel('Temperatura (K)', fontsize=10.5, fontweight='bold')
    axes[0].set_ylabel('Pressão (hPa)', fontsize=10.5, fontweight='bold')
    axes[0].set_title("Perfis de θ, θe e θes", fontsize=11, fontweight='bold')
    axes[0].legend(loc='upper right', fontsize=8.5)

    # Painel 2: N²
    axes[1].plot(n2_vals[mask], p_m, color='#7c3aed', linewidth=2.0, label='N²')
    axes[1].axvline(0.0, color='#64748b', linestyle='--', linewidth=1.0)
    axes[1].set_xlim(-2.0, 5.0)
    axes[1].set_xlabel('N² (×10⁻⁴ s⁻²)', fontsize=10.5, fontweight='bold')
    axes[1].set_title("Freq. Brunt-Väisälä ao Quadrado (N²)", fontsize=11, fontweight='bold')
    axes[1].legend(loc='upper right', fontsize=8.5)

    # Painel 3: S
    axes[2].plot(S_K_per_hPa[mask], p_m, color='#ea580c', linewidth=2.0, label='S')
    axes[2].axvline(0.0, color='#64748b', linestyle='--', linewidth=1.0)
    axes[2].set_xlim(-0.05, 0.25)
    axes[2].set_xlabel('S (K/hPa)', fontsize=10.5, fontweight='bold')
    axes[2].set_title("Estabilidade Estática S = −(T/θ)∂θ/∂p", fontsize=11, fontweight='bold')
    axes[2].legend(loc='upper right', fontsize=8.5)

    # Painel 4: r e PW
    m24 = metrics.get('19951224_raw', {})
    pw_val = m24.get('pw_mm', 0.0)
    axes[3].plot(mixr[mask], p_m, color='#0d9488', linewidth=2.2, label=f'r (g/kg)\nPW = {pw_val:.1f} mm')
    axes[3].fill_betweenx(p_m, 0, mixr[mask], color='#99f6e4', alpha=0.35)
    axes[3].set_xlim(0, 24)
    axes[3].set_xlabel('Razão de Mistura r (g/kg)', fontsize=10.5, fontweight='bold')
    axes[3].set_title("Umidade Específica r(p)", fontsize=11, fontweight='bold')
    axes[3].legend(loc='upper right', fontsize=8.5)

    for ax in axes:
        ax.set_ylim(1050, 200)
        ax.set_yscale('log')
        ax.set_yticks(yticks)
        ax.set_yticklabels([str(y) for y in yticks])
        ax.grid(True, linestyle=':', alpha=0.6, color='#94a3b8')

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    out_fig = 'metpack/fig_cap2_profiles.png'
    plt.savefig(out_fig, dpi=160, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_fig}")

# ==============================================================================
# 6. PERFIS INDIVIDUAIS PARA TODAS AS 3 SONDAGENS
# ==============================================================================
def generate_all_soundings_colab_profiles(metrics):
    """Gera o quarteto de perfis individuais para cada uma das 3 sondagens."""
    cases = [
        ('19951212', '12/12/1995 12Z (Estável)', 'metpack/fig_profiles_19951212.png', '19951212'),
        ('19951222', '22/12/1995 12Z (Neutra)', 'metpack/fig_profiles_19951222.png', '19951222'),
        ('19951224', '24/12/1995 12Z (Instável)', 'metpack/fig_profiles_19951224.png', '19951224_raw')
    ]

    yticks = [1000, 925, 850, 700, 600, 500, 400, 300, 200]

    for date, label, out_fig, m_key in cases:
        df = parse_sounding_file(f"metpack/sounding_{date}_12Z.txt")
        if df is None:
            continue

        p = df['p'].values * units.hPa
        z = df['z'].values * units.meter
        T = df['t'].values * units.degC
        Td = df['td'].values * units.degC

        theta = mpcalc.potential_temperature(p, T).to('kelvin')
        theta_e = mpcalc.equivalent_potential_temperature(p, T, Td).to('kelvin')
        theta_es = mpcalc.saturation_equivalent_potential_temperature(p, T).to('kelvin')
        rh = mpcalc.relative_humidity_from_dewpoint(T, Td)
        mixr = mpcalc.mixing_ratio_from_relative_humidity(p, T, rh).to('g/kg').magnitude

        N2 = mpcalc.brunt_vaisala_frequency_squared(z, theta)
        n2_vals = N2.to('1/s^2').magnitude * 1e4

        p_hpa = p.to('hPa').magnitude
        T_K = T.to('kelvin').magnitude
        theta_K = theta.to('kelvin').magnitude
        dtheta_dp = np.gradient(theta_K, p_hpa)
        S_K_per_hPa = - (T_K / theta_K) * dtheta_dp

        mask = p >= 195 * units.hPa
        p_m = p_hpa[mask]

        fig, axes = plt.subplots(1, 4, figsize=(18, 7.5), dpi=150)
        fig.suptitle(f"Perfis Verticais de Estabilidade — SBPA {label} (Superfície até 200 hPa)",
                     fontsize=13, fontweight='bold', color='#0f172a', y=0.98)

        # 1. θ, θe, θes
        axes[0].plot(theta[mask].magnitude, p_m, color='#1e3a8a', linewidth=2.0, label='θ')
        axes[0].plot(theta_e[mask].magnitude, p_m, color='#16a34a', linewidth=2.2, label='θe')
        axes[0].plot(theta_es[mask].magnitude, p_m, color='#dc2626', linestyle='--', linewidth=2.0, label='θes')
        axes[0].set_xlim(275, 395)
        axes[0].set_xlabel('Temperatura (K)', fontsize=10.5, fontweight='bold')
        axes[0].set_ylabel('Pressão (hPa)', fontsize=10.5, fontweight='bold')
        axes[0].set_title("θ, θe e θes", fontsize=11, fontweight='bold')
        axes[0].legend(loc='upper right', fontsize=8.5)

        # 2. N²
        axes[1].plot(n2_vals[mask], p_m, color='#7c3aed', linewidth=2.0, label='N²')
        axes[1].axvline(0.0, color='#64748b', linestyle='--', linewidth=1.0)
        axes[1].set_xlim(-2.0, 6.0)
        axes[1].set_xlabel('N² (×10⁻⁴ s⁻²)', fontsize=10.5, fontweight='bold')
        axes[1].set_title("Brunt-Väisälä (N²)", fontsize=11, fontweight='bold')
        axes[1].legend(loc='upper right', fontsize=8.5)

        # 3. S
        axes[2].plot(S_K_per_hPa[mask], p_m, color='#ea580c', linewidth=2.0, label='S')
        axes[2].axvline(0.0, color='#64748b', linestyle='--', linewidth=1.0)
        axes[2].set_xlim(-0.05, 0.25)
        axes[2].set_xlabel('S (K/hPa)', fontsize=10.5, fontweight='bold')
        axes[2].set_title("Estabilidade S = −(T/θ)∂θ/∂p", fontsize=11, fontweight='bold')
        axes[2].legend(loc='upper right', fontsize=8.5)

        # 4. r
        m = metrics.get(m_key, {})
        pw_val = m.get('pw_mm', 0.0)
        axes[3].plot(mixr[mask], p_m, color='#0d9488', linewidth=2.2, label=f'r (g/kg)\nPW = {pw_val:.1f} mm')
        axes[3].fill_betweenx(p_m, 0, mixr[mask], color='#99f6e4', alpha=0.35)
        axes[3].set_xlim(0, 24)
        axes[3].set_xlabel('Razão de Mistura r (g/kg)', fontsize=10.5, fontweight='bold')
        axes[3].set_title("Umidade Específica r(p)", fontsize=11, fontweight='bold')
        axes[3].legend(loc='upper right', fontsize=8.5)

        for ax in axes:
            ax.set_ylim(1050, 200)
            ax.set_yscale('log')
            ax.set_yticks(yticks)
            ax.set_yticklabels([str(y) for y in yticks])
            ax.grid(True, linestyle=':', alpha=0.6, color='#94a3b8')

        plt.tight_layout(rect=[0, 0, 1, 0.94])
        plt.savefig(out_fig, dpi=160, bbox_inches='tight')
        plt.close()
        print(f"Saved: {out_fig}")

# ==============================================================================
# 7. HODÓGRAFO CINEMÁTICO (HEMISFÉRIO SUL - BUNKERS LEFT-MOVER)
# ==============================================================================
def generate_kinematics_hodograph(metrics):
    """Gera o hodógrafo com convenções do Hemisfério Sul, fundo branco e sem anotações manuais."""
    df = parse_sounding_file('metpack/sounding_20260828_12Z.txt')
    if df is None:
        return

    m = metrics.get('20260828_raw', metrics.get('19951224_raw', {}))
    p = df['p'].values * units.hPa
    u, v = mpcalc.wind_components(df['sknt'].values * units.knot, df['drct'].values * units.deg)
    z = df['z'].values * units.meter

    mask = p >= 100 * units.hPa
    p_f = p[mask]
    u_f = u[mask].to('meter / second').magnitude
    v_f = v[mask].to('meter / second').magnitude
    z_km = (z[mask] - z[mask][0]).to('km').magnitude

    fig, ax = plt.subplots(figsize=(9, 9), dpi=150)
    circles = [5, 10, 15, 20, 25, 30, 35, 40]
    for c in circles:
        circle = plt.Circle((0, 0), c, color='#cbd5e1', fill=False, linestyle='--', linewidth=0.8)
        ax.add_patch(circle)
        ax.text(c * 0.707, c * 0.707, f"{c} m/s", color='#94a3b8', fontsize=8, ha='center', va='center')

    ax.axhline(0, color='#94a3b8', linestyle='-', linewidth=0.8)
    ax.axvline(0, color='#94a3b8', linestyle='-', linewidth=0.8)

    # Segmentos de camada vertical
    m01 = z_km <= 1.05
    ax.plot(u_f[m01], v_f[m01], color='#ef4444', linewidth=3.8, label='0 - 1 km (Baixos Níveis)')
    m13 = (z_km >= 0.95) & (z_km <= 3.1)
    ax.plot(u_f[m13], v_f[m13], color='#10b981', linewidth=3.2, label='1 - 3 km (Camada de SRH)')
    m36 = (z_km >= 2.9) & (z_km <= 6.2)
    ax.plot(u_f[m36], v_f[m36], color='#0284c7', linewidth=2.8, label='3 - 6 km (Cisalhamento Profundo)')
    m6p = z_km >= 5.9
    ax.plot(u_f[m6p], v_f[m6p], color='#8b5cf6', linewidth=2.2, label='> 6 km (Alta Troposfera)')

    # Pontos de níveis de pressão padrão
    for i in range(len(p_f)):
        p_val = p_f[i].magnitude
        if p_val in [1009, 970, 925, 850, 700, 500, 300, 200]:
            ax.plot(u_f[i], v_f[i], 'o', color='#0f172a', markersize=5.5)
            ax.text(u_f[i] + 0.8, v_f[i] + 0.4, f"{p_val:.0f} hPa", fontsize=8, color='#0f172a')

    # Vetor Bunkers Left-Mover (ciclônico no Hemisfério Sul)
    lm_u = m.get('bunkers_lm_u_ms', 0.0)
    lm_v = m.get('bunkers_lm_v_ms', 0.0)
    lm_spd_kt = m.get('bunkers_lm_spd_kt', 0.0)
    lm_dir = m.get('bunkers_lm_dir_deg', 0.0)
    ax.plot(lm_u, lm_v, 'D', color='#f59e0b', markersize=9, 
            label=f'Bunkers Left-Mover ({lm_u:.1f}, {lm_v:.1f}) m/s [{lm_spd_kt:.1f} kt de {lm_dir:.0f}°]')
    # Vetor Bunkers Right-Mover
    rm_u = m.get('bunkers_rm_u_ms', 0.0)
    rm_v = m.get('bunkers_rm_v_ms', 0.0)
    ax.plot(rm_u, rm_v, 's', color='#dc2626', markersize=9, markeredgecolor='#0f172a',
            label=f'Bunkers Right-Mover ({rm_u:.1f}, {rm_v:.1f}) m/s [{np.hypot(rm_u, rm_v) * 1.943844:.1f} kt]')

    # Vetor de cisalhamento bulk 0-6 km
    idx_6k = np.argmin(np.abs(z_km - 6.0))
    ax.annotate('', xy=(u_f[idx_6k], v_f[idx_6k]), xytext=(u_f[0], v_f[0]),
                arrowprops=dict(arrowstyle="->", color='#1e293b', lw=2.0, linestyle='-'))

    # Legenda diagnóstica
    shear_6 = m.get('bulk_shear_0_6km_ms', 0.0)
    shear_6_kt = m.get('bulk_shear_0_6km_kt', 0.0)
    srh_3 = m.get('srh_0_3km_lm_m2s2', 0.0)
    w925_kt = m.get('wind_925_spd_kt', 0.0)
    w925_dir = m.get('wind_925_dir_deg', 0.0)

    diag_text = (
        f"Bulk Shear 0-6 km: {shear_6:.1f} m/s ({shear_6_kt:.1f} kt)\n"
        f"SRH 0-3 km (LM): {srh_3:.1f} m²/s² (Ciclônica no HS)\n"
        f"Vento em 925 hPa: {w925_kt:.1f} kt de {w925_dir:.0f}°"
    )
    ax.text(0.04, 0.04, diag_text, transform=ax.transAxes, fontsize=9.5, family='monospace',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#f8fafc', edgecolor='#cbd5e1'))

    ax.set_xlim(-40, 40)
    ax.set_ylim(-40, 40)
    ax.set_xlabel("Componente Zonal U (m/s)", fontsize=11, fontweight='bold')
    ax.set_ylabel("Componente Meridional V (m/s)", fontsize=11, fontweight='bold')
    ax.set_title("Hodógrafo do Vento Horizontal & Vetores de Bunkers LM/RM (Hemisfério Sul)\nSBFL Florianópolis (83899) — 28/08/2026 12Z (Granizo Gigante)", 
                 fontsize=12, fontweight='bold', color='#0f172a', pad=12)
    ax.legend(loc='upper right', fontsize=8.5, framealpha=0.92)

    out_fig = 'metpack/fig_kinematics_hodograph.png'
    plt.savefig(out_fig, dpi=160, bbox_inches='tight')
    plt.close()
    print(f"Saved: {out_fig}")

# ==============================================================================
# 8. MATRIZES 2D DE KERRY EMANUEL (ESCALA SIMÉTRICA +-15 K, ISOLINHA 0 K DESTACADA)
# ==============================================================================
def generate_emanuel_matrices(metrics):
    """
    Gera o painel 2x3 de matrizes 2D de Kerry Emanuel (1994):
    - Linha 1: Reversível (Tρ com retenção de condensado)
    - Linha 2: Pseudoadiabático (Tv com precipitação instantânea)
    - Mesma escala simétrica: vmin=-15 K, vmax=+15 K
    - Isolinha de 0 K destacada em preto contínuo espesso
    - Fundo branco
    """
    cases = [
        ('19951212', '12/12/1995 (Estável)'),
        ('19951222', '22/12/1995 (Neutra)'),
        ('19951224', '24/12/1995 (Instável)')
    ]

    fig, axes = plt.subplots(2, 3, figsize=(18, 11), dpi=150)
    fig.suptitle("Matrizes 2D de Convecção de Kerry Emanuel (1994, Atmospheric Convection)\nComparação Tríplice: Reversível (Tρ) vs. Pseudoadiabático (Tv) na Mesma Escala Simétrica", 
                 fontsize=13.5, fontweight='bold', color='#0f172a', y=0.98)

    levels_contour = np.arange(-14, 16, 2)
    mesh_last = None

    for col, (date, label) in enumerate(cases):
        p_path = f"metpack/{date}_p.out"
        po_path = f"metpack/{date}_porig.out"
        tr_path = f"metpack/{date}_tdifrev.out"
        tp_path = f"metpack/{date}_tdifpseudo.out"

        if not (os.path.exists(p_path) and os.path.exists(tr_path)):
            continue

        p = np.loadtxt(p_path)
        porig = np.loadtxt(po_path)
        tdifrev = np.loadtxt(tr_path)
        tdifpseudo = np.loadtxt(tp_path)

        n_rows, n_cols = tdifrev.shape
        p = p[:n_rows]
        porig = porig[:n_cols]
        X, Y = np.meshgrid(porig, p)

        # 1. Linha 1: Reversível (Tρ)
        ax_top = axes[0, col]
        mesh_top = ax_top.pcolormesh(X, Y, tdifrev, cmap='RdBu_r', shading='gouraud', vmin=-15.0, vmax=15.0)
        cs_top = ax_top.contour(X, Y, tdifrev, levels=levels_contour, colors='#475569', linewidths=0.6, alpha=0.7)
        # Isolinha de 0 K destacada
        cs0_top = ax_top.contour(X, Y, tdifrev, levels=[0.0], colors='#000000', linewidths=2.0)
        ax_top.clabel(cs0_top, inline=True, fontsize=8, fmt='0 K')

        ax_top.set_xlim(np.max(porig), np.min(porig))
        ax_top.set_ylim(np.max(p), np.min(p))
        ax_top.set_title(f"{label}\nReversível Tρ (com Carga de Água Retida)", fontsize=10.5, fontweight='bold', color='#0f172a')
        if col == 0:
            ax_top.set_ylabel('Pressão Elevada (hPa)', fontsize=10, fontweight='bold')
        ax_top.grid(True, linestyle=':', alpha=0.5, color='#94a3b8')

        # 2. Linha 2: Pseudoadiabático (Tv)
        ax_bot = axes[1, col]
        mesh_bot = ax_bot.pcolormesh(X, Y, tdifpseudo, cmap='RdBu_r', shading='gouraud', vmin=-15.0, vmax=15.0)
        mesh_last = mesh_bot
        cs_bot = ax_bot.contour(X, Y, tdifpseudo, levels=levels_contour, colors='#475569', linewidths=0.6, alpha=0.7)
        # Isolinha de 0 K destacada
        cs0_bot = ax_bot.contour(X, Y, tdifpseudo, levels=[0.0], colors='#000000', linewidths=2.0)
        ax_bot.clabel(cs0_bot, inline=True, fontsize=8, fmt='0 K')

        ax_bot.set_xlim(np.max(porig), np.min(porig))
        ax_bot.set_ylim(np.max(p), np.min(p))
        ax_bot.set_title(f"{label}\nPseudoadiabático Tv (Precipitação Instantânea)", fontsize=10.5, fontweight='bold', color='#0f172a')
        ax_bot.set_xlabel('Pressão de Origem da Parcela (hPa)', fontsize=10, fontweight='bold')
        if col == 0:
            ax_bot.set_ylabel('Pressão Elevada (hPa)', fontsize=10, fontweight='bold')
        ax_bot.grid(True, linestyle=':', alpha=0.5, color='#94a3b8')

        # Gera também figuras individuais para cada caso
        fig_ind, (ax_r, ax_p) = plt.subplots(1, 2, figsize=(14, 6), dpi=150)
        fig_ind.suptitle(f"Matrizes de Kerry Emanuel (1994) — SBPA {label}", fontsize=12, fontweight='bold')
        
        m_r = ax_r.pcolormesh(X, Y, tdifrev, cmap='RdBu_r', shading='gouraud', vmin=-15.0, vmax=15.0)
        ax_r.contour(X, Y, tdifrev, levels=[0.0], colors='black', linewidths=2.0)
        ax_r.set_xlim(np.max(porig), np.min(porig))
        ax_r.set_ylim(np.max(p), np.min(p))
        ax_r.set_title("Reversível Tρ (K)", fontsize=10.5, fontweight='bold')
        ax_r.set_xlabel('Pressão de Origem (hPa)', fontsize=9.5)
        ax_r.set_ylabel('Pressão Elevada (hPa)', fontsize=9.5)
        plt.colorbar(m_r, ax=ax_r, label='ΔTρ (K)')

        m_p = ax_p.pcolormesh(X, Y, tdifpseudo, cmap='RdBu_r', shading='gouraud', vmin=-15.0, vmax=15.0)
        ax_p.contour(X, Y, tdifpseudo, levels=[0.0], colors='black', linewidths=2.0)
        ax_p.set_xlim(np.max(porig), np.min(porig))
        ax_p.set_ylim(np.max(p), np.min(p))
        ax_p.set_title("Pseudoadiabático Tv (K)", fontsize=10.5, fontweight='bold')
        ax_p.set_xlabel('Pressão de Origem (hPa)', fontsize=9.5)
        plt.colorbar(m_p, ax=ax_p, label='ΔTv (K)')

        plt.tight_layout()
        plt.savefig(f"metpack/tcon_tdifrev_{date}.png", dpi=160, bbox_inches='tight')
        plt.close()

    # Barra de cores horizontal única para o painel principal
    if mesh_last:
        cax = fig.add_axes([0.25, 0.04, 0.50, 0.022])
        cb = fig.colorbar(mesh_last, cax=cax, orientation='horizontal')
        cb.set_label('Diferença de Temperatura de Flutuabilidade ΔT (K) [Azul: Flutuabilidade Negativa  |  Vermelho: Flutuabilidade Positiva]', 
                     fontsize=9.5, fontweight='bold', color='#0f172a')

    plt.tight_layout(rect=[0.02, 0.08, 0.98, 0.95])
    out_master = "metpack/fig_3_soundings_emanuel_matrices.png"
    plt.savefig(out_master, dpi=160, bbox_inches='tight')
    plt.close()
    print(f"Saved master Emanuel tripartite matrix figure: {out_master}")

def main():
    print("=== INICIANDO GERAÇÃO DE FIGURAS CIENTÍFICAS (REVISÃO 3) ===")
    metrics = load_metrics()
    # As figuras abaixo agora são geradas pelo notebook Seminario_plot_sounding_revisado.ipynb
    # (fonte única dos dados e valores) e gravadas em metpack/:
    #   fig_sounding_1_estavel.png, fig_sounding_2_neutra.png, fig_sounding_3_instavel.png,
    #   fig_perfis_theta_triplice.png, fig_3_soundings_profiles_comparison.png,
    #   fig_3_soundings_emanuel_matrices.png e emanuel_AAAAMMDD.png.
    # Por isso generate_individual_skewt, generate_perfis_theta_triplice, generate_3_soundings_profiles_comparison,
    # generate_all_soundings_colab_profiles e generate_emanuel_matrices não são mais chamadas aqui.
    generate_tripartite_skewt_panel(metrics)
    generate_cap2_thermo_profiles(metrics)
    generate_kinematics_hodograph(metrics)
    print("=== TODAS AS FIGURAS CIENTÍFICAS FORAM REGERADAS COM SUCESSO! ===")

if __name__ == '__main__':
    main()
