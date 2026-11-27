"""Match an offline GTFS-Realtime protobuf to an attributed static schedule."""
import argparse
from pathlib import Path
from app.services.transit import match_gtfs
from app.worker import store
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schedule',type=Path,required=True)
    parser.add_argument('--feed',type=Path,required=True)
    parser.add_argument('--service-date',required=True,help='YYYYMMDD in agency local time')
    parser.add_argument('--provenance-url',required=True)
    args=parser.parse_args()
    rows=match_gtfs(args.feed.read_bytes(),args.schedule,args.service_date)
    for _,_,payload in rows:payload['provenance_url']=args.provenance_url
    print(f"Imported {store('gtfs-local','transit',rows,kind='derived')} matched estimates")
