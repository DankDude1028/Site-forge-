import json
import collections
import sys
sys.path.insert(0, '.')
from siteforge.model_router import ROLE_CATEGORIES
def runs(path, budget=None):
    for r in json.load(open(path, encoding='utf-8'))['runs']:
        if r.get('dataset_version') == '1.3.0' and len(r['task_ids']) >= 100 and len(r['results']) >= 100:
            yield r
def stats(r):
    res = [t for t in r['results'] if not t.get('warmup')]
    cat = collections.defaultdict(lambda: [0, 0, 0.0])
    for t in res:
        c = cat[t['category']]; c[1] += 1; c[0] += bool(t['passed']); c[2] += t.get('wall_seconds') or 0
    cut = sum((t.get('completion') or {}).get('finish_reason') == 'length' for t in res)
    s, tel = r['summary'], r['telemetry']
    roles = {}
    for role, cats in ROLE_CATEGORIES.items():
        ok = all(cat[c][1] >= 5 and cat[c][0] / cat[c][1] >= 0.8 for c in cats)
        n = sum(cat[c][1] for c in cats); p = sum(cat[c][0] for c in cats); sec = sum(cat[c][2] for c in cats)
        roles[role] = (ok, p / sec * 3600 if sec else 0)
    return res, cat, cut, s, tel, roles
rows = [('original', r) for r in runs('benchmarks/results/results.json')] + [('4096 budget', r) for r in runs(sys.argv[1])]
for label, r in rows:
    res, cat, cut, s, tel, roles = stats(r)
    print(f"\n{r['source_model']} {r['quantization']} ctx={r['context']} [{label}, max_tokens={r['settings']['max_tokens']}]")
    print(f"  PASSED {s['passed']}/100  cut_off={cut}  schema_valid={s['schema_validity']}  success/hr={s['success_per_hour'] or 0:.0f}  tok/s={s['mean_tokens_per_second'] or 0:.1f}  mean latency={s['mean_latency_seconds'] or 0:.1f}s  load={r.get('load_seconds') or 0:.1f}s")
    print('  ' + '  '.join(f"{k}:{v[0]}/{v[1]}" for k, v in sorted(cat.items())))
    print(f"  GPU peak {tel['peak_gpu_used_mib']:.0f} MiB, util mean {tel['mean_gpu_utilization_percent']:.0f}%, sys RAM peak {tel['peak_system_used_ram_bytes']/2**30:.1f} GiB, LM CPU mean {tel['mean_lm_process_cpu_percent']:.0f}%")
    print('  roles qualified: ' + ', '.join(f"{k} ({v[1]:.0f}/hr)" for k, v in roles.items() if v[0]) if any(v[0] for v in roles.values()) else '  roles qualified: none')
