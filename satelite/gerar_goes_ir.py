"""
GOES-19 ABI canal 13 (IR limpo, 10.3 um) recortado no dominio d03 do projeto
Floripa, com os limites municipais do IBGE por cima.

Gera tres series por varredura:
  c13       - realce IR convencional, escala larga (-90 a +50 C)
  contraste - escala fechada nos topos frios, com os raios do GLM por cima,
              para identificar a celula que produziu granizo
  split     - diferenca split-window C15-C13 (12.3-10.3 um): valor positivo sob
              topo espesso e frio indica topo penetrante (convecccao severa)

Escreve tambem resumo_evento.png e .csv com a serie temporal do evento.

Fontes (bucket publico noaa-goes19, AWS Open Data):
  ABI-L2-CMIPF  Cloud and Moisture Imagery, disco cheio, 10 min
  GLM-L2-LCFA   Geostationary Lightning Mapper, granulos de 20 s

Uso:
  python gerar_goes_ir.py                 # gera tudo que falta
  python gerar_goes_ir.py 3               # so as 3 primeiras varreduras (teste)
"""
import os
import sys
import datetime as dt
import tempfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import netCDF4
import s3fs
import xarray as xr
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm
from pyproj import CRS, Transformer
from scipy.ndimage import map_coordinates

SAIDA = r'C:\gis4wrf\projects\Floripa\satelite'
SHP_MUN = 'C:/gis4wrf/projects/Floripa/shp_ibge/SC_Municipios_2022.shp'

# Dominio d03 do namelist.wps (181x181 @ 1 km, centrado na Ilha de SC)
LON_MIN, LON_MAX = -49.545, -47.857
LAT_MIN, LAT_MAX = -28.246, -26.749

# Norte da Ilha de Santa Catarina — area de interesse marcada nas figuras
NORTE_LON = (-48.60, -48.37)
NORTE_LAT = (-27.52, -27.35)

# Grade de saida (~0.01 deg ~ 1.1 km; superamostra o pixel do GOES de proposito,
# para os limites municipais nao ficarem serrilhados)
PASSO = 0.01

INICIO = dt.datetime(2026, 8, 29, 21, 0)
FIM = dt.datetime(2026, 8, 30, 5, 0)

# --- Relatos de granizo (horarios em UTC; local = UTC-3) --------------------
#
# Episodio 1 — o de interesse. A celula atinge Biguacu (continente) e a ponta
# oeste do norte da Ilha por volta das 22h, e avanca para leste: Cachoeira do
# Bom Jesus as 22h50 (referencia mais precisa) e Ingleses/Vargem ate 23h.
#
# Episodio 2 — novos registros proximo da meia-noite local (~03h UTC). Evento
# distinto: marcado como tal nas figuras para nao ser confundido com o primeiro.
#
# Coordenadas aproximadas, no nivel do bairro/sede municipal.
def _u(h, m, dia=29):
    return dt.datetime(2026, 8, dia, h, m)


RELATOS = [
    {'nome': 'Biguaçu', 'lon': -48.657, 'lat': -27.494,
     'ini': _u(22, 0), 'fim': _u(22, 30)},
    {'nome': 'Jurerê / Canasvieiras', 'lon': -48.480, 'lat': -27.432,
     'ini': _u(22, 0), 'fim': _u(22, 30)},
    {'nome': 'Cachoeira do Bom Jesus', 'lon': -48.437, 'lat': -27.425,
     'ini': _u(22, 50), 'fim': _u(22, 50)},
    {'nome': 'Ingleses / Vargem do Bom Jesus', 'lon': -48.402, 'lat': -27.432,
     'ini': _u(22, 40), 'fim': _u(23, 0)},
]

EP1 = (_u(22, 0), _u(23, 0))
EP1_REF = _u(22, 50)   # Cachoeira do Bom Jesus — referencia temporal mais precisa
EP2 = (_u(2, 30, 30), _u(4, 0, 30))


