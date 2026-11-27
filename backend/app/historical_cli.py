"""Download reproducible public historical cases, then evaluate locally."""
import argparse,json
from app.services.historical import definitions,download,read_case,encoded
from app.services.artifacts import write_bytes

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['download','evaluate']);p.add_argument('--case');p.add_argument('--all',action='store_true');p.add_argument('--refresh',action='store_true');args=p.parse_args()
    if not args.case and not args.all:p.error('Choose --case or --all')
    failures=[]
    for case in ([args.case] if args.case else [r['id'] for r in definitions()]):
        try:
            data=download(case,args.refresh) if args.command=='download' else read_case(case)
            if args.command=='evaluate':
                from app.services.historical_evaluation import evaluate
                result=evaluate(data);write_bytes(f'historical/evaluations/{case}.json',encoded(result))
                print(json.dumps({'case':case,'detection':result['detection']['status'],'warning':result['advance_warning']['status']}),flush=True)
            else:print(json.dumps({'case':case,'samples':len(data['times']),'coverage':{c['id']:c['coverage_pct'] for c in data['channels']},'sha256':data['dataset_hash']}),flush=True)
        except Exception as e:
            failures.append(case);print(json.dumps({'case':case,'error':type(e).__name__,'detail':str(e)[:250]}),flush=True)
    if failures:raise SystemExit('Unavailable studies: '+', '.join(failures))

if __name__=='__main__':main()
