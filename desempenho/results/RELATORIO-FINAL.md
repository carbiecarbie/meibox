# Relatório final: otimização do R36S (SNES, Mega Drive, GBA)

Período: 03 e 04/11/2026. Aparelho: R36S, RK3326 (4× Cortex-A35 a 1512 MHz),
895 MiB de RAM, dArkOSRE R36 (Debian 13), kernel 4.4.189.

## Resultado em uma frase

Nos 27 jogos medidos, escolhidos entre os mais pesados da biblioteca, o
número de jogos que **não seguravam 60 fps caiu de 5 para 0**, e quase todos
os jogos leves de Mega Drive, SNES e GBA passaram a responder ao botão **um
quadro mais rápido** (~16 ms).

## Como foi medido

- Velocidade "sem limite" (vsync e sincronia de áudio desligados) a partir de
  um savestate de uma cena pesada de cada jogo: fps = 1800 quadros / tempo.
  Mediana de 3 rodadas, CPU/GPU/RAM no máximo (o mesmo que o ES usa no jogo).
- O número mostra a **folga**: o jogo continua rodando a 60, mas um jogo que
  faz 75 sem limite segura 60 nas partes pesadas, e um que faz 58 engasga.
  Regra de conforto usada: 66 fps (10% acima de 60).
- Fidelidade: captura do quadro 1920 de cada cena comparada pixel a pixel
  (PSNR) ou a olho, quando os emuladores chegam a quadros diferentes.
- Detalhes do método em `L0.md`; ferramentas em `device/bench/` e
  `scripts/bench_run.py`.

## Ganho por plataforma

| Plataforma | Ganho típico | De onde veio |
|---|---|---|
| GBA | +11% a +16% em qualquer jogo; +55% a +280% nos pesados que trocaram de emulador | mgba recompilado com PGO; gpsp novo nos 3D pesados |
| SNES | média de +24% (de +3% a +52%) | snes9x recompilado com PGO; emulador próprio nos jogos Super FX |
| Mega Drive | 0% em velocidade | já tinha folga de 50% a 180%; ganhou só a resposta mais rápida do botão |

Médias dos jogos medidos antes e depois: SNES +24% (6 jogos); GBA +86%
(5 jogos, puxada pelo F-Zero; mediana +55%, sem o F-Zero +36%).

## Jogos que seguram 60

| Situação (27 jogos medidos) | Antes | Agora |
|---|---:|---:|
| Abaixo de 60 (engasga) | 5 | 0 |
| Entre 60 e 66 (sem folga) | 3 | 1 |
| Acima de 66 (com folga) | 19 | 26 |

Antes abaixo de 60: Doom (SNES), Vortex, Dirt Racer (nem funcionava), Super
Monkey Ball Jr. e Street Racing Syndicate (os dois últimos estimados a partir
do mgba novo). O único ainda sem folga é o Street Racing Syndicate (64,9).

## Melhores casos

| Jogo | Antes | Agora | Mudança |
|---|---:|---:|---|
| F-Zero GP Legend (GBA) | 70,0 | 268,1 | gpsp novo |
| Super Monkey Ball Jr. (GBA) | 61,6\* | 289,6 | gpsp |
| Doom II (GBA) | 73,7 | 121,5 | gpsp novo |
| Duke Nukem Advance (GBA) | 69,5 | 107,7 | gpsp novo |
| Vortex (SNES) | 54,2\* | 82,4 | supafaust |
| Star Fox (SNES) | 63,1 | 95,6 | supafaust |
| Doom (SNES) | 58,0\* | 79,0 | chimerasnes |
| Dirt Racer (SNES, 50 Hz) | não funcionava | 54,0 | supafaust |

\* "Antes" já com o core recompilado; o ganho sobre o de fábrica é maior.

## Casos que menos mudaram

| Jogo | Antes | Agora | Motivo |
|---|---:|---:|---|
| Super Mario RPG (SNES) | 72,7 | 75,0 | só a recompilação ajudou |
| Kirby Super Star (SNES) | 72,7 | 80,2 | idem |
| NFS Carbon (GBA) | 65,4 | 73,0 | fica no mgba (suspeita de erro no HUD do gpsp) |
| Golden Sun (GBA) | 122,1 | 139,1 | já era leve |
| Mega Drive inteiro | 91–168 | igual | já tinha folga |