def rotulo_episodio(quando):
    """
    Marcador curto de episodio para o titulo. Os nomes das localidades ficam
    na caixa de relatos, nao aqui: titulo de comprimento variavel muda a
    largura da figura salva com bbox_inches='tight', e a serie sai desalinhada.
    """
    if EP1[0] <= quando <= EP1[1]:
        return '   ← episódio 1', '#b00000'
    if EP2[0] <= quando <= EP2[1]:
        return '   ← 2º episódio (evento distinto)', '#8a6d00'
    return '', 'black'


def marcar_relatos(ax, quando):
    """
    Numera os pontos de relato no mapa e lista os nomes numa caixa. Os rotulos
    ficam fora do mapa de proposito: as localidades do norte da Ilha distam
    poucos km entre si, e caixas de texto sobre elas se sobrepoem.
    """
    linhas = []
    for n, r in enumerate(RELATOS, 1):
        ativo = r['ini'] <= quando <= r['fim']
        ax.plot(r['lon'], r['lat'], marker='v' if ativo else '.',
                ms=10 if ativo else 5,
                mfc='#ff2020' if ativo else '#ffffff',
                mec='#000000', mew=1.0 if ativo else 0.6, zorder=8)
        ax.annotate(str(n), xy=(r['lon'], r['lat']), xytext=(0, 7),
                    textcoords='offset points', ha='center', fontsize=7,
                    weight='bold', color='#b00000' if ativo else '#404040',
                    zorder=9)
        janela = f"{r['ini']:%H:%M}" + (f"–{r['fim']:%H:%M}" if r['fim'] != r['ini'] else '')
        linhas.append((f"{n}. {r['nome']}  {janela}Z", ativo))

    texto = '\n'.join(t for t, _ in linhas)
    caixa = ax.text(0.015, 0.015, 'Relatos de granizo (episódio 1)\n' + texto,
                    transform=ax.transAxes, fontsize=6.5, va='bottom', ha='left',
                    zorder=10, linespacing=1.4,
                    bbox=dict(boxstyle='round,pad=0.35', fc='#ffffffdd', ec='#909090',
                              lw=0.5))
    if any(a for _, a in linhas):
        caixa.set_color('#b00000')

# Escala fechada do produto de contraste
CONTR_MIN, CONTR_MAX = -60.0, -15.0

# Escala do split-window C15-C13, em K (assimetrica: o sinal deste evento vai
# de -8 a +1, e o zero e a referencia fisica que separa nuvem fina de topo
# penetrante, entao a rampa e centrada nele)
SPLIT_MIN, SPLIT_MAX = -6.0, 1.5

# Limiar de topo espesso e frio: acima dele o split-window nao diz nada
# sobre topo penetrante
ANVIL_C = -45.0


def escala_ir():
    """
    Realce IR classico: tons de cinza do quente (escuro) ao frio (claro) ate
    -30 C, e a partir dai cores para destacar topos de nuvem convectivos.
    """
    tmin, tmax = -90.0, 50.0

    def pos(t):
        return (t - tmin) / (tmax - tmin)

    cores = [
        (pos(-90), '#ffffff'),
        (pos(-80), '#b400b4'),
        (pos(-70), '#ff0000'),
        (pos(-60), '#ffa500'),
        (pos(-50), '#ffff00'),
        (pos(-40), '#00c800'),
        (pos(-30), '#00ffff'),
        (pos(-30.001), '#ffffff'),
        (pos(20), '#404040'),
        (pos(50), '#000000'),
    ]
    cores = sorted(set(cores), key=lambda c: c[0])
    return LinearSegmentedColormap.from_list('ir_realce', cores), Normalize(tmin, tmax)


def escala_contraste():
    """
    Rampa esticada entre -60 e -15 C, faixa onde ficam os topos deste evento —
    a escala larga achata tudo isso num verde uniforme. Acima de -15 C segue em
    cinza, no mesmo mapa de cores: usar um unico imshow evita o serrilhado que
    aparece quando se mascara o campo antes de interpolar.
    """
    tmin, tmax = CONTR_MIN, 20.0

    def pos(t):
        return (t - tmin) / (tmax - tmin)

    cores = [
        (pos(-60), '#6b0f6b'),
        (pos(-55), '#d81e1e'),
        (pos(-50), '#f08a1e'),
        (pos(-45), '#e8e83a'),
        (pos(-40), '#2fd07a'),
        (pos(-35), '#2f8fd0'),
        (pos(-30), '#7ec8e3'),
        (pos(-20), '#dff0f6'),
        (pos(CONTR_MAX), '#e6e6e6'),
        (pos(0), '#909090'),
        (pos(20), '#3a3a3a'),
    ]
    return (LinearSegmentedColormap.from_list('contraste', cores),
            Normalize(tmin, tmax))


