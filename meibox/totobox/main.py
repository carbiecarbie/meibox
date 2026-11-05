"""Totobox entry point.

Development options (used over SSH, not by the menu launcher):
  --home DIR          data/cache/state folder (default ~/.local/share/totobox)
  --script a,b,...    inject actions; also shot:NAME, wait:MS, mem, quit
  --shots DIR         where shot:NAME screenshots go
  --game-timeout S    ask a launched game to quit after S seconds
  --report FILE       write timings, memory and launches as JSON on exit
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from totobox.app import App  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--home", default=os.path.expanduser("~/.local/share/totobox"))
    p.add_argument("--script", default="")
    p.add_argument("--shots")
    p.add_argument("--game-timeout", type=float)
    p.add_argument("--report")
    a = p.parse_args()
    script = [s.strip() for s in a.script.split(",") if s.strip()]
    app = App(a.home, script, a.shots, a.game_timeout, a.report)
    if os.environ.get("TOTOBOX_PROFILE"):
        import cProfile
        import pstats
        prof = cProfile.Profile()
        prof.runcall(app.run)
        with open(os.environ["TOTOBOX_PROFILE"], "w") as f:
            pstats.Stats(prof, stream=f).sort_stats("tottime").print_stats(30)
    else:
        app.run()


if __name__ == "__main__":
    main()
