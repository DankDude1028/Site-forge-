"""Load one model at several context sizes; record measured VRAM and RAM. No inference."""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
import psutil

model, out = sys.argv[1], sys.argv[2]
def vram_mib():
    return int(subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                              capture_output=True, text=True).stdout.strip())
def lm_private_gib():
    total = 0
    for p in psutil.process_iter(['exe']):
        try:
            if p.info['exe'] and ('.lmstudio' in p.info['exe'] or 'LM Studio' in p.info['exe']):
                total += p.memory_info().private
        except (psutil.Error, OSError):
            pass
    return total / 2**30
def snap():
    return {'vram_mib': vram_mib(), 'free_ram_gib': psutil.virtual_memory().available / 2**30, 'lm_private_gib': lm_private_gib()}

subprocess.run(['lms', 'unload', '--all'], capture_output=True, timeout=60)
time.sleep(3)
rows = []
for ctx in (8192, 16384, 32768, 65536, 131072):
    base = snap()
    t0 = time.monotonic()
    load = subprocess.run(['lms', 'load', model, '--identifier', 'ctx-probe', '--context-length', str(ctx),
                           '--parallel', '1', '--yes'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    seconds = time.monotonic() - t0
    time.sleep(5)
    loaded = snap()
    ps = subprocess.run(['lms', 'ps', '--json'], capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
    row = {'context': ctx, 'loaded_ok': load.returncode == 0, 'load_seconds': round(seconds, 2),
           'baseline': base, 'loaded': loaded,
           'vram_increase_mib': loaded['vram_mib'] - base['vram_mib'],
           'free_ram_drop_gib': round(base['free_ram_gib'] - loaded['free_ram_gib'], 2),
           'lms_ps': (ps or '')[:600], 'load_tail': ((load.stdout or '') + (load.stderr or ''))[-300:]}
    rows.append(row)
    print(f"ctx={ctx:>6} ok={row['loaded_ok']} VRAM {loaded['vram_mib']} MiB (+{row['vram_increase_mib']}) | "
          f"free RAM {loaded['free_ram_gib']:.1f} GiB (-{row['free_ram_drop_gib']}) | LM private {loaded['lm_private_gib']:.2f} GiB", flush=True)
    subprocess.run(['lms', 'unload', 'ctx-probe'], capture_output=True, timeout=60)
    time.sleep(4)
    if not row['loaded_ok'] or loaded['vram_mib'] > 11500:
        print('stopping: load failed or VRAM near the 12 GB limit', flush=True)
        break
json.dump({'model': model, 'captured_at': datetime.now(timezone.utc).isoformat(), 'scope': 'load-only memory measurement, no inference', 'rows': rows},
          open(out, 'w', encoding='utf-8'), indent=2)
