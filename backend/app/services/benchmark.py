"""Seeded labelled simulations for methodology tests, never historical validation."""
from datetime import datetime,timedelta,timezone
import hashlib,json
import numpy as np
from sklearn.ensemble import IsolationForest


def dataset(seed=42):
    rng=np.random.default_rng(seed)
    scenarios=[]
    for name,kind in [('normal','normal'),('weather','weather'),('restriction','restriction'),('outage','outage'),('compound','compound'),('recovery','recovery')]:
        n=240;hours=np.arange(n)
        weather=np.maximum(0,8+rng.normal(0,2,n))
        traffic=100+15*np.sin(hours*2*np.pi/24)+rng.normal(0,3,n)
        transit=20+rng.normal(0,2,n)
        quality=np.ones(n,dtype=bool);labels=np.zeros(n,dtype=bool)
        start,end=180,210
        if kind=='weather':weather[start:end]=75;traffic[start:end]-=45;transit[start:end]+=20;labels[start:end]=True
        if kind=='restriction':traffic[start:end]-=55;labels[start:end]=True
        if kind=='outage':quality[start:end]=False;traffic[start:end]=0
        if kind=='compound':traffic[start:end]-=25;transit[start:end]+=15;labels[start:end]=True
        if kind=='recovery':traffic[start:end]-=np.linspace(55,5,end-start);labels[start:end-5]=True
        scenarios.append({'id':name,'dataset_mode':'synthetic','kind':kind,'traffic':traffic.tolist(),'weather':weather.tolist(),'transit':transit.tolist(),'quality':quality.tolist(),'labels':labels.tolist(),'onset_index':start if labels.any() else None})
    return scenarios


def binary_metrics(predicted,actual,onset=None,start=120):
    predicted=np.asarray(predicted,dtype=bool);actual=np.asarray(actual,dtype=bool)
    tp=int(np.sum(predicted & actual));fp=int(np.sum(predicted & ~actual));fn=int(np.sum(~predicted & actual))
    hits=np.flatnonzero(predicted & actual)
    delay=int(hits[0]+start-onset) if onset is not None and len(hits) else None
    return {'true_positives':tp,'false_positives':fp,'false_negatives':fn,
            'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
            'false_alerts':fp,'detection_delay_hours':delay}


def run(seed=42):
    scenarios=dataset(seed)
    methods=['z_score','isolation_forest','quality_aware_fusion']
    totals={m:{'true_positives':0,'false_positives':0,'false_negatives':0,'delays':[]} for m in methods}
    results=[]
    for case in scenarios:
        traffic=np.array(case['traffic']);transit=np.array(case['transit']);weather=np.array(case['weather']);quality=np.array(case['quality'])
        split=120
        expected=np.array([np.mean(traffic[:split][np.arange(split)%24==i%24]) for i in range(len(traffic))])
        residual=traffic-expected
        sd=max(float(residual[:split].std()),1)
        z=np.abs(residual[split:]/sd)
        transit_z=np.abs((transit[split:]-transit[:split].mean())/max(transit[:split].std(),1))
        matrix=np.column_stack([residual/sd,(transit-transit[:split].mean())/max(transit[:split].std(),1)])
        forest=IsolationForest(n_estimators=80,random_state=seed,contamination=.03).fit(matrix[:split])
        predicted={'z_score':z>=3,'isolation_forest':forest.predict(matrix[split:])==-1,
                   'quality_aware_fusion':((z>=3)|(transit_z>=3)) & quality[split:]}
        comparisons=[]
        for method,flags in predicted.items():
            metrics=binary_metrics(flags,case['labels'][split:],case['onset_index'],split)
            comparisons.append(dict(method=method,**metrics))
            for key in ('true_positives','false_positives','false_negatives'):totals[method][key]+=metrics[key]
            if metrics['detection_delay_hours'] is not None:totals[method]['delays'].append(metrics['detection_delay_hours'])
        results.append({'id':case['id'],'dataset_mode':'synthetic','comparisons':comparisons,
                        'weather_associated_hours':int(np.sum((weather>=40)&quality)),
                        'missing_hours':int(np.sum(~quality))})
    comparisons=[]
    for method,total in totals.items():
        tp,fp,fn=(total[k] for k in ('true_positives','false_positives','false_negatives'))
        comparisons.append({'method':method,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
                            'false_alerts':fp,'mean_detection_delay_hours':float(np.mean(total['delays'])) if total['delays'] else None})
    return {'dataset_mode':'synthetic','seed':seed,'dataset_hash':hashlib.sha256(json.dumps(scenarios,sort_keys=True).encode()).hexdigest(),
            'scenarios':results,'comparisons':comparisons,'method_version':'synthetic-benchmark-v1',
            'limitations':['All six cases and their labels are simulated; these metrics are not real-world accuracy.',
                           'Training uses the first 120 hours; evaluation uses the subsequent 120 hours.',
                           'Weather explains a possible disruption; it does not erase the disruption label.',
                           'The fusion ablation tests quality masking and multiple operational signals, not a validated causal model.']}
