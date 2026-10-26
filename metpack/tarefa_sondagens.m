%% Tarefa de sondagens - versão MATLAB (MATLAB Online ou instalado)
% Baseado nos programas de Kerry Emanuel em https://texmex.mit.edu/pub/emanuel/soundings/
% (getsounding.m, skewt.m, tcon.m e wyoming.f), adaptados para a interface atual do Wyoming:
%   getsounding_wyoming.m  - baixa a sondagem e grava sounding.txt para o wyoming.f
%   skewt.m                - diagrama Skew-T de Emanuel: skewt(p, T, UR 0-1)
%   figuras_sondagem.m     - Skew-T com barbelas (windbarb.m), hodógrafo com Bunkers e perfis de
%                            estabilidade (thermo_td.m)
%   tcon_emanuel.m         - calcula e desenha as matrizes de flutuabilidade (como o tcon.m)
%   wyoming_emanuel.m      - tradução em MATLAB do wyoming.f (não precisa de compilador Fortran)
%
% Como usar no MATLAB Online (https://matlab.mathworks.com):
%   1. Envie a pasta metpack do repositório para o MATLAB Drive (ou use "Open in MATLAB Online").
%   2. Abra este arquivo, troque as três sondagens em CASOS pelas SUAS (estação e data) e clique em Run.
%   3. Para cada caso saem: o Skew-T com barbelas e o hodógrafo (Bunkers LM/RM), os perfis de
%      theta, theta_e, theta_es, N^2 e S até 200 hPa e as matrizes de Emanuel (reversível e pseudoadiabática).
%
% Os casos abaixo são apenas o EXEMPLO do tutorial (Porto Alegre, dezembro de 1995).

clear; close all;

CASOS = {
%   regime        estação   [ano mês dia hora UTC]
    'ESTÁVEL',    83899,    [2026 08 26 12];
    'NEUTRA',     83899,    [2026 08 31 00];
    'INSTÁVEL',   83899,    [2026 08 28 12];
};
CORTE_EMANUEL = false;   % false = sem o piso artificial de -4 K do wyoming.f original

pasta_metpack = fileparts(mfilename('fullpath'));
addpath(pasta_metpack);

for k = 1:size(CASOS, 1)
    regime = CASOS{k, 1};
    est = CASOS{k, 2};
    d = CASOS{k, 3};
    rotulo = sprintf('%s: %d %02d/%02d/%04d %02dZ', regime, est, d(3), d(2), d(1), d(4));
    fprintf('\n=== %s ===\n', rotulo);

    [data, header, status, fonte] = getsounding_wyoming(est, d(1), d(2), d(3), d(4));
    if status ~= 1
        warning('Sem dados para %s; caso ignorado.', rotulo);
        continue
    end

    pasta = sprintf('emanuel_%04d%02d%02d_%02d', d(1), d(2), d(3), d(4));
    if ~exist(pasta, 'dir'), mkdir(pasta); end

    % Skew-T de Emanuel com barbelas e hodógrafo (Bunkers LM/RM); perfis de theta, theta_e,
    % theta_es, N^2 e S até 200 hPa (rotinas do metpack: skewt, windbarb, wswd_to_uv, thermo_td)
    F = figuras_sondagem(data, rotulo, pasta, 200);

    % Matrizes de flutuabilidade de Emanuel (tradução do wyoming.f)
    copyfile('sounding.txt', fullfile(pasta, 'sounding.txt'));
    E = tcon_emanuel(pasta, rotulo, CORTE_EMANUEL);

    [cmax_rev, i_rev] = max(E.cape(:, 6));
    [cmax_pse, i_pse] = max(E.cape(:, 7));
    fprintf('Fonte dos dados: %s\n', fonte);
    fprintf('CAPE reversível na superfície: %.1f J/kg | máxima: %.1f J/kg (origem %.0f hPa)\n', ...
            E.cape(1, 6), cmax_rev, E.cape(i_rev, 1));
    fprintf('CAPE pseudoadiabática na superfície: %.1f J/kg | máxima: %.1f J/kg (origem %.0f hPa)\n', ...
            E.cape(1, 7), cmax_pse, E.cape(i_pse, 1));
    fprintf('Bunkers LM: (%.1f, %.1f) m/s | RM: (%.1f, %.1f) m/s\n', F.bunkers_lm, F.bunkers_rm);
    fprintf('Figuras em %s: skewt_hodografo.png, perfis_estabilidade.png e as matrizes de Emanuel\n', pasta);
end
