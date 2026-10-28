# granizo-gigante

Análise do granizo de 29 de agosto de 2026 em Santa Catarina: madrugada no Oeste, manhã no Meio-Oeste e
fim de tarde na Grande Florianópolis, com pedras de até ~6 cm em Biguaçu.

A página interativa é o [`index.html`](index.html) (GitHub Pages): mapa com as trajetórias das células
desde a Argentina e o extremo-oeste, relatos × passagem das células, a célula da Ilha no satélite, a
simulação com o WRF e os ensembles, aerossol e clima espacial na semana anterior, e a lista de testes e
ressalvas.

## Perguntas

1. De onde vieram as células que deram granizo do oeste ao litoral, e como andaram pelo estado?
2. O ambiente estava dentro da raridade ou faz parte de um clima com mais vapor e menos aerossol?
3. A atividade solar anômala dos dias anteriores deixou o ambiente com Jz alto?

## Conteúdo

| Pasta | O que tem |
|---|---|
| `satelite/` | Rastreio das células pelos raios do GLM (GOES-19): download (`glm_estado.py`), trajetórias (`glm_trajetorias.py`), cruzamento com os relatos (`glm_relatos.py`) e figura (`fig_trajetorias_episodios.py`); série GOES-19 e GLM sobre a Ilha (`resumo_evento.csv`) e os scripts que a geram |
| `radar/` | MaxCAPPI do DECEA/REDEMET (`baixar_redemet.py`, chave em variável de ambiente), mosaico Santiago + Morro da Igreja (`trajetoria_estado.py`), comparação WRF × radar e resumo dos ensembles, objetos do WRF d02 |
| `clima_espacial/` | Kp, Dst, Ey, AE, nêutrons (Oulu, Dome C), AOD (CAMS e MERRA-2, com climatologia de agosto 1980–2026), Jz da rede de magnetômetros e a figura da semana anterior |
| `apresentacao/` | Gerador da página (`build_index.py` + `index_modelo.html`) |

A visualização 3D da supercélula está em [reinaldohaas/granizo_gigante](https://github.com/reinaldohaas/granizo_gigante).
A tarefa da disciplina (sondagens, Emanuel, teste do WRF pelos alunos) está em
[reinaldohaas/tarefa-meso](https://github.com/reinaldohaas/tarefa-meso).

## Como reproduzir

Os scripts foram escritos para rodar dentro do projeto `C:\gis4wrf\projects\Floripa`, onde estão os
`wrfout`, os shapefiles do IBGE e os dados brutos. Ficaram fora deste repositório, por tamanho, e se refazem
pelos scripts: os flashes brutos do GLM, as imagens do GOES-19, os quadros do radar, os arquivos dos
magnetômetros e do CAMS.

Credenciais (nenhuma está no repositório): Copernicus ADS em `~/.adsapirc`, Earthdata no netrc (no
Windows o `earthaccess` lê `~/_netrc` ou o arquivo da variável `NETRC`) e `REDEMET_KEY` no ambiente.

## Ressalvas

- O rastreio por raios segue células eletricamente ativas; os limiares (5 flashes por cela de 0,1° em
  10 min, 45 km entre intervalos, trajetórias de 1 h ou mais) são escolhas.
- Os horários do oeste vêm de "madrugada de 29/08" nas reportagens: a coincidência com as trajetórias é de
  lugar e horário, não de medição de granizo.
- O Jz da rede é corrente ionosférica equivalente, em nA/m², e a rede de 2026 não tem MED, SMS, TCM e EUS.
- O domínio de 3 km do WRF começa em ~51°W: o modelo, como está, não simula as células do oeste.
- É um único evento; coincidências no tempo não provam causa.
