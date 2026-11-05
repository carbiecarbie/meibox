R36S Diagnostics - 0.1.2
=======================

Ferramenta local para o R36S com dArkOSRE. Python 3 e biblioteca padrao,
dialog e gptokeyb ja presentes no sistema. Nao precisa instalar pacotes.

NO APARELHO
No menu Options/Opcoes do EmulationStation, abra "R36S Diagnostics".
Direcional: escolher e rolar. A/START: abrir/voltar da pagina.
SELECT: voltar/sair. B tambem volta quando o launcher inicia seu proprio
gptokeyb; um helper compartilhado pode usar o mapeamento original do OS.
L1/R1: rolar paginas. As leituras se atualizam ao abrir cada tela.

Telas: resumo; rede e USB; CPU, memoria e bateria; espaco do cartao;
salvar relatorio JSON/TXT; sobre e limitacoes.

Salvar cria dois arquivos privados em:
/home/ark/.local/share/r36s-diagnostics/reports/
O relatorio inclui IP/SSID e dados do sistema, sem senhas de Wi-Fi.
Datas dos arquivos e da coleta em UTC. Pode ser copiado por SSH/SFTP.

ARQUITETURA
src/r36s_diagnostics.py: coleta, interface dialog e CLI.
device-launcher.sh: launcher instalado com o nome launcher.sh; trava contra
instancias duplicadas, inicia helper se necessario e encerra somente o seu.
keys.gptk: mapeamento de botoes proprio.
state/: trava de instancia, log da ultima abertura e runtime privado de
reserva. Nao depende da existencia de uma sessao SSH em /run/user/1000.
menu-entry.sh: atalho instalado em /opt/system/R36S Diagnostics.sh.
docs/system-survey.json: primeira coleta do aparelho.
docs/system-inventory.json: inventario complementar e hashes de boot.
docs/levantamento.txt: mapa do sistema e pontos de extensao.
artifacts/: recibos de instalacao e verificacoes locais (ignorado pelo Git).

A ferramenta consulta /proc, /sys, ip, nmcli e systemctl. Nao troca modo
USB, instala driver, conecta rede, muda volume/fonte ou atualiza o OS.
A lista Wi-Fi usa o cache do NetworkManager (--rescan no). "Conectado"
exige estado 100 do NetworkManager e endereco IPv4. Internet nao e testada.
USB distingue controlador interno, Realtek DISK 0bda:1a2b e NIC 0bda:c820.
Sensores sao identificados pelo nome; soc-thermal nao e temperatura da
bateria. Tensao em V e corrente em mA, convertidas das unidades do kernel.
Somente montagens reais sao contadas; /roms2 vazio nao vira segundo cartao.

DESENVOLVIMENTO
Na raiz do projeto (Linux, macOS ou WSL):
  python3 -m unittest discover -s tests -v
  bash -n device-launcher.sh menu-entry.sh

Para implantar com scripts/device.py, e preciso um SSH master autenticado
no socket /tmp/r36s-diag-dev-ssh, para o aparelho em R36S_HOST
(ex.: ark@192.168.0.50). R36S_KNOWN_HOSTS fixa a chave de host (opcional).
A senha e solicitada pelo SSH ao abrir o master; nao e salva no codigo.
  export R36S_HOST=ark@<ip-do-aparelho>
  ssh -M -N -f -o ControlPath=/tmp/r36s-diag-dev-ssh -o ControlPersist=600 "$R36S_HOST"
  python3 scripts/device.py deploy
  python3 scripts/device.py survey

Deploy grava so os quatro arquivos proprios, confere SHA256 e guarda a
versao anterior de um arquivo alterado como .previous. Recusa um atalho
existente que nao perteneca a este aplicativo. Nao altera es_systems.cfg.

CLI via SSH, no aparelho:
  python3 /home/ark/.local/share/r36s-diagnostics/r36s_diagnostics.py --json
  python3 /home/ark/.local/share/r36s-diagnostics/r36s_diagnostics.py --section all
  python3 /home/ark/.local/share/r36s-diagnostics/r36s_diagnostics.py --save

VERIFICACAO
tests/test_diagnostics.py cobre desconexao com IP residual, escaping de
SSID, falta de hardware/comandos, modos USB Realtek, sensores, unidades,
exportacao e permissoes dos relatorios.
tests/device_ui_smoke.py executa o dialog real em PTY 24x64 no R36S,
abre todas as telas e confere os dois arquivos exportados.
tests/device_launcher_smoke.py abre brevemente o atalho na tty1, le a tela
do console e confere inicio/limpeza do helper. Para e restaura o servico
EmulationStation; executar apenas quando nenhum jogo estiver em uso.
Esse teste passa XDG_RUNTIME_DIR apontando para uma pasta inexistente,
reproduzindo a falha observada ao abrir pelo menu depois de encerrar SSH.
Os testes automatizados nao substituem pressionar os botoes fisicos.

REMOCAO
Para retirar do menu, basta remover o arquivo exato:
/opt/system/R36S Diagnostics.sh
O payload e os relatorios permanecem em ~/.local/share/r36s-diagnostics.
Nao precisa restaurar nenhum arquivo original do sistema.
