"""Archive parser contracts and causal evaluation, without network requests."""
from datetime import datetime,timedelta,timezone
import csv,io,json,zipfile
import numpy as np
import pytest
from app.services import historical as history
from app.services.historical_evaluation import evaluate,features,split_indices,warning,prediction_features,predictor,numeric_forecast


def archive(rows):
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    binary=io.BytesIO()
    with zipfile.ZipFile(binary,'w') as z:z.writestr('data.csv',output.getvalue())
    return binary.getvalue()


def test_noaa_quality_flags_and_sentinel_values():
    assert history.qc_number('180,1,N,0123,1',3,4,10,9999)==12.3
    assert history.qc_number('180,1,N,9999,1',3,4,10,9999) is None
    assert history.qc_number('10000,9') is None
    assert history.qc_number('10000,1')==1000


def test_fixed_epa_monitor_does_not_mix_sensors(monkeypatch):
    rows=[]
    for i in range(110):
        t=datetime(2023,4,1)+timedelta(hours=i)
        row={'State Code':'36','County Code':'61','Site Num':'135','POC':'1','Date GMT':t.date().isoformat(),'Time GMT':t.strftime('%H:%M'),'Sample Measurement':'10','Units of Measure':'Micrograms/cubic meter (LC)','Qualifier':''}
        rows.extend([row,dict(row,POC='2',**{'Sample Measurement':'1000'})])
    monkeypatch.setattr(history,'fetch',lambda *a:(archive(rows),{'url':'https://example.org/public','name':'fixture'}))
    times,channels,_=history.epa()
    assert channels[0]['values'][:110]==[10]*110
    assert channels[0]['values'][110] is None


def test_bts_local_clock_rollover_and_cancellation_are_preserved(monkeypatch):
    rows=[{'FlightDate':'2023-01-11','Origin':'JFK','CRSDepTime':'630','DepDelay':'80','Cancelled':'0'},
          {'FlightDate':'2023-01-11','Origin':'JFK','CRSDepTime':'630','DepDelay':'','Cancelled':'1'},
          {'FlightDate':'2023-01-11','Origin':'JFK','CRSDepTime':'2400','DepDelay':'5','Cancelled':'0'},
          {'FlightDate':'2023-01-11','Origin':'LAX','CRSDepTime':'630','DepDelay':'999','Cancelled':'0'}]
    monkeypatch.setattr(history,'fetch',lambda *a:(archive(rows),{'url':'https://example.org/public','name':'fixture'}))
    times,channels,_=history.bts();index=times.index(history.stamp('2023-01-11T11:00:00Z'))
    assert channels[0]['values'][index]==80 and channels[1]['values'][index]==.5
    assert channels[0]['values'][times.index(history.stamp('2023-01-12T05:00:00Z'))]==5
    assert channels[0]['values'][0] is None
    assert channels[2]['values'][0]==0  # complete archive: no scheduled flight is a known zero


def test_nab_missing_timestamps_become_null_not_interpolated_measurements(monkeypatch):
    raw=b'timestamp,value\n2020-01-01 00:00:00,10\n2020-01-01 00:05:00,11\n2020-01-01 00:15:00,13\n'
    def fetch(url,name):
        if 'combined_windows' in url:return b'{"realKnownCause/machine_temperature_system_failure.csv":[]}',{'url':url}
        return raw,{'url':url}
    monkeypatch.setattr(history,'fetch',fetch)
    times,channels,_,labels,cadence=history.nab('nab-machine-temperature')
    assert channels[0]['values']==[10,11,None,13] and cadence==5/60 and len(labels)==4


def test_nab_clock_reversal_excludes_all_ambiguous_readings(monkeypatch):
    raw=b'timestamp,value\n2020-01-01 00:00:00,10\n2020-01-01 00:05:00,11\n2020-01-01 00:10:00,12\n2020-01-01 00:05:00,21\n2020-01-01 00:10:00,22\n2020-01-01 00:15:00,13\n'
    def fetch(url,name):
        if 'combined_windows' in url:return b'{"realKnownCause/machine_temperature_system_failure.csv":[]}',{'url':url}
        return raw,{'url':url}
    monkeypatch.setattr(history,'fetch',fetch)
    _,channels,_,_,_=history.nab('nab-machine-temperature')
    assert channels[0]['values']==[10,None,None,13]
    assert channels[0]['ambiguous_timestamps']==2 and channels[0]['excluded_ambiguous_readings']==4


