#!/usr/bin/env python3
"""Compare single-thread fixed-depth traces and perft totals for a batch-04 candidate."""
from pathlib import Path
import argparse,json,re,subprocess
p=argparse.ArgumentParser();p.add_argument('baseline');p.add_argument('candidate');a=p.parse_args()
here=Path(__file__).resolve().parent
cases=[(13,'default','depth'),(14,'default','depth'),(8,str(here/'holdout.fen'),'depth'),(3,str(here/'specials.fen'),'perft')]
def run(exe,case):
 depth,positions,kind=case
 r=subprocess.run([str(Path(exe).resolve()),'bench','16','1',str(depth),positions,kind],capture_output=True,text=True,check=True)
 m=re.search(r'Nodes searched\s*:\s*(\d+)',r.stderr)
 if not m:raise RuntimeError(r.stderr[-2000:])
 trace=[' '.join(re.sub(r'\b(?:time|nps) \d+','',line).split()) for line in r.stdout.splitlines() if line.startswith(('info depth','bestmove'))]
 return int(m[1]),trace
report=[]
for case in cases:
 b=run(a.baseline,case);t=run(a.candidate,case)
 if b!=t:raise RuntimeError(f'Equivalence mismatch: {case}; node totals {b[0]} and {t[0]}')
 if case==(13,'default','depth') and b[0]!=1559611:raise RuntimeError('Wrong batch baseline signature')
 report.append({'depth':case[0],'positions':case[1],'kind':case[2],'nodes':b[0],'matching_trace_lines':len(b[1])})
print(json.dumps({'status':'pass','checks':report},indent=2))
