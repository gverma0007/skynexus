"""Evaluate user-supplied independent labels without importing future features."""
from datetime import datetime
import hashlib,json
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from app.services.benchmark import binary_metrics


def evaluate_labelled(document):
    if document.get('dataset_mode') not in ('historical','synthetic'):
        raise ValueError('Declare historical or synthetic dataset_mode')
    if not document.get('provenance_url') or not document.get('labels_provenance_url'):
        raise ValueError('Measurements and independent labels require separate provenance references')
    rows=document.get('series',[])
    if not 240<=len(rows)<=10000:raise ValueError('Provide 240 to 10000 complete hourly observations')
    times=[datetime.fromisoformat(r['time'].replace('Z','+00:00')) for r in rows]
    if any(t.tzinfo is None for t in times) or any((b-a).total_seconds()!=3600 for a,b in zip(times,times[1:])):
        raise ValueError('Use consecutive hourly timestamps with timezones')
    if any(type(r.get('label')) is not bool or type(r.get('quality',True)) is not bool for r in rows):
        raise ValueError('Each hour requires a boolean independently supplied label and quality flag')
    values=np.array([float(r['value']) for r in rows]);labels=np.array([r['label'] for r in rows]);quality=np.array([r.get('quality',True) for r in rows])
    if not np.isfinite(values).all():raise ValueError('Values must be finite; flag missing-source observations with quality=false')
    n=len(rows);train_end=n//2;cal_end=n*3//4;horizon=int(document.get('horizon_hours',6))
    if not 1<=horizon<=24:raise ValueError('horizon_hours must be 1 to 24')
    reference=values[:train_end][quality[:train_end] & ~labels[:train_end]]
    if len(reference)<48:raise ValueError('Need at least 48 valid normal training observations')
    mean=float(reference.mean());sd=max(float(reference.std()),abs(mean)*.05,1e-6)
    residual=(values-mean)/sd
    forest=IsolationForest(random_state=42,n_estimators=80,contamination=.03).fit(reference.reshape(-1,1))
    start=cal_end
    predictions={'z_score':abs(residual[start:])>=3,'isolation_forest':forest.predict(values[start:].reshape(-1,1))==-1,
                 'quality_aware_fusion':(abs(residual[start:])>=3)&quality[start:]}
    detection={name:binary_metrics(flags,labels[start:],start=start) for name,flags in predictions.items()}
    # Forecast target is disruption in the next H hours, excluding the current hour.
    X=np.column_stack([residual,np.r_[0,np.diff(values)]/sd,np.arange(n)%24])
    target=np.array([labels[i+1:i+horizon+1].any() for i in range(n-horizon)])
    training=[i for i in range(1,train_end-horizon) if quality[i]]
    calibration=[i for i in range(train_end,cal_end-horizon) if quality[i]]
    testing=[i for i in range(cal_end,n-horizon) if quality[i]]
    warning={'status':'insufficient_labels','target':f'any labelled disruption in the next {horizon} hours'}
    if all(len({bool(target[i]) for i in subset})==2 for subset in (training,calibration)) and testing:
        model=make_pipeline(StandardScaler(),LogisticRegression(random_state=42,max_iter=500)).fit(X[training],target[training])
        platt=LogisticRegression(random_state=42,max_iter=500).fit(model.decision_function(X[calibration]).reshape(-1,1),target[calibration])
        probability=platt.predict_proba(model.decision_function(X[testing]).reshape(-1,1))[:,1]
        actual=target[testing]
        bins=[]
        for low in (0,.2,.4,.6,.8):
            selected=(probability>=low)&(probability<(low+.2 if low<.8 else 1.000001))
            bins.append({'lower':low,'upper':low+.2,'samples':int(selected.sum()),'mean_probability':float(probability[selected].mean()) if selected.any() else None,'observed_rate':float(actual[selected].mean()) if selected.any() else None})
        onsets=[i for i in range(cal_end,n-horizon) if labels[i] and not labels[i-1]]
        leads=[]
        for onset in onsets:
            candidates=[onset-i for k,i in enumerate(testing) if i<onset and onset-i<=horizon and not labels[i] and probability[k]>=.5]
            if candidates:leads.append(max(candidates))
        warning={'status':'heldout_evaluated','target':warning['target'],'horizon_hours':horizon,'brier_score':float(np.mean((probability-actual)**2)),
                 'reference_brier_score':float(np.mean((target[training].mean()-actual)**2)),'reliability_bins':bins,'test_samples':len(testing),'event_onsets':len(onsets),'events_with_advance_warning':len(leads),'mean_warning_lead_hours':float(np.mean(leads)) if leads else None,'false_warning_hours':int(np.sum((probability>=.5)&~actual)),
                 'predictions':[{'time':times[i].isoformat(),'probability':float(p),'outcome':bool(actual[k])} for k,(i,p) in enumerate(zip(testing,probability))]}
    return {'dataset_mode':document['dataset_mode'],'method_version':'independent-labels-v1','dataset_hash':hashlib.sha256(json.dumps(document,sort_keys=True).encode()).hexdigest(),
            'detection_metrics':detection,'advance_warning':warning,'split':{'training':train_end,'calibration':cal_end-train_end,'test':n-cal_end},
            'label_provenance':document['labels_provenance_url'],'limitations':['Labels are supplied by the dataset curator; SkyNexus has not independently audited them.','Targets crossing training/calibration/test boundaries are excluded.','A calibrated simulation or retrospective test does not guarantee live forecasting accuracy.']}