def test_tonga_catalogue_does_not_relabel_earthquakes_as_eruptions(monkeypatch):
    t=int(history.stamp('2022-01-15T04:14:45Z').timestamp()*1000)
    doc={'metadata':{'count':2},'features':[{'properties':{'time':t,'type':'earthquake'}},{'properties':{'time':t,'type':'volcanic eruption'}}]}
    monkeypatch.setattr(history,'fetch',lambda *a:(json.dumps(doc).encode(),{'url':'https://example.org/public','name':'fixture'}))
    _,channels,_=history.tonga()
    assert sum(channels[0]['values'])==1 and sum(channels[1]['values'])==1


def fixture():
    n=600;labels=[any(a<=i<b for a,b in [(100,120),(390,410),(510,530)]) for i in range(n)]
    return {'id':'unit-labelled-fixture','dataset_mode':'historical','dataset_hash':'unit-fixture-only','label_kind':'independent_annotations','label_definition':'Unit fixture labels, not real observations',
        'description':'Isolated test fixture only','provenance':[],'event_start':'2020-01-05T00:00:00Z','event_end':'2020-01-25T00:00:00Z','cadence_hours':1,'times':[(datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(hours=i)).isoformat() for i in range(n)],
        'channels':[{'label':'Fixture value','unit':'arbitrary','values':[100+10*np.sin(i*np.pi/12)-(40 if labels[i] else 0) for i in range(n)]}], 'labels':labels,'limitations':['Unit fixture only']}


def test_warning_features_never_read_current_or_future_values():
    x=np.arange(200.).reshape(100,2);before=features(x,24,np.array([1.,2.]))
    x[50:]=1e9;after=features(x,24,np.array([1.,2.]))
    assert np.array_equal(before[:51],after[:51])


def test_batched_recursive_features_match_scalar_prefixes():
    y=np.arange(40.);y[5]=np.nan;origins=np.array([10,20]);previous=np.array([[80.,81.,np.nan],[90.,91.,np.nan]])
    actual=prediction_features(y,origins,3,previous,8,0)
    expected=np.array([predictor(list(y[:origin])+list(previous[k,:2]),origin+2,8,0) for k,origin in enumerate(origins)])
    assert np.allclose(actual,expected)


def test_batched_forecasts_do_not_observe_future_targets():
    y=np.array([100+10*np.sin(i*np.pi/12) for i in range(240)])
    before=numeric_forecast(y,144,180,1,24,100)
    y[180:]=10000
    after=numeric_forecast(y,144,180,1,24,100)
    first=lambda result:[p['value'] for p in result['predictions'] if p['origin_index']==180]
    assert first(before)==first(after) and len(first(before))==3


def test_single_event_is_held_out_and_warning_does_not_invent_accuracy():
    data=fixture();data.update(label_kind='event_window_proxy',labels=[i in range(480,510) for i in range(600)])
    assert split_indices(data)==(384,480)
    result=evaluate(data)
    assert result['advance_warning']['status']=='insufficient_labels'
    assert 'brier_score' not in result['advance_warning']
    assert result['forecast']['forecast_metrics']['persistence']['samples']>0


def test_independent_warning_is_purged_and_reports_heldout_probabilities():
    data=fixture();result=evaluate(data);warning=result['advance_warning']
    assert result['split']=={'training':360,'calibration':120,'test':120}
    assert warning['status']=='heldout_evaluated' and warning['purge_samples_per_boundary']==6
    assert all(p['index']>=480 for p in warning['predictions'])
    assert all(not data['labels'][p['index']] for p in warning['predictions'])
    assert 0<=warning['brier_score']<=1 and warning['event_onsets']==1
    assert 'training_prevalence' in {m['method'] for m in warning['comparisons']}


def test_late_bts_outcomes_do_not_claim_live_advance_warning():
    data=fixture();data['id']='faa-notam-2023'
    labels=np.array(data['labels']);X=np.ones((600,2))
    result=warning(data,X,np.ones(600,dtype=bool),labels,360,480,1)
    assert result['status']=='unsupported_source_availability' and 'brier_score' not in result


