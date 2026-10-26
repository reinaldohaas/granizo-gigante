# 🌪️ Diagnóstico de Mesoescala: Caso Granizo Gigante em Florianópolis (28/08/2026)
### Análise Termodinâmica e Cinemática de Três Regimes Troposféricos

**Disciplina:** FSC7116 — Meteorologia de Mesoescala  
**Docente:** Prof. Dr. Reinaldo Haas  
**Instituição:** Universidade Federal de Santa Catarina (UFSC)  
**Público-alvo:** Estudantes de graduação/pós-graduação em Meteorologia e previsores da Defesa Civil de Santa Catarina (DCSC).  
**Tutorial Online (GitHub Pages):** [https://reinaldohaas.github.io/tarefa-meso/](https://reinaldohaas.github.io/tarefa-meso/)  

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/reinaldohaas/tarefa-meso/blob/master/Seminario_plot_sounding_revisado.ipynb)

---

## 📌 O que é a Tarefa

Este repositório é um tutorial prático e reprodutível para análise termodinâmica e cinemática de radiossondagens observadas na América do Sul. A tarefa consiste em diagnosticar comparativamente **três regimes atmosféricos observados distintos**:

1. **Atmosfera Estável:** Perfil com forte estabilidade térmica, estratificação hidrostática estável com $N^2 > 0$ e ausência de convecção profunda *(Florianópolis — SBFL 83899 em 26/08/2026 12Z — SBCAPE: 8.1 J/kg, MUCAPE: 0 J/kg, PW: 27.1 mm)*.
2. **Atmosfera Neutra:** Perfil de transição pós-frontal úmida com flutuabilidade moderada em altitude *(Florianópolis — SBFL 83899 em 31/08/2026 00Z — MUCAPE: 267.1 J/kg, PW: 45.8 mm)*.
3. **Atmosfera Instável:** Ambiente pré-convectivo precursor do temporal severo de granizo gigante, com forte gradiente vertical de $\theta_e$, elevado CAPE e intenso cisalhamento vertical *(Florianópolis — SBFL 83899 em 28/08/2026 12Z — MUCAPE: 1303.5 J/kg, SBCAPE: 442.8 J/kg, PW: 40.9 mm)*.

> **Importante:** os casos de Porto Alegre (dezembro de 1995) são só o **exemplo resolvido**. Cada aluno ou dupla troca as três sondagens pelas suas; presumivelmente, a instável é a mais próxima do evento severo escolhido para o trabalho de fim de curso. Os valores citados devem sair da sua execução.

---

## 📋 Para o Estudante: leia o ROTEIRO

