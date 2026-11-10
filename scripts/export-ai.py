"""Snapshot explicitly selected native sessions, preserving chronology and recording cutoff."""
import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--session',action='append',required=True,help='Explicit native JSONL path; repeat for review sessions')
parser.add_argument('--commits',default='')
args=parser.parse_args()
output=Path('ai/sessions')
output.mkdir(parents=True,exist_ok=True)
manifest=[]
index=[]
for name in args.session:
    source=Path(name)
    raw=source.read_text()
    # An actively written log can end with an incomplete line; export complete JSON records only.
    records=[]
    lines=[]
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
            lines.append(line)
        except json.JSONDecodeError:
            break
    native='\n'.join(lines)+'\n'
    redactions=0
    for pattern in [r'\bghp_[A-Za-z0-9]{30,}\b',r'\bgithub_pat_[A-Za-z0-9_]{30,}\b',r'\bsk-[A-Za-z0-9_-]{32,}\b']:
        native,n=re.subn(pattern,'[REDACTED: credential]',native)
        redactions+=n
    if re.search(r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----\r?\n(?:[A-Za-z0-9+/=]+\r?\n)+-----END (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',native):
        raise SystemExit('Private key detected; inspect and narrowly redact before export.')
    metas=[r['payload'] for r in records if r.get('type')=='session_meta']
    match=re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$',source.name)
    sid=match.group(1) if match else (metas[-1].get('id',source.stem) if metas else source.stem)
    contexts=[r.get('payload',{}) for r in records if r.get('type')=='turn_context']
    models=sorted({c['model'] for c in contexts if isinstance(c.get('model'),str)})
    started=next((r['timestamp'] for r in records if r.get('type')=='session_meta' and r.get('payload',{}).get('id')==sid),records[0]['timestamp'])
    starts=[r['timestamp'] for r in records if r.get('payload',{}).get('type')=='task_started']
    ends=[r['timestamp'] for r in records if r.get('payload',{}).get('type')=='task_complete']
    if not any(m.get('id')==sid for m in metas) and starts:
        started=starts[-1]
    ended=ends[-1] if ends and (not starts or ends[-1]>starts[-1]) else ''
    target=output/source.name
    target.write_text(native)
    cutoff=records[-1].get('timestamp','')
    manifest.append({'session_id':sid,'native_metadata_session_ids':sorted({m.get('id','') for m in metas}),'export_file':str(target),'captured_at':datetime.now(timezone.utc).isoformat(),'last_record_at':cutoff,'records':len(records),'redactions':redactions,'sha256':hashlib.sha256(native.encode()).hexdigest(),'partial_snapshot':not bool(ended)})
    purpose='Assessment implementation and documentation' if sid=='01a1c623-2c2e-7b80-abe6-be94617590ba' else 'Independent design or code review (native fork history retained)'
    index.append([sid,'Codex', ';'.join(models) or 'not recorded',started,ended,str(target),purpose,args.commits])
with Path('ai/session-index.csv').open('w',newline='') as f:
    writer=csv.writer(f,lineterminator="\n")
    writer.writerow(['session_id','tool','model','started_at','ended_at','export_file','purpose','related_commits'])
    writer.writerows(index)
Path('ai/export-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f'Exported {len(index)} native chronological session snapshots; {sum(m["redactions"] for m in manifest)} credential-pattern redactions.')
