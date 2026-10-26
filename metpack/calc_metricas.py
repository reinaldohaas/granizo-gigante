"""
calc_metricas.py adaptado para Florianópolis - Caso Granizo Gigante 28/08/2026
"""
import os, sys, re, json
import numpy as np
import pandas as pd
import metpy.calc as mpcalc
from metpy.units import units

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calc_metricas import (
    parse_wyoming_txt, parse_wyoming_indices_html,
    analyze_lapse_rates_and_qc, calc_diagnostics, parse_emanuel_cape_out
)

def main():
    print("=== INICIANDO CÁLCULO DE MÉTRICAS: FLORIANÓPOLIS 28/08/2026 ===")
    
    indices_files = {
        '20260826': 'metpack/indices_20260826_12Z.txt',
        '20260831': 'metpack/indices_20260831_00Z.txt',
        '20260828': 'metpack/indices_20260828_12Z.txt'
    }

    out_json = {}

    # 1. Carregamento dos dados
    df_12 = parse_wyoming_txt('metpack/sounding_20260826_12Z.txt')
    df_22 = parse_wyoming_txt('metpack/sounding_20260831_00Z.txt')
    df_24 = parse_wyoming_txt('metpack/sounding_20260828_12Z.txt')

    # QC e taxas de lapso em 28/08/2026
    qc_flags_24 = analyze_lapse_rates_and_qc(df_24)
    out_json['qc_camadas_superadiabaticas_20260828'] = qc_flags_24
    out_json['qc_camadas_superadiabaticas_19951224'] = qc_flags_24

    # Camadas específicas de baixos níveis / 925 hPa em 28/08/2026
    idx_925 = (df_24['PRES'] - 925.0).abs().idxmin()
    idx_908 = (df_24['PRES'] - 908.0).abs().idxmin()
    idx_850 = (df_24['PRES'] - 850.0).abs().idxmin()

    dz_925_908 = df_24.loc[idx_908, 'HGHT'] - df_24.loc[idx_925, 'HGHT']
    dT_925_908 = df_24.loc[idx_908, 'TEMP'] - df_24.loc[idx_925, 'TEMP']
    gamma_925_908 = - (dT_925_908 / dz_925_908) * 1000.0 if dz_925_908 != 0 else 0
    dth_dz_925_908 = ((df_24.loc[idx_908, 'THTA'] - df_24.loc[idx_925, 'THTA']) / dz_925_908) * 1000.0 if dz_925_908 != 0 else 0

    dz_908_850 = df_24.loc[idx_850, 'HGHT'] - df_24.loc[idx_908, 'HGHT']
    dT_908_850 = df_24.loc[idx_850, 'TEMP'] - df_24.loc[idx_908, 'TEMP']
    gamma_908_850 = - (dT_908_850 / dz_908_850) * 1000.0 if dz_908_850 != 0 else 0
    dth_dz_908_850 = ((df_24.loc[idx_850, 'THTA'] - df_24.loc[idx_908, 'THTA']) / dz_908_850) * 1000.0 if dz_908_850 != 0 else 0

    out_json['gradientes_camadas_925'] = {
        'camada_925_910': {
            'dz_m': round(float(dz_925_908), 1),
            'dT_C': round(float(dT_925_908), 2),
            'gamma_K_km': round(float(gamma_925_908), 2),
            'dtheta_dz_K_km': round(float(dth_dz_925_908), 2),
            'dtheta_e_K': round(float(df_24.loc[idx_908, 'THTE'] - df_24.loc[idx_925, 'THTE']), 2)
        },
        'camada_910_850': {
            'dz_m': round(float(dz_908_850), 1),
            'dT_C': round(float(dT_908_850), 2),
            'gamma_K_km': round(float(gamma_908_850), 2),
            'dtheta_dz_K_km': round(float(dth_dz_908_850), 2),
            'dtheta_e_K': round(float(df_24.loc[idx_850, 'THTE'] - df_24.loc[idx_908, 'THTE']), 2)
        }
    }

    # Teste de sensibilidade: sondagem sem os níveis de 946 a 908 hPa
    low_level_near_925 = [946.0, 940.6, 925.0, 908.0]
    df_24_sens = df_24[~df_24['PRES'].isin(low_level_near_925)].reset_index(drop=True)

    # 2. Diagnóstico Estável (26/08/2026 12Z)
    diag_12 = calc_diagnostics(df_12, "20260826")
    emanuel_12 = parse_emanuel_cape_out('emanuel_20260826_12/cape.out')
    diag_12['emanuel'] = emanuel_12
    ind_12 = parse_wyoming_indices_html(indices_files['20260826'])
    diag_12['indices_wyoming'] = ind_12
    out_json['20260826'] = diag_12
    out_json['19951212'] = diag_12

    # 3. Diagnóstico Neutra (31/08/2026 00Z)
    diag_22 = calc_diagnostics(df_22, "20260831")
    emanuel_22 = parse_emanuel_cape_out('emanuel_20260831_00/cape.out')
    diag_22['emanuel'] = emanuel_22
    ind_22 = parse_wyoming_indices_html(indices_files['20260831'])
    diag_22['indices_wyoming'] = ind_22
    out_json['20260831'] = diag_22
    out_json['19951222'] = diag_22

    # 4. Diagnóstico Instável (28/08/2026 12Z)
    diag_24_raw = calc_diagnostics(df_24, "20260828_raw")
    emanuel_24 = parse_emanuel_cape_out('emanuel_20260828_12/cape.out')
    diag_24_raw['emanuel'] = emanuel_24
    ind_24 = parse_wyoming_indices_html(indices_files['20260828'])
    diag_24_raw['indices_wyoming'] = ind_24
    out_json['20260828_raw'] = diag_24_raw
    out_json['20260828'] = diag_24_raw
    out_json['19951224_raw'] = diag_24_raw
    out_json['19951224'] = diag_24_raw

    # 5. Sensibilidade 28/08/2026
    diag_24_sens = calc_diagnostics(df_24_sens, "20260828_sensibilidade")
    diag_24_sens['emanuel'] = "Teste de sensibilidade com níveis de 925 hPa removidos da ascensão"
    diag_24_sens['indices_wyoming'] = None
    out_json['20260828_sensibilidade'] = diag_24_sens
    out_json['19951224_sensibilidade'] = diag_24_sens
    out_json['19951224_qc'] = diag_24_sens

    # Integração direta com metpack/metricas_notebook.json
    arq_nb = 'metpack/metricas_notebook.json'
    if os.path.exists(arq_nb):
        with open(arq_nb, encoding='utf-8') as f:
            nbm = json.load(f)
        mapa = {
            'pw_mm': 'PWAT (mm)', 'lcl_p_hPa': 'LCL (hPa)', 'sbcape_Jkg': 'SBCAPE (J/kg)', 'sbcin_Jkg': 'SBCIN (J/kg)',
            'mucape_Jkg': 'MUCAPE (J/kg)', 'mucin_Jkg': 'MUCIN (J/kg)', 'mlcape_Jkg': 'MLCAPE (J/kg)', 'mlcin_Jkg': 'MLCIN (J/kg)',
            'lfc_p_hPa': 'LFC (hPa)', 'el_p_hPa': 'EL (hPa)', 'lifted_index_K': 'LI (K)', 'k_index_C': 'K Index (°C)',
            'total_totals_C': 'Total Totals (°C)', 'showalter_K': 'Showalter (K)', 'sweat_index': 'SWEAT',
            'sweat_index_kt': 'SWEAT (vento em nós)', 'dcape_metpy_Jkg': 'DCAPE (J/kg)',
            'bulk_shear_0_1km_kt': 'Shear 0-1 km (kt)', 'bulk_shear_0_6km_kt': 'Shear 0-6 km (kt)',
            'srh_0_1km_lm_m2s2': 'SRH 0-1 km LM (m²/s²)', 'srh_0_3km_lm_m2s2': 'SRH 0-3 km LM (m²/s²)'
        }
        mapa_em = {
            'surface_cape_rev_Jkg': 'CAPE reversível superfície (J/kg)', 'surface_cape_pseudo_Jkg': 'CAPE pseudoadiabática superfície (J/kg)',
            'max_cape_rev_Jkg': 'CAPE reversível máxima (J/kg)', 'max_cape_pseudo_Jkg': 'CAPE pseudoadiabática máxima (J/kg)',
            'max_cape_p_hPa': 'Nível de origem da CAPE máxima (hPa)', 'max_dcape_emanuel_Jkg': 'DCAPE máxima Emanuel (J/kg)'
        }
        for dkey, diag in (('20260826', diag_12), ('20260831', diag_22), ('20260828', diag_24_raw)):
            if dkey in nbm:
                I = nbm[dkey]['indices_metpy']
                for k_m, k_nb in mapa.items():
                    if I.get(k_nb) is not None:
                        diag[k_m] = round(float(I[k_nb]), 1)
                if not isinstance(diag.get('emanuel'), dict):
                    diag['emanuel'] = {}
                for k_m, k_nb in mapa_em.items():
                    if k_nb in nbm[dkey]['emanuel']:
                        diag['emanuel'][k_m] = nbm[dkey]['emanuel'][k_nb]
        print(f"-> Valores do notebook aplicados a partir de {arq_nb}")

    # DCAPE comparativo
    out_json['dcape_comparativo'] = {
        '20260826': {
            'data': '26/08/2026', 'regime': 'Estável',
            'wyoming_Jkg': (ind_12.get('DCAPE', {}).get('value') if ind_12 else None),
            'metpy_Jkg': diag_12.get('dcape_metpy_Jkg'),
            'emanuel_max_Jkg': (emanuel_12.get('max_dcape_emanuel_Jkg') if emanuel_12 else None),
            'emanuel_max_p_hPa': (emanuel_12.get('max_dcape_p_hPa') if emanuel_12 else None)
        },
        '20260831': {
            'data': '31/08/2026', 'regime': 'Neutra',
            'wyoming_Jkg': (ind_22.get('DCAPE', {}).get('value') if ind_22 else None),
            'metpy_Jkg': diag_22.get('dcape_metpy_Jkg'),
            'emanuel_max_Jkg': (emanuel_22.get('max_dcape_emanuel_Jkg') if emanuel_22 else None),
            'emanuel_max_p_hPa': (emanuel_22.get('max_dcape_p_hPa') if emanuel_22 else None)
        },
        '20260828_raw': {
            'data': '28/08/2026', 'regime': 'Instável (Oficial - Granizo Gigante)',
            'wyoming_Jkg': (ind_24.get('DCAPE', {}).get('value') if ind_24 else None),
            'metpy_Jkg': diag_24_raw.get('dcape_metpy_Jkg'),
            'emanuel_max_Jkg': (emanuel_24.get('max_dcape_emanuel_Jkg') if emanuel_24 else None),
            'emanuel_max_p_hPa': (emanuel_24.get('max_dcape_p_hPa') if emanuel_24 else None)
        },
        '20260828_sensibilidade': {
            'data': '28/08/2026', 'regime': 'Instável (Sensibilidade)',
            'wyoming_Jkg': None,
            'metpy_Jkg': diag_24_sens.get('dcape_metpy_Jkg'),
            'emanuel_max_Jkg': None,
            'emanuel_max_p_hPa': None
        }
    }
    # Backward compatibility
    out_json['dcape_comparativo']['19951212'] = out_json['dcape_comparativo']['20260826']
    out_json['dcape_comparativo']['19951222'] = out_json['dcape_comparativo']['20260831']
    out_json['dcape_comparativo']['19951224_raw'] = out_json['dcape_comparativo']['20260828_raw']
    out_json['dcape_comparativo']['19951224_sensibilidade'] = out_json['dcape_comparativo']['20260828_sensibilidade']

    # Tabela comparativa Wyoming vs MetPy
    comp_dict = {}
    for dt_key, dt_label, diag in [('20260826', '26/08/2026', diag_12), ('20260831', '31/08/2026', diag_22), ('20260828', '28/08/2026', diag_24_raw)]:
        w = diag.get('indices_wyoming', {}) or {}
        items = [
            ('PW (Água Precipitável)', 'mm', w.get('PWAT', {}).get('value'), diag.get('pw_mm')),
            ('MUCAPE (Most Unstable CAPE)', 'J/kg', w.get('MUCAPE', {}).get('value'), diag.get('mucape_Jkg')),
            ('MUCIN (Most Unstable CIN)', 'J/kg', w.get('MUCIN', {}).get('value'), diag.get('mucin_Jkg')),
            ('SBCAPE (Surface-Based CAPE)', 'J/kg', w.get('CAPE', {}).get('value'), diag.get('sbcape_Jkg')),
            ('SBCIN (Surface-Based CIN)', 'J/kg', w.get('CINS', {}).get('value'), diag.get('sbcin_Jkg')),
            ('LCL Pressão (LCLP)', 'hPa', w.get('LCLP', {}).get('value'), diag.get('lcl_p_hPa')),
            ('LFC Pressão (LFCP)', 'hPa', w.get('LFCP', {}).get('value'), diag.get('lfc_p_hPa')),
            ('EL Pressão (EQLV)', 'hPa', w.get('EQLV', {}).get('value'), diag.get('el_p_hPa')),
            ('K-Index (KINX)', '°C', w.get('KINX', {}).get('value'), diag.get('k_index_C')),
            ('Total Totals (TOTL)', 'K', w.get('TOTL', {}).get('value'), diag.get('total_totals_C')),
            ('Cross Totals (CTOT)', 'K', w.get('CTOT', {}).get('value'), diag.get('cross_totals_C')),
            ('Vertical Totals (VTOT)', 'K', w.get('VTOT', {}).get('value'), diag.get('vertical_totals_C')),
            ('Showalter Index (SHOW)', 'K', w.get('SHOW', {}).get('value'), diag.get('showalter_K')),
            ('SWEAT Index (SWET)', 'adimensional', w.get('SWET', {}).get('value'), diag.get('sweat_index')),
            ('SWEAT com vento em nós', 'adimensional', None, diag.get('sweat_index_kt')),
            ('Lifted Index (LFVT/LIFT)', 'K', w.get('LFVT', {}).get('value'), diag.get('lifted_index_K')),
            ('DCAPE (Downdraft CAPE)', 'J/kg', w.get('DCAPE', {}).get('value'), diag.get('dcape_metpy_Jkg'))
        ]
        row_list = []
        for name, unit, val_w, val_calc in items:
            diff = round(val_calc - val_w, 2) if (val_w is not None and val_calc is not None and isinstance(val_w, (int, float)) and isinstance(val_calc, (int, float))) else None
            row_list.append({
                'indice': name, 'unidade': unit, 'wyoming': val_w, 'metpy': val_calc, 'siphon_metpy': val_calc, 'diferenca': diff
            })
        comp_dict[dt_key] = {'data': dt_label, 'linhas': row_list}
    comp_dict['19951212'] = comp_dict['20260826']
    comp_dict['19951222'] = comp_dict['20260831']
    comp_dict['19951224'] = comp_dict['20260828']
    out_json['comparativo_wyoming_metpy'] = comp_dict

    with open('metpack/metricas.json', 'w', encoding='utf-8') as f:
        json.dump(out_json, f, indent=2, ensure_ascii=False)
    print("-> SUCESSO: metpack/metricas.json gerado com sucesso para Florianópolis 2026!")

if __name__ == '__main__':
    main()
