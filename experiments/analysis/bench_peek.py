import json
import sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
for r in d['runs']:
    res = [t for t in r['results'] if not t.get('warmup')]
    cut = sum((t.get('completion') or {}).get('finish_reason') == 'length' for t in res)
    print(f"{r['source_model']} ctx={r['context']} max_tokens={r['settings'].get('max_tokens')} done={len(res)} passed={sum(t['passed'] for t in res)} cut_off={cut} errors={sum(bool(t.get('errors')) for t in res)}")
    for t in res[-6:]:
        c = t.get('completion') or {}
        print(f"  {t['task_id']:<14} {t['category']:<9} {'PASS' if t['passed'] else 'fail':<4} {c.get('finish_reason')} tokens={c.get('output_tokens')} {round(t.get('wall_seconds') or 0, 1)}s {(t.get('reason') or '')[:40]}")