def listar_abi(fs, inicio, fim, canal='C13'):
    """Arquivos do canal no disco cheio cujo inicio de varredura cai na janela."""
    achados = {}
    h = inicio.replace(minute=0, second=0, microsecond=0)
    while h <= fim:
        pref = f"noaa-goes19/ABI-L2-CMIPF/{h.year}/{h.timetuple().tm_yday:03d}/{h.hour:02d}"
        try:
            for f in fs.ls(pref):
                nome = f.rsplit('/', 1)[-1]
                if f'-M6{canal}_' not in nome and f'-M3{canal}_' not in nome:
                    continue
                s = nome.split('_s')[1][:13]  # YYYYDDDHHMMSS
                t = dt.datetime.strptime(s[:11], '%Y%j%H%M')
                if inicio <= t <= fim:
                    achados[t] = f
        except FileNotFoundError:
            pass
        h += dt.timedelta(hours=1)
    return achados


def campo(fs, chave, lons, lats):
    """Baixa um arquivo CMIP e devolve o recorte ja reamostrado, em °C."""
    with tempfile.NamedTemporaryFile(suffix='.nc', delete=False) as tmp:
        local = tmp.name
    try:
        fs.get(chave, local)
        with xr.open_dataset(local, engine='netcdf4') as ds:
            return recortar(ds, lons, lats)
    finally:
        try:
            os.remove(local)
        except OSError:
            pass


def raios_glm(fs, inicio, fim, cache={}):
    """
    Flashes do GLM na janela [inicio, fim). Le os granulos direto da memoria,
    em paralelo — sao ~30 arquivos de 370 KB por intervalo de 10 min.
    """
    pref = (f"noaa-goes19/GLM-L2-LCFA/{inicio.year}/"
            f"{inicio.timetuple().tm_yday:03d}/{inicio.hour:02d}")
    if pref not in cache:
        try:
            cache[pref] = sorted(fs.ls(pref))
        except FileNotFoundError:
            cache[pref] = []

    alvos = []
    for f in cache[pref]:
        s = f.rsplit('/', 1)[-1].split('_s')[1][:13]
        t = dt.datetime.strptime(s[:11], '%Y%j%H%M')
        if inicio <= t < fim:
            alvos.append(f)
    if not alvos:
        return np.empty((0, 2))

    def baixar(chave):
        try:
            return fs.cat_file(chave)
        except Exception:
            return None

    # So o download vai para as threads. A decodificacao roda em serie: a
    # biblioteca HDF5 nao e thread-safe, e abrir varios arquivos em paralelo
    # corrompe o estado global dela — o sintoma aparece depois, como
    # "NetCDF: Not a valid ID" na proxima leitura, que pode ser de outro arquivo.
    with ThreadPoolExecutor(max_workers=16) as ex:
        blobs = list(ex.map(baixar, alvos))

    partes = []
    for n, blob in enumerate(blobs):
        if not blob:
            continue
        try:
            with netCDF4.Dataset(f'glm{n}', memory=blob) as d:
                lon = np.asarray(d['flash_lon'][:], dtype='float64')
                lat = np.asarray(d['flash_lat'][:], dtype='float64')
        except Exception:
            continue
        if lon.size:
            partes.append(np.column_stack([lon, lat]))

    if not partes:
        return np.empty((0, 2))
    p = np.vstack(partes)
    m = ((p[:, 0] >= LON_MIN) & (p[:, 0] <= LON_MAX) &
         (p[:, 1] >= LAT_MIN) & (p[:, 1] <= LAT_MAX) & np.isfinite(p).all(axis=1))
    return p[m]