**Todas as instruções estão no [ROTEIRO_ESTUDANTES.md](https://github.com/reinaldohaas/tarefa-meso/blob/master/ROTEIRO_ESTUDANTES.md)**: escolha das sondagens, as três formas de rodar, o que apresentar e os critérios de avaliação.

Resumo das três formas de rodar (detalhes, downloads e comandos no item 3 do ROTEIRO):

| Opção | Onde roda | O que produz |
| :--- | :--- | :--- |
| **A. Notebook Jupyter** — [abrir no Colab](https://colab.research.google.com/github/reinaldohaas/tarefa-meso/blob/master/Seminario_plot_sounding_revisado.ipynb) ou em qualquer IDE com Jupyter (VS Code, JupyterLab, PyCharm…) | Navegador ou seu computador | Tudo: índices do MetPy e conferência com o Wyoming, Skew-T com hodógrafo, perfis até 200 hPa e matrizes de Emanuel |
| **B. Linha de comando com o `uv`** — `metpack/tarefa_sondagens.py` | Seu computador | Skew-T e matrizes de Emanuel |
| **C. MATLAB Online** — `metpack/tarefa_sondagens.m` | Navegador | Skew-T com barbelas, hodógrafo (Bunkers), perfis até 200 hPa e matrizes de Emanuel |

Em todas, troque as três sondagens do exemplo em `CASOS` pelas suas.

---

## 📂 Estrutura de Pastas do Repositório

```text
tarefa-meso/
├── index.html                   # Tutorial didático para web (GitHub Pages)
├── build_index_html.py          # Script gerador do index.html
├── generate_figures.py          # Script que plota todas as figuras científicas
├── generate_pptx.py             # Script gerador da apresentação de 10 slides (PPTX)
├── apresentacao_meso.pptx       # Apresentação oficial para a Defesa Civil de SC
├── ROTEIRO_ESTUDANTES.md        # Roteiro passo a passo com critérios de avaliação
├── Seminario_plot_sounding_revisado.ipynb # Notebook oficial para execução no Google Colab
└── metpack/                     # Módulo de processamento meteorológico
    ├── metricas.json            # Fonte única de verdade de todas as métricas calculadas
    ├── calc_metricas.py         # Script que calcula métricas e grava o metricas.json
    ├── metricas_notebook.json   # Valores gravados pelo notebook (fonte dos números do site e dos slides)
    ├── wyoming.f                # Programa de Kerry Emanuel (Fortran 77) para parcelas e CAPE
    ├── tarefa_sondagens.py / .m # Script principal em Python / MATLAB (troque CASOS pelas suas sondagens)
    ├── getsounding_wyoming.py / .m  # Baixa a sondagem do Wyoming e grava o sounding.txt do wyoming.f
    ├── tcon_emanuel.py / .m     # Roda o wyoming.f e desenha as matrizes de flutuabilidade
    ├── wyoming_emanuel.m        # Tradução do wyoming.f para MATLAB (MATLAB Online, sem Fortran)
    ├── wyoming.py               # Tradução do wyoming.f para Python (Opção B sem gfortran)
    ├── figuras_sondagem.m       # MATLAB: Skew-T com barbelas, hodógrafo (Bunkers) e perfis de estabilidade
    ├── skewt.py / skewt.m       # Diagrama Skew-T de Emanuel
    ├── getsounding.m, tcon.m    # Originais de Kerry Emanuel (texmex.mit.edu), só como referência
    ├── sounding_*_12Z.txt, indices_*_12Z.txt  # Cópias das sondagens do exemplo (Wyoming)
    ├── *.m (thermo_*, brunt_*, ...)  # Rotinas auxiliares de termodinâmica em MATLAB (ver Leiame.txt)
    └── *.png                    # Figuras do site e dos slides
```

---

## 🛠️ Como rodar

Veja o **[ROTEIRO_ESTUDANTES.md](https://github.com/reinaldohaas/tarefa-meso/blob/master/ROTEIRO_ESTUDANTES.md)**, item 3: as três formas de rodar (notebook no Colab ou em IDE com Jupyter, linha de comando com o `uv` e MATLAB Online), com o que instalar e os comandos.

Para rodar no seu computador (opções A2 e B) ou enviar a pasta `metpack/` ao MATLAB Online (opção C), baixe antes o repositório:
```bash
git clone https://github.com/reinaldohaas/tarefa-meso.git
```
ou, no GitHub, **Code → Download ZIP**. (O endereço `https://reinaldohaas.github.io/tarefa-meso/` é só o tutorial na web; não serve para o `git clone`.)

---

## 📚 Referências Bibliográficas

- **Emanuel, K. A. (1994):** *Atmospheric Convection*. Oxford University Press, 580 pp.
- **Bunkers, M. J. et al. (2000):** *Predicting Supercell Motion Using a New Hodograph Technique*. Weather and Forecasting, 15(1), 61–79.
- **Markowski, P. & Richardson, Y. (2010):** *Mesoscale Meteorology in Midlatitudes*. Wiley-Blackwell.
- **Thompson, R. L. et al. (2003, 2012):** *Close proximity soundings within supercell environments*. Weather and Forecasting.
- **Weisman, M. L. & Klemp, J. B. (1982):** *The dependence of numerically simulated convective storms on vertical wind shear and buoyancy*. MWR.
- **University of Wyoming:** *Department of Atmospheric Science Radiosonde Archive*.
