"""Run account-free validation against attributed hourly data and independent labels."""
import argparse,json
from pathlib import Path
from app.services.validation import evaluate_labelled
from app.services.artifacts import bundle
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    original=args.file.read_bytes();result=evaluate_labelled(json.loads(original))
    args.output.write_bytes(bundle({'input.json':original,'evaluation.json':json.dumps(result,indent=2).encode()},{'dataset_mode':result['dataset_mode'],'dataset_hash':result['dataset_hash']}))
    print(f'Wrote reproducible labelled evaluation: {args.output}')