def recortar(ds, lons, lats):
    """Reamostra o CMI da grade fixa do GOES para a grade regular lat/lon."""
    proj = ds['goes_imager_projection']
    h = float(proj.perspective_point_height)
    geos = CRS.from_proj4(
        f"+proj=geos +h={h} +lon_0={float(proj.longitude_of_projection_origin)} "
        f"+a={float(proj.semi_major_axis)} +b={float(proj.semi_minor_axis)} "
        f"+sweep={proj.sweep_angle_axis} +units=m +no_defs")
    para_geos = Transformer.from_crs(CRS.from_epsg(4326), geos, always_xy=True)

    LON, LAT = np.meshgrid(lons, lats)
    X, Y = para_geos.transform(LON, LAT)

    # eixos do arquivo estao em radianos de angulo de varredura
    x = ds['x'].values * h
    y = ds['y'].values * h
    col = (X - x[0]) / (x[1] - x[0])
    lin = (Y - y[0]) / (y[1] - y[0])

    # le so o bloco necessario, com folga
    c0 = max(int(np.nanmin(col)) - 2, 0)
    c1 = min(int(np.nanmax(col)) + 3, x.size)
    l0 = max(int(np.nanmin(lin)) - 2, 0)
    l1 = min(int(np.nanmax(lin)) + 3, y.size)

    bloco = ds['CMI'][l0:l1, c0:c1].values.astype('float64')
    dados = map_coordinates(np.nan_to_num(bloco, nan=np.nanmax(bloco)),
                            [lin - l0, col - c0], order=1, mode='nearest')
    return dados - 273.15  # K -> C


def moldura(ax, lons, lats, municipios, cor='#000000'):
    """
    Limites municipais, contorno de Florianopolis e caixa do norte da Ilha.

    `cor` existe porque os produtos de fundo escuro (C13-C07, microfisica)
    engolem traco preto: neles passa-se um tom claro.
    """
    municipios.boundary.plot(ax=ax, edgecolor=cor, linewidth=0.6, alpha=0.6, zorder=2)
    floripa = municipios[municipios['NM_MUN'].str.contains('Florian', case=False, na=False)]
    if not floripa.empty:
        floripa.boundary.plot(ax=ax, edgecolor=cor, linewidth=1.6, zorder=3)

    ax.add_patch(plt.Rectangle((NORTE_LON[0], NORTE_LAT[0]),
                               NORTE_LON[1] - NORTE_LON[0],
                               NORTE_LAT[1] - NORTE_LAT[0],
                               fill=False, edgecolor=cor, linewidth=1.2,
                               linestyle='--', zorder=5))
    ax.annotate('Norte da Ilha', xy=(NORTE_LON[1], NORTE_LAT[1]),
                xytext=(4, 4), textcoords='offset points',
                fontsize=8, weight='bold', color=cor, zorder=6)

    ax.set_xlim(lons[0], lons[-1])
    ax.set_ylim(lats[-1], lats[0])
    ax.set_xlabel('Longitude'); ax.set_ylabel('Latitude')
    ax.grid(color='#ffffff40', linewidth=0.4, linestyle=':', zorder=4)


