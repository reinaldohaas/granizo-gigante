"""
Isoterma de 0 graus, CAPE e vapor do ERA5 em agosto, 1940-2026, sobre SC e o corredor das celulas.

Pergunta: no granizo de 29/08/2026 a isoterma de 0 graus estava baixa em relacao ao normal de agosto?
E ela vem baixando ao longo das decadas? (Hipotese de fundo: na Pequena Idade do Gelo, com isoterma mais
baixa, granizo era comum na Ilha; depois sumiu por ~100 anos.)

Baixa do CDS (reanalysis-era5-single-levels), 18 e 21 UTC de todos os dias de agosto:
  zero_degree_level (m acima da superficie), convective_available_potential_energy, total_column_water_vapour.
Credencial: ~/.cdsapirc. Os arquivos ficam em ambiente/dados/era5/.

Uso: python ambiente/era5_isoterma.py
"""
import os
import zipfile

import cdsapi

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(AQUI, 'dados', 'era5')
AREA = [-25.5, -56.0, -29.5, -47.5]  # N, W, S, E
VARS = ['zero_degree_level', 'convective_available_potential_energy', 'total_column_water_vapour']
BLOCOS = [(1940, 1969), (1970, 1999), (2000, 2026)]


def main():
    import sys
    global VARS
    sufixo = ''
    if len(sys.argv) > 1 and sys.argv[1] == '--2m':   # temperatura e ponto de orvalho a 2 m (nivel de condensacao)
        VARS, sufixo = ['2m_temperature', '2m_dewpoint_temperature'], '_2m'
    os.makedirs(DADOS, exist_ok=True)
    c = cdsapi.Client()
    for a, b in BLOCOS:
        arq = os.path.join(DADOS, f'era5_ago{sufixo}_{a}_{b}.zip')
        if os.path.exists(arq):
            print('ja existe', arq, flush=True)
            continue
        print('pedindo', a, b, flush=True)
        c.retrieve('reanalysis-era5-single-levels', {
            'product_type': ['reanalysis'], 'variable': VARS,
            'year': [str(y) for y in range(a, b + 1)], 'month': ['08'],
            'day': [f'{d:02d}' for d in range(1, 32)], 'time': ['18:00', '21:00'],
            'area': AREA, 'data_format': 'netcdf', 'download_format': 'zip'}, arq)
        with zipfile.ZipFile(arq) as z:
            z.extractall(os.path.join(DADOS, f'{a}_{b}{sufixo}'))
        print('ok', arq, flush=True)


if __name__ == '__main__':
    main()
