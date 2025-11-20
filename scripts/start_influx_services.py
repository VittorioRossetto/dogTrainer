#!/usr/bin/env python3
"""Start both the Influx collector and the HTTP API together.

This script launches `src/influx_api.py` and `src/influx_collector.py` as
subprocesses, forwards their stdout/stderr to the console, and will restart
either service if it exits (unless --no-restart is provided).

Usage:
  python3 scripts/start_influx_services.py
  python3 scripts/start_influx_services.py --no-restart
"""
import argparse
import os
import signal
import subprocess
import sys
import time


def start_process(cmd, cwd=None):
    return subprocess.Popen([sys.executable, cmd], cwd=cwd)


def main(argv=None):
    p = argparse.ArgumentParser(description="Start Influx collector + API")
    p.add_argument("--no-restart", action="store_true", help="Do not restart services if they exit")
    args = p.parse_args(argv)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    api_script = os.path.join(repo_root, "src", "influx_api.py")
    collector_script = os.path.join(repo_root, "src", "influx_collector.py")

    procs = {}

    def spawn_all():
        procs['api'] = start_process(api_script)
        print(f"[LAUNCHER] Started API (pid={procs['api'].pid})")
        procs['collector'] = start_process(collector_script)
        print(f"[LAUNCHER] Started Collector (pid={procs['collector'].pid})")

    spawn_all()

    try:
        while True:
            # Poll processes
            for name, proc in list(procs.items()):
                ret = proc.poll()
                if ret is not None:
                    print(f"[LAUNCHER] Process {name} (pid={proc.pid}) exited with {ret}")
                    if args.no_restart:
                        # exit if any process dies
                        print("[LAUNCHER] --no-restart set; shutting down remaining processes")
                        for other in procs.values():
                            if other.poll() is None:
                                other.terminate()
                        return 0
                    else:
                        print(f"[LAUNCHER] Restarting {name} in 2s...")
                        time.sleep(2)
                        if name == 'api':
                            procs['api'] = start_process(api_script)
                            print(f"[LAUNCHER] Restarted API (pid={procs['api'].pid})")
                        elif name == 'collector':
                            procs['collector'] = start_process(collector_script)
                            print(f"[LAUNCHER] Restarted Collector (pid={procs['collector'].pid})")
            time.sleep(1)

    except KeyboardInterrupt:
        print("[LAUNCHER] KeyboardInterrupt, terminating children")
        for proc in procs.values():
            try:
                proc.terminate()
            except Exception:
                pass
        # give them a moment
        time.sleep(1)
        for proc in procs.values():
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
        return 0


if __name__ == '__main__':
    sys.exit(main())