def desenhar_padrao(temp_c, lons, lats, quando, municipios, cmap, norm, destino):
    fig, ax = plt.subplots(figsize=(9, 8.4), dpi=150)
    im = ax.imshow(temp_c, origin='upper', cmap=cmap, norm=norm,
                   extent=[lons[0], lons[-1], lats[-1], lats[0]],
                   interpolation='bilinear', zorder=1)
    moldura(ax, lons, lats, municipios)
    ax.set_title(f"GOES-19 ABI C13 (IR 10.3 um)  —  {quando:%d/%m/%Y %H:%M} UTC\n"
                 f"dominio d03 (Floripa)", fontsize=11)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02,
                      ticks=[-90, -70, -50, -30, -10, 10, 30, 50])
    cb.set_label('Temperatura de brilho (°C)')
    fig.tight_layout()
    fig.savefig(destino, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def desenhar_contraste(temp_c, lons, lats, quando, municipios, cmap, norm,
                       flashes, destino):
    fig, ax = plt.subplots(figsize=(9, 8.4), dpi=150)
    ext = [lons[0], lons[-1], lats[-1], lats[0]]

    im = ax.imshow(temp_c, origin='upper', cmap=cmap, norm=norm, extent=ext,
                   interpolation='bilinear', zorder=1)

    if len(flashes):
        ax.scatter(flashes[:, 0], flashes[:, 1], s=30, marker='+',
                   c='#000000', linewidths=1.0, zorder=7,
                   label=f'GLM: {len(flashes)} flashes / 10 min')
        ax.legend(loc='upper left', fontsize=8, framealpha=0.85)

    moldura(ax, lons, lats, municipios)

    marca, cor = rotulo_episodio(quando)
    marcar_relatos(ax, quando)
    local = quando - dt.timedelta(hours=3)
    ax.set_title(f"GOES-19 C13 — realce de topos frios  —  {quando:%d/%m/%Y %H:%M} UTC "
                 f"({local:%H:%M} local){marca}\n"
                 f"cores de {CONTR_MIN:.0f} a {CONTR_MAX:.0f} °C, cinza acima"
                 f"   |   + = flashes GLM   |   ▼ = relato de granizo",
                 fontsize=10, color=cor)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02,
                      ticks=[-60, -55, -50, -45, -40, -35, -30, -25, -20, -15, 0, 20])
    cb.set_label('Temperatura de brilho (°C)')
    fig.tight_layout()
    fig.savefig(destino, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def desenhar_split(btd, temp_c, lons, lats, quando, municipios, destino):
    """
    Diferenca split-window C15 - C13 (12.3 - 10.3 um).

    O vapor d'agua absorve mais em 12.3 um que em 10.3 um, entao o sinal depende
    da opacidade e do perfil de temperatura acima da nuvem:

      muito negativo  nuvem fina / borda de anvil / ceu limpo — parte da radiacao
                      quente da superficie vaza mais no canal 10.3
      perto de zero   topo espesso e opaco
      positivo        assinatura de topo penetrante: acima da tropopausa a
                      temperatura sobe com a altura, e o canal mais absorvente
                      passa a enxergar camadas mais quentes
    """
    fig, ax = plt.subplots(figsize=(9, 8.4), dpi=150)
    ext = [lons[0], lons[-1], lats[-1], lats[0]]

    im = ax.imshow(btd, origin='upper', cmap='RdBu_r',
                   norm=TwoSlopeNorm(vcenter=0.0, vmin=SPLIT_MIN, vmax=SPLIT_MAX),
                   extent=ext, interpolation='bilinear', zorder=1)

    # contorno do anvil, para situar onde estao os topos frios
    cs = ax.contour(lons, lats, temp_c, levels=[-50, -45], colors='#000000',
                    linewidths=[1.1, 0.7], linestyles=['-', '--'], zorder=4)
    ax.clabel(cs, fmt='%d °C', fontsize=7)

    # so conta positivos sob topo espesso e frio: em ceu limpo ou nuvem baixa
    # o sinal positivo nao tem nada a ver com topo penetrante
    anvil = temp_c <= ANVIL_C
    positivos = int((btd[anvil] > 0).sum()) if anvil.any() else 0

    moldura(ax, lons, lats, municipios)
    local = quando - dt.timedelta(hours=3)
    marca, cor = rotulo_episodio(quando)
    marcar_relatos(ax, quando)
    ax.set_title(f"GOES-19 split-window C15−C13 (12.3−10.3 µm)  —  "
                 f"{quando:%d/%m/%Y %H:%M} UTC ({local:%H:%M} local){marca}\n"
                 f"positivo = possível topo penetrante  |  {positivos} px > 0 "
                 f"sob C13 ≤ {ANVIL_C:.0f} °C  |  contorno: C13 em −50/−45 °C",
                 fontsize=10, color=cor)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label('C15 − C13 (K)')
    fig.tight_layout()
    fig.savefig(destino, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def resumo_evento(registros, destino):
    """
    Serie temporal do evento: topo mais frio no dominio e no norte da Ilha,
    contra a contagem de flashes do GLM por intervalo de 10 min.
    """
    if not registros:
        return
    t = [r['quando'] for r in registros]
    fig, ax = plt.subplots(figsize=(11, 5), dpi=150)

    ax2 = ax.twinx()
    ax2.bar(t, [r['flashes'] for r in registros],
            width=dt.timedelta(minutes=8), color='#c8c8c8',
            edgecolor='#9a9a9a', linewidth=0.4, zorder=1,
            label='flashes GLM / 10 min (domínio d03)')
    ax2.set_ylabel('Flashes GLM por 10 min')
    ax2.set_ylim(bottom=0)

    ax.plot(t, [r['min_d03'] for r in registros], '-o', ms=3.5, lw=1.6,
            color='#1f4fd8', zorder=3, label='topo mais frio — domínio d03')
    ax.plot(t, [r['min_norte'] for r in registros], '-s', ms=3.5, lw=1.6,
            color='#d81e1e', zorder=3, label='topo mais frio — norte da Ilha')
    ax.set_zorder(ax2.get_zorder() + 1); ax.patch.set_visible(False)

    topo = ax.get_ylim()[1]

    # episodio 1 — o de interesse
    ax.axvspan(EP1[0], EP1[1], color='#d81e1e', alpha=0.12, zorder=0)
    ax.axvline(EP1_REF, color='#b00000', lw=1.6, ls='--', zorder=4)
    ax.annotate('episódio 1 — granizo\n22:00–23:00Z (19–20h local)',
                xy=(EP1[0], topo), xytext=(4, -10), textcoords='offset points',
                fontsize=8, weight='bold', va='top', color='#b00000')

    # episodio 2 — evento distinto, nao misturar com o primeiro
    ax.axvspan(EP2[0], EP2[1], color='#8a6d00', alpha=0.10, zorder=0)
    ax.annotate('2º episódio\n(~meia-noite local)',
                xy=(EP2[0], topo), xytext=(4, -10), textcoords='offset points',
                fontsize=8, va='top', color='#8a6d00')

    # relatos individuais, no eixo do tempo
    for r in RELATOS:
        ax.plot([r['ini']], [topo], marker='v', ms=7, mfc='#ff2020',
                mec='#000000', mew=0.8, clip_on=False, zorder=6)

    ax.set_ylabel('Temperatura de brilho mínima (°C)')
    ax.set_xlabel('Tempo (UTC)')
    ax.grid(color='#00000018', lw=0.5)
    ax.set_title('GOES-19: topos frios e atividade elétrica — 29–30/08/2026', fontsize=12)

    # Folga embaixo e legenda a direita: no canto inferior esquerdo ela cobria
    # justamente o minimo de -62.9 C sobre o norte da Ilha, as 22:20Z.
    minimos = [r['min_d03'] for r in registros] + [r['min_norte'] for r in registros]
    ax.set_ylim(bottom=min(minimos) - 8)

    l1, r1 = ax.get_legend_handles_labels()
    l2, r2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, r1 + r2, loc='lower right', fontsize=8, framealpha=0.9)

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(destino, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"resumo -> {os.path.basename(destino)}")


def resumo_do_csv():
    """
    Redesenha resumo_evento.png a partir do CSV ja gravado. Serve para iterar
    no grafico sem rebaixar as dezenas de varreduras que o alimentaram.
    """
    caminho = os.path.join(SAIDA, 'resumo_evento.csv')
    registros = []
    with open(caminho, encoding='utf-8') as f:
        next(f)
        for linha in f:
            utc, d03, norte, flashes, btd, pos = linha.strip().split(',')
            registros.append({
                'quando': dt.datetime.strptime(utc, '%Y-%m-%dT%H:%MZ'),
                'min_d03': float(d03),
                'min_norte': float(norte),
                'flashes': int(flashes),
                'btd_max_anvil': float(btd),
                'btd_pos_anvil': int(pos),
            })
    resumo_evento(registros, os.path.join(SAIDA, 'resumo_evento.png'))
    print(f"{len(registros)} registros lidos de {os.path.basename(caminho)}")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'resumo':
        resumo_do_csv()
        return

    limite = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    os.makedirs(SAIDA, exist_ok=True)
    lons = np.arange(LON_MIN, LON_MAX + PASSO / 2, PASSO)
    lats = np.arange(LAT_MAX, LAT_MIN - PASSO / 2, -PASSO)

    municipios = gpd.read_file(SHP_MUN).to_crs(4326).cx[LON_MIN:LON_MAX, LAT_MIN:LAT_MAX]
    cmap_p, norm_p = escala_ir()
    cmap_c, norm_c = escala_contraste()

    fs = s3fs.S3FileSystem(anon=True)
    c13 = listar_abi(fs, INICIO, FIM, 'C13')
    c15 = listar_abi(fs, INICIO, FIM, 'C15')
    momentos = sorted(c13)
    if limite:
        momentos = momentos[:limite]
    print(f"{len(momentos)} varreduras entre {INICIO:%d/%m %H:%M} e {FIM:%d/%m %H:%M} UTC")
    print(f"grade {lons.size}x{lats.size} | {len(municipios)} municipios no recorte")

    registros = []
    for i, quando in enumerate(momentos, 1):
        dst_p = os.path.join(SAIDA, f"goes19_c13_{quando:%Y%m%d_%H%M}z.png")
        dst_c = os.path.join(SAIDA, f"goes19_contraste_{quando:%Y%m%d_%H%M}z.png")
        dst_s = os.path.join(SAIDA, f"goes19_split_{quando:%Y%m%d_%H%M}z.png")

        temp_c = campo(fs, c13[quando], lons, lats)

        if not os.path.exists(dst_p):
            desenhar_padrao(temp_c, lons, lats, quando, municipios, cmap_p, norm_p, dst_p)

        flashes = raios_glm(fs, quando, quando + dt.timedelta(minutes=10))
        if not os.path.exists(dst_c):
            desenhar_contraste(temp_c, lons, lats, quando, municipios, cmap_c, norm_c,
                               flashes, dst_c)

        btd = None
        if quando in c15:
            btd = campo(fs, c15[quando], lons, lats) - temp_c
            if not os.path.exists(dst_s):
                desenhar_split(btd, temp_c, lons, lats, quando, municipios, dst_s)

        # recorte do norte da Ilha na grade de saida
        jn = (lats <= NORTE_LAT[1]) & (lats >= NORTE_LAT[0])
        inn = (lons >= NORTE_LON[0]) & (lons <= NORTE_LON[1])

        # split-window so faz sentido onde ha topo espesso e frio
        anvil = temp_c <= ANVIL_C
        if btd is not None and anvil.any():
            btd_max = float(btd[anvil].max())
            btd_pos = int((btd[anvil] > 0).sum())
        else:
            btd_max, btd_pos = float('nan'), 0

        registros.append({
            'quando': quando,
            'min_d03': float(temp_c.min()),
            'min_norte': float(temp_c[np.ix_(jn, inn)].min()),
            'flashes': len(flashes),
            'btd_max_anvil': btd_max,
            'btd_pos_anvil': btd_pos,
        })

        print(f"  [{i}/{len(momentos)}] {quando:%H:%M}z  min {temp_c.min():6.1f} C  "
              f"norte {registros[-1]['min_norte']:6.1f} C  GLM {len(flashes):4d}  "
              f"BTD max {btd_max:+.2f} K ({btd_pos} px > 0)")

    resumo_evento(registros, os.path.join(SAIDA, 'resumo_evento.png'))
    with open(os.path.join(SAIDA, 'resumo_evento.csv'), 'w', encoding='utf-8') as f:
        f.write('utc,min_d03_C,min_norte_ilha_C,flashes_glm_10min,'
                'btd_max_anvil_K,btd_pos_anvil_px\n')
        for r in registros:
            f.write(f"{r['quando']:%Y-%m-%dT%H:%M}Z,{r['min_d03']:.1f},"
                    f"{r['min_norte']:.1f},{r['flashes']},"
                    f"{r['btd_max_anvil']:.2f},{r['btd_pos_anvil']}\n")


if __name__ == '__main__':
    main()
