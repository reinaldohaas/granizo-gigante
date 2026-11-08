# -*- coding: utf-8 -*-
"""Gera apresentacao/testes.html: todos os testes do granizo de 29/08/2026, o estado de cada pergunta e o plano.

Le as tabelas das analises e embute tudo num unico arquivo:
  ambiente/isoterma_resumo.csv, isoterma_anual.csv, isoterma_dias_biguacu.csv, isoterma_texto.html
  radar/oeste_o1_vs_relatos.csv, radar/figuras/oeste_o1_hailcast.png, radar/figuras/d01_kf_vs_gf.png
Saidas: apresentacao/testes.html (documento completo) e testes_artifact.html (so o corpo, para o Artifact).

Uso: python apresentacao/build_testes.py
"""
import base64
import io
import json
import os

import pandas as pd
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(AQUI, '..')


def caminho(*a):
    return os.path.join(P, *a)


def jpeg(arq, largura=1500):
    im = Image.open(arq).convert('RGB')
    if im.width > largura:
        im = im.resize((largura, int(im.height * largura / im.width)), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, 'JPEG', quality=84, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()


def main():
    d = {}
    o1 = pd.read_csv(caminho('radar', 'oeste_o1_vs_relatos.csv'))
    d['o1'] = o1.where(o1.notna(), None).to_dict(orient='records')
    texto = '<p class="vazio">Resultado do ERA5 ainda não processado.</p>'
    if os.path.exists(caminho('ambiente', 'isoterma_resumo.csv')):
        r = pd.read_csv(caminho('ambiente', 'isoterma_resumo.csv'))
        d['iso_resumo'] = r.to_dict(orient='records')
        an = pd.read_csv(caminho('ambiente', 'isoterma_anual.csv'))
        d['iso_anual'] = [{'lugar': l, 'ano': g.ano.tolist(), 'iso': g.isoterma0_m.round(0).tolist()}
                          for l, g in an.groupby('lugar', sort=False)]
        dias = pd.read_csv(caminho('ambiente', 'isoterma_dias_biguacu.csv'))
        ev = r[r.lugar.str.startswith('Grande')].iloc[0]
        d['iso_hist'] = {'valores': dias.isoterma0_m.round(0).tolist(), 'evento': float(ev.isoterma0_m),
                         'lugar': 'Biguaçu', 'hora': '21 UTC'}
        arq_txt = caminho('ambiente', 'isoterma_texto.html')
        if os.path.exists(arq_txt):
            texto = open(arq_txt, encoding='utf-8').read()

    modelo = open(os.path.join(AQUI, 'testes_modelo.html'), encoding='utf-8').read()
    html = modelo.replace('/*__DADOS__*/{}', json.dumps(d, ensure_ascii=False, separators=(',', ':')))
    html = html.replace('__TEXTO_ISOTERMA__', texto)
    selo = '<span class="estado" style="--c:var({})">{}</span>'
    fum = {'texto': 'climatologia diária ainda não processada', 'sentido': 'NEUTRO'}
    arq_f = caminho('clima_espacial', 'resultados', 'fumaca_resumo.json')
    if os.path.exists(arq_f):
        fum = json.load(open(arq_f, encoding='utf-8'))
    html = html.replace('__FUMACA__', fum['texto']).replace('__FUMACA_SENTIDO__', '__' + fum['sentido'] + '__')
    html = (html.replace('__CONTRA__', selo.format('--nao', 'contra'))
                .replace('__FAVOR__', selo.format('--sim', 'a favor'))
                .replace('__NEUTRO__', selo.format('--aberto', 'neutro')))
    html = html.replace('__IMG_O1__', jpeg(caminho('radar', 'figuras', 'oeste_o1_hailcast.png')))
    html = html.replace('__IMG_KFGF__', jpeg(caminho('radar', 'figuras', 'd01_kf_vs_gf.png')))
    html = html.replace('__IMG_ROSENFELD__', jpeg(caminho('radar', 'figuras', 'rosenfeld_resumo.png'), 1000))
    with open(os.path.join(AQUI, 'testes_artifact.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    doc = ('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n</head>\n<body>\n'
           + html + '\n</body>\n</html>\n')
    with open(os.path.join(AQUI, 'testes.html'), 'w', encoding='utf-8') as f:
        f.write(doc)
    print('->', os.path.join(AQUI, 'testes.html'), f'{len(doc) / 1e6:.2f} MB')


if __name__ == '__main__':
    main()