## O que foi aplicado no aparelho

Todas as mudanças estão em `manifest.jsonl`, cada uma com o comando para
desfazer. Para desfazer tudo: `device/undo-all.sh` (ver abaixo).

| Camada | Mudança | Relatório |
|---|---|---|
| L0 | Proteção de tela do ES: vídeo aleatório → tela preta (aquecia à toa) | `L0.md` |
| L1 | Samba desligado; timers do apt e de verificação de disco desligados; escalonador do cartão cfq → deadline. Sem ganho de fps, menos interrupção no meio do jogo | `L1.md` |
| L2 | Vídeo sem thread por padrão em Genesis Plus GX, Snes9x, mGBA e gpSP; com thread no Sega CD, em 36 jogos de SNES com chip e em 102 jogos de GBA pesados (143 overrides) | `L2.md` |
| L3 | Emulador por jogo no `gamelist.xml`: Star Fox, Vortex, Dirt Racer e família Star Fox → supafaust; Stunt Race FX e Doom (SNES) → chimerasnes; Doom II, Duke, F-Zero GP Legend e Super Monkey Ball Jr. → gpsp | `L3.md` |
| L4 | Cores padrão trocados: snes9x e mgba recompilados no aparelho com PGO (GCC 12, `-mcpu=cortex-a35`); gpsp atualizado para o upstream de 2026 (53 correções, -O3); `g++-12` instalado para compilar | `L4.md` |

## O que foi testado e não ficou

- **Afinidade de CPU e nice** (L1): nenhum ganho acima do ruído.
- **Trocar o resampler de áudio** (L2): nada; desligar o áudio inteiro ganha
  só ~2%.
- **Compilar com -O3 sem PGO** (L4): ganha em alguns jogos e perde em
  outros (Star Fox −6%). O PGO ganhou de todas as versões em todos os jogos.
- **Outros emuladores de GBA** (vba_next, vbam): mais lentos que o mgba.
- **retroarch32 / cores de 32 bits**: não ganham de nenhum core de 64 bits de
  mesma qualidade.
- **Overclock** (L6): a CPU já está no teto real do chip (1512 MHz; 1,6 GHz
  exige 1,50 V e trava quente). A RAM a 924 MHz daria ~2–5% em jogos que já
  seguram 60, com risco de corromper saves sem aviso (o aparelho não tem
  ECC). Decisão: não aplicar. Levantamento em `L6.md`.

## Pendências (não bloqueiam nada)

- Ouvir o som do Super Monkey Ball Jr. no gpsp (o do Doom II foi aprovado).
- Winter Gold, Tokyo Xtreme Racer, Top Gear Rally e NFS Underground 2 não
  foram medidos: o roteiro de botões parou no menu. NFS Underground 2 usa o
  mesmo motor do Underground (76 fps).
- Star Fox 2 e as versões europeias do Star Fox foram para o supafaust por
  analogia, sem medição própria.
- L5 (EmulationStation mais leve) não foi feita. Ela não muda o fps dos jogos;
  afeta o menu, o tempo de abrir o jogo e a memória livre (o ES ocupa de 138
  a ~296 MB depois de horas).

## Como desfazer

No aparelho:

```bash
~/.local/share/r36s-perf/undo-all.sh -n        # mostra o que faria
~/.local/share/r36s-perf/undo-all.sh           # desfaz L0 a L4
~/.local/share/r36s-perf/undo-all.sh --limpar  # também tira g++-12, a pasta do projeto e a chave SSH
```

Última garantia: o snapshot btrfs `/.snapshots/00-inicial`, feito antes de
qualquer mudança, e a cópia do `/boot` em `backups/boot-00-inicial/`.

## Números para os próximos projetos

- CPU nos jogos pesados: 68–73 °C, sem throttling (o governador térmico liga
  em 70 °C e mira 85 °C).
- Jogos leves usam uma fração pequena da CPU (Minish Cap roda a 339 fps sem
  limite, ou seja, ~18% do tempo de quadro).
- Memória: 895 MiB sem swap; o ES ocupa 138 MB ao ligar.
