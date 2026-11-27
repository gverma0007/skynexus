"""Process local scientific products or retrieve an authorized EWDS request."""
import argparse,json
from pathlib import Path
from app.services.scientific import process


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    local=commands.add_parser('process')
    local.add_argument('file',type=Path)
    local.add_argument('--source',required=True)
    local.add_argument('--observed-at',required=True)
    local.add_argument('--published-at')
    local.add_argument('--provenance-url',required=True)
    local.add_argument('--threshold',type=float,required=True)
    local.add_argument('--comparison',choices=['gte','lte'],default='gte')
    local.add_argument('--kind',choices=['observed','forecast','derived','synthetic'],default='observed')
    local.add_argument('--variable')
    local.add_argument('--selection',default='{}',help='JSON dimension:index pairs')
    local.add_argument('--baseline',type=Path)
    local.add_argument('--percent',action='store_true')
    local.add_argument('--output',type=Path,required=True)
    remote=commands.add_parser('download')
    remote.add_argument('--dataset',choices=['cems-glofas-forecast','cems-glofas-historical','cems-glofas-reforecast'],required=True)
    remote.add_argument('--request',type=Path,required=True,help='Request JSON from the dataset download form')
    remote.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='download':
        import cdsapi
        from app.core.config import get_settings
        token=get_settings().EWDS_API_TOKEN
        if not token:parser.error('Configure EWDS_API_TOKEN and accept the dataset terms in EWDS first')
        cdsapi.Client(url='https://ewds.climate.copernicus.eu/api',key=token,quiet=True).retrieve(args.dataset,json.loads(args.request.read_text()),str(args.output))
        return
    row=process(args.file,source=args.source,observed_at=args.observed_at,published_at=args.published_at,
                provenance_url=args.provenance_url,threshold=args.threshold,comparison=args.comparison,
                kind=args.kind,variable=args.variable,selection=json.loads(args.selection),baseline=args.baseline,percent=args.percent)
    from app.services.artifacts import write_bytes
    content=args.file.read_bytes()
    key='scientific/'+row['payload']['product_sha256']+'/'+args.file.name
    write_bytes(key,content)
    row['payload']['archive_key']=key
    if args.baseline:
        write_bytes('scientific/'+row['payload']['baseline_sha256']+'/'+args.baseline.name,args.baseline.read_bytes())
    args.output.write_text(json.dumps(row,sort_keys=True)+'\n')
    print(f'Wrote attributed footprint: {args.output}')

if __name__=='__main__':main()
