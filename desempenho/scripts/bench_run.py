"""Orquestra o teste de velocidade do r36s-perf no R36S, pelo SSH.

Cada medição roda o mesmo jogo duas vezes, com N1 e N2 quadros, e usa
fps = (N2 - N1) / (t2 - t1): o tempo de carregar core e ROM se cancela.

Uso:
  python scripts/bench_run.py jobs.json --tag L0 [--es parado|rodando]

jobs.json: lista de {"emu", "core", "rom", "n1", "n2", "reps"?, "slot"?, "ss"?}
"""
import argparse
import os
import json
import shlex
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Aparelho e chave vêm do ambiente: R36S_HOST=ark@<ip> (obrigatório), R36S_SSH_KEY e R36S_KNOWN_HOSTS (opcionais).
HOST = os.environ.get("R36S_HOST", "")
BENCH = "/home/ark/.local/share/r36s-perf/bench/bench.sh"
SSH = (["ssh"] + (["-i", os.environ["R36S_SSH_KEY"], "-o", "IdentitiesOnly=yes"] if os.environ.get("R36S_SSH_KEY") else [])
       + (["-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=" + os.environ["R36S_KNOWN_HOSTS"]]
          if os.environ.get("R36S_KNOWN_HOSTS") else [])
       + ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "LogLevel=ERROR", HOST])


def remote(cmd, timeout=900):
    r = subprocess.run(SSH + [cmd], capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"falhou ({r.returncode}): {cmd}\n{r.stderr}")
    return r.stdout


def fetch(remote_path, local_path):
    local_path.parent.mkdir(parents=True, exist_ok=True)
    scp = ["scp"] + SSH[1:-1] + [f"{HOST}:{remote_path}", str(local_path)]
    subprocess.run(scp, check=True, capture_output=True, timeout=120)


def one_run(job, frames, ss_path=None):
    # job["env"]: variáveis para o bench.sh, ex.: {"RUNPFX": "taskset -c 3"}
    envs = dict(job.get("env", {}), **({"SS_PATH": ss_path} if ss_path else {}))
    env = "".join(f"{k}={shlex.quote(v)} " for k, v in envs.items())
    cmd = env + " ".join(shlex.quote(str(a)) for a in
                         [BENCH, job["emu"], job["core"], job["rom"], frames] +
                         ([str(job["slot"])] if job.get("slot") is not None else []))
    line = remote(cmd).strip().splitlines()[-1]
    data = json.loads(line)
    if "erro" in data or data.get("rc") != 0 or data.get("state_loaded") is False:
        raise RuntimeError(f"rodada falhou: {data}")
    return data


def slug(text):
    return "".join(c if c.isalnum() else "_" for c in text)[:60].strip("_")


def measure(job, tag, es, stamp, raw):
    reps = job.get("reps", 3)
    fps_list, runs = [], []
    for rep in range(reps):
        # Alterna a ordem para não favorecer sempre a mesma rodada.
        order = [job["n1"], job["n2"]]
        if rep % 2:
            order.reverse()
        res = {frames: one_run(job, frames) for frames in order}
        a, b = res[job["n1"]], res[job["n2"]]
        fps = (job["n2"] - job["n1"]) / (b["wall_s"] - a["wall_s"])
        fps_list.append(fps)
        for r in (a, b):
            r.update(tag=tag, es=es, rep=rep, stamp=stamp)
            runs.append(r)
        with raw.open("a", encoding="utf-8") as f:
            for r in (a, b):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.write(json.dumps({"tag": tag, "es": es, "rep": rep,
                                "emu": job["emu"], "core": job["core"],
                                "core_sha": b["core_sha"],
                                "rom": Path(job["rom"]).name, "env": job.get("env"),
                                "fps": round(fps, 2)},
                               ensure_ascii=False) + "\n")
    if job.get("ss"):
        # Rodada extra, fora da conta: o screenshot custa tempo.
        ss = f"/home/ark/.local/share/r36s-perf/bench/tmp/{slug(job['rom'])}-{job['emu']}-{slug(Path(job['core']).name)}.png"
        one_run(job, job["n2"], ss)
        fetch(ss, ROOT / "results" / "scenes" / tag / Path(ss).name)
    med = statistics.median(fps_list)
    spread = (max(fps_list) - min(fps_list)) / med * 100 if med else 0
    row = {"rom": Path(job["rom"]).name, "emu": job["emu"], "core": job["core"],
           "env": job.get("env"), "fps_med": round(med, 1), "spread_pct": round(spread, 1),
           "temp_max_c": max(r["temp_max_c"] for r in runs),
           "throttled": any(r["throttled"] for r in runs)}
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs")
    ap.add_argument("--tag", required=True, help="camada/variante, ex.: L0")
    ap.add_argument("--es", choices=["parado", "rodando"], default="parado")
    args = ap.parse_args()

    jobs = json.loads(Path(args.jobs).read_text(encoding="utf-8"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw = ROOT / "results" / "raw" / f"{stamp}-{args.tag}.jsonl"
    raw.parent.mkdir(parents=True, exist_ok=True)

    if remote("pgrep -f '^/opt/retroarch/bin/' || true").strip():
        sys.exit("Há um jogo aberto no aparelho; nada foi medido.")
    if args.es == "parado":
        remote("sudo -n systemctl stop emulationstation; sleep 2")
    try:
        summary = []
        out = ROOT / "results" / f"{stamp}-{args.tag}-resumo.json"
        for job in jobs:
            try:
                row = measure(job, args.tag, args.es, stamp, raw)
            except (RuntimeError, ZeroDivisionError, subprocess.TimeoutExpired) as e:
                row = {"rom": Path(job["rom"]).name, "emu": job["emu"], "core": job["core"],
                       "erro": str(e)[:300]}
            summary.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            # Grava a cada jogo: uma matriz longa não perde o que já mediu.
            out.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"resumo: {out}")
    finally:
        if args.es == "parado":
            remote("sudo -n systemctl start emulationstation")
            time.sleep(3)
            remote("[ -f ~/.local/share/r36s-perf/state/backlight-off ] && "
                   "echo 0 > /sys/class/backlight/backlight/brightness || true")


if __name__ == "__main__":
    main()
