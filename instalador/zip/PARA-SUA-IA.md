# Para a sua IA instalar o Meibox

**Se você é a pessoa:** conecte o R36S no Wi-Fi e diga ao seu assistente de IA (Claude Code, Codex ou parecido):
*"Leia o arquivo PARA-SUA-IA.md desta pasta e instale o Meibox no meu R36S."*
Ele vai explicar cada passo e pedir a sua confirmação antes de mudar alguma coisa.

**If you are the person:** connect the R36S to Wi-Fi and tell your AI assistant: *"Read PARA-SUA-IA.md in this folder and install Meibox on my R36S."*

---

## Instruções para o assistente

Você vai instalar o **Meibox** (tela de início) e, se a pessoa quiser, os **jogos mais rápidos** (emuladores recompilados e ajustes de vídeo por jogo) e o **Copiloto da Mei** (dicas de IA durante o jogo) num R36S, pela rede local, via SSH. Os arquivos estão nesta pasta: `tools/` e `totobox/`. O instalador é `totobox/instalador/instalar.sh`. Leia esse arquivo antes de começar: ele diz exatamente o que muda no aparelho.

Fale com a pessoa na língua dela (as instruções aqui estão em português; os comandos valem para qualquer língua). Use palavras simples. Muita gente nunca usou um terminal. Antes de cada passo, diga o que vai fazer e por quê.

### Regras

1. **A chave de API é da pessoa e não passa por você.** Nunca peça para ela colar a chave no chat. Depois que ela colar a chave em `totobox/chave-da-ia.txt`, não abra, não leia e não imprima esse arquivo. Também não leia nada em `~/.config/mei-copiloto/chaves/` no aparelho. Para saber se há uma chave, use `python3 -I totobox/instalador/chave.py ler <arquivo>`: ele mostra só o fornecedor (`openai` ou `anthropic`).
2. **Peça OK antes de mudar qualquer coisa no aparelho.** Rode `--conferir` primeiro e mostre o resultado.
3. **Só faça o que o instalador faz.** Não mexa em boot, kernel, Wi-Fi, senhas nem pacotes do sistema, e não desligue proteções.
4. **Se algo falhar, pare.** Mostre as últimas linhas de `/roms/totobox/instalador/ultimo-log.txt` e explique. Não tente consertos por conta própria no sistema.
5. **Não varra a rede** procurando o aparelho. Pergunte o IP para a pessoa.

### 1. O que a pessoa faz no aparelho

- Confirme que o sistema é **dArkOS** ou **ArkOS**. O Meibox não funciona em ROCKNIX, AmberELEC nem Knulli.
- Ligar o Wi-Fi: o R36S precisa de um **adaptador Wi-Fi USB**. Ela conecta pelo menu **Options › Wifi**.
- Ligar o acesso pela rede: **Options › Enable Remote Services**.
- Descobrir o IP: **Options › Network Info**. É um número como `192.168.0.50`. Nos comandos abaixo, `IP` é esse número.
- Usuário `ark`, senha padrão `ark`.

### 2. Acesso SSH sem senha

Você não consegue digitar senhas. Por isso, a pessoa instala uma chave SSH sua uma única vez:

- Se ainda não houver chave no computador, você pode criar uma: `ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519`.
- **A pessoa roda o comando abaixo no terminal dela** e digita `ark` quando ele pedir a senha:
  - Windows (PowerShell):
    `Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | ssh -o StrictHostKeyChecking=accept-new ark@IP "umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys"`
  - macOS / Linux: `ssh-copy-id ark@IP`
- Teste: `ssh -o BatchMode=yes ark@IP true`.

### 3. Chave da IA (só se a pessoa quiser o copiloto)

Explique que o copiloto é opcional. Ele custa uma fração de centavo por dica e precisa de uma chave da OpenAI (`sk-...`) ou da Anthropic (`sk-ant-...`).

Se ela quiser, peça para **ela mesma** abrir o arquivo `totobox/chave-da-ia.txt` **desta pasta** num editor de texto, colar a chave na linha em branco e salvar. Você não abre o arquivo. Depois confira só o fornecedor com `chave.py ler`, como explicado nas regras.

Se ela não quiser o copiloto, pule este passo. O arquivo fica como está.

### 4. Copiar para o aparelho

Nesta pasta, rode:

```
scp -r tools totobox ark@IP:/roms/
```

Esse comando junta as pastas com as que já existem no cartão. Ele não apaga os arquivos da pessoa: fotos, frases, dicas e guias.

### 5. Conferir

```
ssh ark@IP "bash /roms/totobox/instalador/instalar.sh --conferir"
```

Explique o resultado. Se aparecer "não é compatível", pare e conte o que faltou.

### 6. Instalar

Confirme que nenhum jogo está aberto. Depois pergunte à pessoa:
- a língua dela;
- se o Meibox deve abrir quando o aparelho liga;
- se quer os jogos mais rápidos (recomendado). Explique em uma frase: troca snes9x, mGBA e gpSP por versões recompiladas para o R36S e ajusta o vídeo por jogo; SNES fica em média 24% mais rápido e GBA de 11% a 280%; Remover desfaz.

Rode:

```
ssh ark@IP "bash /roms/totobox/instalador/instalar.sh"
```

Opções: `--lingua en`, `--sem-boot`, `--sem-copiloto`, `--sem-desempenho` (se a pessoa não quiser os jogos mais rápidos).

O que o instalador faz:
- instala o Meibox;
- se a pessoa não disse `--sem-desempenho`, troca os emuladores (guardando os originais) e cria os ajustes de jogo. Os emuladores que não abrem no sistema dela ficam como estão;
- se encontrar a chave no cartão, instala o copiloto;
- guarda a chave fora do cartão, com permissão 600, e apaga a chave do arquivo no cartão;
- escolhe o modelo.

Mostre o resumo para a pessoa.

### 7. Reiniciar e conferir

- Pergunte antes de reiniciar: `ssh ark@IP "sudo -n systemctl reboot"`.
- Depois peça para a pessoa confirmar que o Meibox apareceu na tela.
- Com os jogos mais rápidos, confira: `ssh ark@IP "python3 -I ~/.local/share/meibox-desempenho/desempenho.py instalado && echo ok"`. A escolha de emulador por jogo é aplicada nesse reinício.
- Com o copiloto, confira que o serviço está ativo: `ssh ark@IP "systemctl is-active mei-copiloto"`.
- Depois peça para ela abrir um jogo e apertar **SELECT + R1**. Na primeira vez em cada jogo, a Mei "estuda" por cerca de 1 minuto.

### 8. Arrumar no fim

- Se a pessoa colou a chave, devolva o arquivo desta pasta ao modelo, **sem ler o arquivo**:
  `cp totobox/instalador/chave-da-ia.modelo.txt totobox/chave-da-ia.txt`
- Pergunte se ela quer desligar **Enable Remote Services**. Esse item também liga o compartilhamento de arquivos na rede.

### Bom saber

- Não pare o EmulationStation pelo SSH. No dArkOS, o brilho da tela pode ir a zero. Se a tela apagar, reinicie o aparelho.
- Remover: `bash /roms/totobox/instalador/instalar.sh --remover`. Acrescente `--apagar-chave` para apagar também a chave guardada.
- Para ver o que deu errado:
  - `/roms/totobox/instalador/ultimo-log.txt` (nunca contém a chave);
  - `journalctl -u mei-copiloto -n 50` para o copiloto.
- Detalhes técnicos e outros fornecedores de IA: o README do repositório, em https://github.com/carbiecarbie/meibox.