def test_processed_historical_cache_detects_tampering(tmp_path,monkeypatch):
    from app.core.config import base_settings
    monkeypatch.setattr(base_settings(),'ARTIFACT_DIR',str(tmp_path));monkeypatch.setattr(base_settings(),'ARCHIVE_STORAGE','local')
    d=dict(fixture(),id='suez-2021');d['dataset_hash']=history.digest(history.encoded({k:v for k,v in d.items() if k!='dataset_hash'}))
    path=tmp_path/'historical/cases/suez-2021.json';path.parent.mkdir(parents=True);path.write_bytes(history.encoded(d))
    assert history.read_case('suez-2021')['dataset_hash']==d['dataset_hash']
    d['channels'][0]['values'][0]=999;path.write_bytes(history.encoded(d))
    with pytest.raises(ValueError,match='checksum'):history.read_case('suez-2021')


def test_missing_remote_cache_object_is_a_cache_miss(monkeypatch):
    from app.core.config import base_settings
    from botocore.exceptions import ClientError
    monkeypatch.setattr(base_settings(),'ARCHIVE_STORAGE','r2')
    class Missing:
        def get_object(self,**kwargs):raise ClientError({'Error':{'Code':'NoSuchKey'}},'GetObject')
    monkeypatch.setattr(history.artifacts,'client',lambda:Missing())
    with pytest.raises(FileNotFoundError):history.read_key('historical/cases/test.json')


@pytest.fixture
def direct_client(monkeypatch,tmp_path):
    from app.core.db import engine
    from sqlalchemy import text
    try:
        with engine.connect() as c:assert c.execute(text("SELECT to_regclass('research_sessions')")).scalar()
    except Exception:pytest.skip('needs migrated database')
    from app.core import auth
    from app.core.config import base_settings
    from app.main import app
    from collections import defaultdict,deque
    from fastapi.testclient import TestClient
    cfg=base_settings();monkeypatch.setattr(cfg,'DEMO_DIRECT_LOGIN',True);monkeypatch.setattr(cfg,'ARTIFACT_DIR',str(tmp_path));monkeypatch.setattr(cfg,'ARCHIVE_STORAGE','local')
    monkeypatch.setattr(auth,'attempts',defaultdict(deque))
    with TestClient(app) as client:yield client


def test_direct_login_is_flagged_origin_checked_and_revocable(direct_client,monkeypatch):
    from app.core.config import base_settings
    client=direct_client
    assert client.get('/api/auth/options').json()=={'direct_demo_login':True}
    assert client.get('/api/cases').status_code==401
    assert client.post('/api/auth/demo',headers={'origin':'https://unrelated.example'}).status_code==403
    response=client.post('/api/auth/demo');assert response.status_code==200 and 'HttpOnly' in response.headers['set-cookie']
    assert client.get('/api/auth/me').json()['role']=='demo'
    client.post('/api/auth/logout');assert client.get('/api/cases').status_code==401
    monkeypatch.setattr(base_settings(),'DEMO_DIRECT_LOGIN',False)
    assert client.post('/api/auth/demo').status_code==403


def test_historical_replay_evaluation_and_archive_are_consistent_and_private(direct_client):
    from app.services.artifacts import write_bytes
    from fastapi.testclient import TestClient
    from app.main import app
    data=dict(fixture(),id='suez-2021');data['dataset_hash']=history.digest(history.encoded({k:v for k,v in data.items() if k!='dataset_hash'}))
    # This fixture is only in the temporary test artifact directory, never the real cache.
    write_bytes('historical/cases/suez-2021.json',history.encoded(data))
    client=direct_client;assert client.post('/api/auth/demo').status_code==200
    loaded=client.get('/api/cases/suez-2021/data');assert loaded.status_code==200
    response=client.post('/api/cases/suez-2021/evaluate');assert response.status_code==201
    result=response.json();assert result['dataset_hash']==loaded.json()['dataset_hash']
    artifact=result['artifacts'][0];content=client.get(artifact['url']).content
    assert history.digest(content)==artifact['sha256']
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        assert json.loads(z.read('observations-and-labels.json'))['dataset_hash']==result['dataset_hash']
        assert 'manifest.json' in z.namelist()
        assert result['dataset_hash'] in z.read('report.md').decode()
    stranger=TestClient(app);assert stranger.post('/api/auth/demo').status_code==200
    assert stranger.get(artifact['url']).status_code==404
    cached=client.get('/api/cases/suez-2021/data').json()['evaluation']
    assert cached['advance_warning']['brier_score']==result['advance_warning']['brier_score']
