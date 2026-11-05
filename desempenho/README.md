# r36s-perf

Otimização de desempenho de um R36S (RK3326) com dArkOSRE para Super Nintendo,
Mega Drive e Game Boy Advance. Tudo foi medido no próprio aparelho, e cada
mudança tem como ser desfeita.

**Resultado:** veja [`results/RELATORIO-FINAL.md`](results/RELATORIO-FINAL.md).
Nos 27 jogos mais pesados medidos, os que não seguravam 60 fps caíram de 5
para 0.

## O que tem aqui

| Pasta | Conteúdo |
|---|---|
| `results/` | Relatórios por camada (`L0.md` a `L6.md`), relatório final e `manifest.jsonl` (todas as mudanças, com o comando para desfazer) |
| `device/bench/` | O que roda no aparelho: teste de velocidade, criação de savestates por roteiro de botões, troca de emulador por jogo, varredura de chips |
| `device/build/` | Compilação dos cores no aparelho (-O2, -O3, PGO) |
| `device/overrides/` | Configurações por core e por jogo do RetroArch (thread de vídeo) |
| `device/undo-all.sh` | Desfaz todas as mudanças no aparelho |
| `scripts/` | O que roda no PC: `bench_run.py` (roda uma lista de testes por SSH) |
| `jobs/` | Listas de testes e roteiros de botões usados em cada rodada |

## Como funciona o teste de velocidade

1. `device/bench/nav.py` abre o jogo em tempo real, aperta botões por rede
   (roteiro em `jobs/nav-*.json`) até uma cena pesada e salva um savestate.
2. `device/bench/bench.sh` abre o jogo sem limite de velocidade a partir
   desse savestate e marca o tempo nos quadros 120 e 1920.
3. `scripts/bench_run.py jobs/<lista>.json --tag <nome>` roda tudo pelo PC,
   com o EmulationStation parado, e grava `results/<data>-<nome>-resumo.json`.

## Rodar os testes de velocidade

No PC, com o aparelho acessível por SSH:

```bash
R36S_HOST=ark@<ip-do-aparelho> python scripts/bench_run.py jobs/validacao.json --tag teste
```

`R36S_SSH_KEY` e `R36S_KNOWN_HOSTS` (opcionais) escolhem a chave e fixam a chave de host.
`scripts/r36` é um atalho de SSH/SCP com as mesmas variáveis.

O código-fonte dos cores (snes9x, mgba, gpsp) não vem junto: cada um tem a sua licença.
`device/build/build-core.sh` espera os pacotes em `~/.local/share/r36s-perf/build/src/` no
aparelho, baixados dos repositórios oficiais do libretro nos commits citados em `results/L4.md`.
Também não vêm junto as capturas de tela, as varreduras da biblioteca e as medições brutas.
