#!/usr/bin/env python3
"""Liga o Serviço de IA do RetroArch para o Copiloto da Mei (design 5.2 + network_cmd_enable).

Uso:
  retroarch-patch.py conferir   mostra o que mudaria, sem gravar nada
  retroarch-patch.py aplicar    faz backup (<cfg>.antes-copiloto) e troca as 6 linhas
  retroarch-patch.py desfazer   volta só essas 6 linhas para o valor do backup

Mexe nas duas configs (retroarch e retroarch32). Só troca linhas que já existem; se faltar
alguma, ou se algum atalho já usar o botão 5, para sem gravar. Recusa rodar com o RetroArch aberto.
"""
import os
import re
import shutil
import subprocess
import sys

CONFIGS = [os.path.expanduser("~/.config/retroarch/retroarch.cfg"),
           os.path.expanduser("~/.config/retroarch32/retroarch.cfg")]
SUFIXO_BACKUP = ".antes-copiloto"
MUDANCAS = {
    "ai_service_enable": "true",
    "ai_service_url": "http://127.0.0.1:4404/",
    "ai_service_mode": "0",
    "ai_service_pause": "true",
    "input_ai_service_btn": "5",
    "network_cmd_enable": "true",
}
EXIGIDOS = {"network_cmd_port": "55355", "config_save_on_exit": "false", "input_enable_hotkey_btn": "12"}
_LINHA = re.compile(r'^(\w+)\s*=\s*"(.*)"\s*$')


def ler(caminho):
    with open(caminho, encoding="utf-8", newline="") as f:
        return f.read().splitlines(keepends=True)


def valores(linhas):
    out = {}
    for l in linhas:
        m = _LINHA.match(l.rstrip("\r\n"))
        if m:
            out[m.group(1)] = m.group(2)
    return out


def trocar(linhas, novos):
    """Troca o valor das chaves em `novos`, mantendo o resto do arquivo byte a byte."""
    feitos, out = set(), []
    for l in linhas:
        fim = l[len(l.rstrip("\r\n")):]
        m = _LINHA.match(l.rstrip("\r\n"))
        if m and m.group(1) in novos:
            out.append(f'{m.group(1)} = "{novos[m.group(1)]}"{fim}')
            feitos.add(m.group(1))
        else:
            out.append(l)
    return out, set(novos) - feitos


def problemas(caminho, v):
    p = []
    for k in MUDANCAS:
        if k not in v:
            p.append(f"falta a linha {k}")
    for k, esperado in EXIGIDOS.items():
        if v.get(k) != esperado:
            p.append(f"{k} = {v.get(k)!r} (esperado {esperado!r})")
    atalhos5 = [k for k, val in v.items() if k.endswith("_btn") and val == "5"
                and not k.startswith("input_player") and k != "input_ai_service_btn"]
    if atalhos5:
        p.append(f"atalho já usa o botão 5 (R1): {', '.join(atalhos5)}")
    pasta = os.path.join(os.path.dirname(caminho), "config")
    for raiz, _, arquivos in os.walk(pasta):
        for a in arquivos:
            if a.endswith(".cfg"):
                arq = os.path.join(raiz, a)
                ov = valores(ler(arq))
                for k in list(MUDANCAS) + ["input_enable_hotkey_btn"]:
                    if k in ov:
                        p.append(f"override {arq} redefine {k}")
                for k, val in ov.items():
                    if k.endswith("_btn") and val == "5" and not k.startswith("input_player"):
                        p.append(f"override {arq} usa o botão 5 em {k}")
    return p


def retroarch_aberto():
    r = subprocess.run(["pgrep", "-f", "/usr/local/bin/retroarch|/opt/retroarch/bin/"],
                       capture_output=True)
    return r.returncode == 0


def gravar(caminho, linhas):
    tmp = caminho + ".tmp-copiloto"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.writelines(linhas)
    shutil.copymode(caminho, tmp)
    os.replace(tmp, caminho)


def principal(modo):
    if modo not in ("conferir", "aplicar", "desfazer"):
        print(__doc__)
        return 2
    if modo != "conferir" and retroarch_aberto():
        print("ERRO: o RetroArch está aberto. Feche o jogo e rode de novo.")
        return 3
    if modo == "aplicar":  # tudo ou nada: confere as duas configs antes de gravar qualquer uma
        achados = [(cfg, x) for cfg in CONFIGS if os.path.exists(cfg)
                   for x in problemas(cfg, valores(ler(cfg)))]
        if achados:
            for cfg, x in achados:
                print(f"PROBLEMA em {cfg}: {x}")
            print("nada foi gravado")
            return 1
    erro = False
    for cfg in CONFIGS:
        print(f"== {cfg}")
        if not os.path.exists(cfg):
            print("   não existe; pulando")
            continue
        linhas = ler(cfg)
        v = valores(linhas)
        backup = cfg + SUFIXO_BACKUP
        if modo == "desfazer":
            if not os.path.exists(backup):
                print("   sem backup; nada a desfazer")
                continue
            antes = valores(ler(backup))
            novos = {k: antes[k] for k in MUDANCAS if k in antes}
        else:
            p = problemas(cfg, v)
            if p:
                erro = True
                for x in p:
                    print(f"   PROBLEMA: {x}")
                continue
            novos = dict(MUDANCAS)
        for k, val in novos.items():
            marca = "igual" if v.get(k) == val else f"{v.get(k)!r} -> {val!r}"
            print(f"   {k}: {marca}")
        if modo == "conferir":
            continue
        if modo == "aplicar" and not os.path.exists(backup):
            shutil.copy2(cfg, backup)
            print(f"   backup: {backup}")
        novas, faltando = trocar(linhas, novos)
        if faltando:
            print(f"   ERRO: linhas não encontradas: {sorted(faltando)}; nada gravado")
            erro = True
            continue
        gravar(cfg, novas)
        confere = valores(ler(cfg))
        ruins = [k for k, val in novos.items() if confere.get(k) != val]
        mudou = sum(1 for a, b in zip(linhas, novas) if a != b)
        if ruins or len(novas) != len(linhas):
            print(f"   ERRO na conferência: {ruins}")
            erro = True
        else:
            print(f"   gravado e conferido ({mudou} linhas mudaram, {len(linhas)} no total)")
    return 1 if erro else 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1] if len(sys.argv) > 1 else ""))
