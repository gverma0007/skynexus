"""Chronological historical evaluation with purged onset targets and baselines."""
import math
import numpy as np
from app.services.historical import stamp,iso
METHOD_VERSION='historical-chronological-v3'


def report_markdown(data,result):
    def value(v):return 'unavailable' if v is None else f'{v:.5g}' if isinstance(v,float) else str(v)
    lines=[f"# Historical study: {data['id']}",data['description'],f"Dataset SHA-256: `{data['dataset_hash']}`",f"Method: {result['method_version']}; native interval: {data['cadence_hours']} hours.",
           '## Labels and chronological split',data['label_definition'],str(result['split']),
           '## Heldout anomaly detection','False alerts below are native samples, not independent incidents.',
           '| Method | Precision | Recall | F1 | False samples | Event recall | Mean delay (hours) |','|---|---:|---:|---:|---:|---:|---:|']
    for m in result['detection']['comparisons']:lines.append('| '+' | '.join(value(m.get(k)) for k in ('method','precision','recall','f1','false_alerts','event_recall','mean_detection_delay_hours'))+' |')
    f=result['forecast'];lines+=['## Numeric prediction',f"Target: {f['target']} ({f['unit']}); horizon: {f.get('horizon_hours','unavailable')} hours.",'| Method | MAE | RMSE | Scored targets |','|---|---:|---:|---:|']
    for name,m in f.get('forecast_metrics',{}).items():lines.append(f"| {name} | {value(m['mae'])} | {value(m['rmse'])} | {m['samples']} |")
    w=result['advance_warning'];lines+=['## Advance warning',w['status'],w['message'],w['target']]
    for key in ('brier_score','reference_brier_score','brier_skill_score','precision','recall','event_onsets','events_with_advance_warning','mean_warning_lead_hours','false_warning_hours'):
        if key in w:lines.append(f"- {key}: {value(w[key])}")
    lines+=['## Limits']+['- '+line for line in result['limitations']]+['## Provenance']+['- '+s['name']+': '+s['url'] for s in data['provenance']]
    return '\n'.join(lines).encode()


def classification(flags,truth):
    flags=np.asarray(flags,dtype=bool);truth=np.asarray(truth,dtype=bool)
    tp=int(np.sum(flags&truth));fp=int(np.sum(flags&~truth));fn=int(np.sum(~flags&truth))
    p=tp/(tp+fp) if tp+fp else None;r=tp/(tp+fn) if tp+fn else None
    return {'precision':p,'recall':r,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,'true_positives':tp,'false_positives':fp,'false_negatives':fn,'false_alerts':fp,'samples':len(truth)}


def split_indices(data):
    n=len(data['times'])
    if data['label_kind']=='independent_annotations':return int(n*.6),int(n*.8)
    first=next((i for i,v in enumerate(data['labels']) if v),None)
    if first is None or first<32:raise ValueError('Event study needs at least 32 pre-event samples')
    # Entire event is held out; calibrating on its aftermath would leak it.
    return int(first*.8),first


def event_windows(labels,start=0):
    windows=[];i=start
    while i<len(labels):
        if not labels[i]:i+=1;continue
        begin=i
        while i<len(labels) and labels[i]:i+=1
        windows.append((begin,i))
    return windows


def features(values,period,medians):
    """Each row t uses only t-1 and older measurements, never current/future y."""
    n,d=values.shape;columns=[]
    filled=np.where(np.isfinite(values),values,medians)
    for lag in (1,2,max(1,period)):
        previous=np.empty_like(filled);previous[:lag]=medians;previous[lag:]=filled[:-lag]
        missing=np.ones_like(filled);missing[lag:]=~np.isfinite(values[:-lag])
        columns.extend([previous,missing])
    phase=2*np.pi*np.arange(n)/max(1,period)
    columns.extend([np.sin(phase)[:,None],np.cos(phase)[:,None]])
    return np.column_stack(columns)


def predictor(history,at,period,median):
    vals=[]
    for lag in (1,2,max(1,period)):
        value=history[at-lag] if at>=lag else float('nan')
        vals.extend([float(value) if np.isfinite(value) else median,0. if np.isfinite(value) else 1.])
    phase=2*np.pi*at/max(1,period)
    return vals+[math.sin(phase),math.cos(phase)]


def prediction_features(y,origins,step,previous,period,median):
    """Batch recursive origins without copying prefixes or reading future actuals."""
    at=origins+step-1;columns=[]
    for lag in (1,2,max(1,period)):
        indices=at-lag;values=np.full(len(origins),np.nan)
        observed=(indices>=0)&(indices<origins)
        values[observed]=y[indices[observed]]
        recursive=indices>=origins
        values[recursive]=previous[np.flatnonzero(recursive),(indices-origins)[recursive]]
        finite=np.isfinite(values);columns.extend([np.where(finite,values,median),(~finite).astype(float)])
    phase=2*np.pi*at/max(1,period)
    columns.extend([np.array([math.sin(x) for x in phase]),np.array([math.cos(x) for x in phase])])
    return np.column_stack(columns)


def numeric_forecast(y,train_end,test_start,cadence,period,median):
    from sklearn.ensemble import GradientBoostingRegressor
    horizon=max(1,math.ceil(6/cadence))
    train=[i for i in range(max(2,period),train_end) if np.isfinite(y[i])]
    if len(train)<24:return {'status':'insufficient_data','forecast_metrics':{},'by_horizon':{},'message':'At least 24 valid lagged training targets are required.'}
    X=np.array([predictor(y,i,period,median) for i in train])
    models={q:GradientBoostingRegressor(loss='quantile',alpha=q,n_estimators=35,max_depth=2,random_state=42).fit(X,y[train]) for q in (.1,.5,.9)}
    available=np.arange(test_start,len(y)-horizon+1)
    if not len(available):return {'status':'insufficient_data','forecast_metrics':{},'by_horizon':{}}
    # Uniform deterministic origin subsampling is independent of values/labels.
    origins=np.unique(np.linspace(available[0],available[-1],min(96,len(available)),dtype=int))
    selected=sorted({1,max(1,math.ceil(3/cadence)),horizon})
    errors={h:{name:[] for name in ('persistence','seasonal','quantile_gradient_boosting')} for h in selected};coverage=[];predictions=[];evaluated_origins=0
    candidate_count=len(origins);origins=origins[np.isfinite(y[origins-1])];evaluated_origins=len(origins)
    paths={q:np.full((len(origins),horizon),np.nan) for q in models}
    for step in range(1,horizon+1):
        estimates={}
        for q,model in models.items():
            estimates[q]=model.predict(prediction_features(y,origins,step,paths[q],period,median)) if len(origins) else np.array([])
            paths[q][:,step-1]=estimates[q]
        if step not in selected:continue
        for k,origin in enumerate(origins):
            if not np.isfinite(y[origin+step-1]):continue
            actual=float(y[origin+step-1]);season_index=origin+step-1-period
            # Recursive seasonal baseline uses only values before the origin.
            while season_index>=origin:season_index-=period
            seasonal=float(y[season_index]) if season_index>=0 and np.isfinite(y[season_index]) else float(y[origin-1])
            candidates={'persistence':float(y[origin-1]),'seasonal':seasonal,'quantile_gradient_boosting':float(estimates[.5][k])}
            for name,value in candidates.items():errors[step][name].append(value-actual)
            low,high=min(float(v[k]) for v in estimates.values()),max(float(v[k]) for v in estimates.values())
            if step==horizon:coverage.append(low<=actual<=high)
            predictions.append({'origin_index':int(origin),'target_index':int(origin+step-1),'horizon_hours':round(step*cadence,6),'actual':actual,'value':float(estimates[.5][k]),'low':low,'high':high})
    predictions.sort(key=lambda p:(p['origin_index'],p['target_index']))
    metrics={str(round(h*cadence,6)):{name:{'mae':float(np.mean(np.abs(err))),'rmse':float(np.sqrt(np.mean(np.square(err)))),'samples':len(err)} for name,err in methods.items() if err} for h,methods in errors.items()}
    return {'status':'heldout_evaluated','horizon_hours':round(horizon*cadence,6),'forecast_metrics':metrics.get(str(round(horizon*cadence,6)),{}),'by_horizon':metrics,
            'interval_nominal_coverage':.8,'interval_observed_coverage':float(np.mean(coverage)) if coverage else None,'origins_evaluated':evaluated_origins,'candidate_origins':candidate_count,'predictions':predictions}


def warning(data,X,quality,labels,train_end,test_start,cadence):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    horizon=max(1,math.ceil(6/cadence));n=len(labels)
    result={'status':'insufficient_labels','target':'Annotated anomaly-window onset in the next '+str(round(horizon*cadence,6))+' hours, conditional on being outside a labelled window.',
            'horizon_hours':round(horizon*cadence,6),'message':'Training and calibration must each contain normal and pre-onset examples. A single heldout incident cannot train a validated warning classifier.'}
    if data['id']=='faa-notam-2023':
        return dict(result,status='unsupported_source_availability',message='BTS outcomes were published later and have no original per-record availability timestamp; they cannot substantiate a live advance-warning claim.')
    onset=labels & ~np.r_[False,labels[:-1]]
    target=np.array([onset[i+1:i+horizon+1].any() for i in range(n-horizon)])
    # Horizon targets crossing either split boundary are purged in full.
    train=np.array([i for i in range(2,train_end-horizon) if quality[i-1] and not labels[i]])
    calibration=np.array([i for i in range(train_end,test_start-horizon) if quality[i-1] and not labels[i]])
    test=np.array([i for i in range(test_start,n-horizon) if quality[i-1] and not labels[i]])
    result['purge_samples_per_boundary']=horizon
    if any(not len(indices) or len(np.unique(target[indices]))<2 for indices in (train,calibration)) or not len(test):return result
    model=make_pipeline(StandardScaler(),LogisticRegression(max_iter=500,random_state=42,class_weight='balanced')).fit(X[train],target[train])
    calibrator=LogisticRegression(max_iter=500,random_state=42).fit(model.decision_function(X[calibration]).reshape(-1,1),target[calibration])
    calibrated=calibrator.predict_proba(model.decision_function(X[calibration]).reshape(-1,1))[:,1]
    candidates=[]
    # Rare-event probabilities can all be below 1%; select the operating point
    # from calibration probability quantiles rather than an arbitrary 0.01 grid.
    thresholds=np.unique(np.r_[0.,np.quantile(calibrated,np.linspace(0,1,201)),1.])
    for threshold in thresholds:
        m=classification(calibrated>=threshold,target[calibration]);candidates.append((m['f1'] or 0,m['precision'] or 0,float(threshold)))
    threshold=max(candidates)[2]
    probability=calibrator.predict_proba(model.decision_function(X[test]).reshape(-1,1))[:,1];truth=target[test];flags=probability>=threshold
    metrics=classification(flags,truth);base=float(target[train].mean())
    brier=float(np.mean((probability-truth)**2));reference=float(np.mean((base-truth)**2))
    onsets=[i for i in range(test_start,n) if onset[i]];leads=[]
    for event in onsets:
        before=[(event-i)*cadence for k,i in enumerate(test) if 0<event-i<=horizon and flags[k]]
        if before:leads.append(max(before))
    bins=[]
    for low in (0,.2,.4,.6,.8):
        selected=(probability>=low)&(probability<(low+.2 if low<.8 else 1.000001))
        bins.append({'lower':low,'upper':low+.2,'samples':int(selected.sum()),'mean_probability':float(probability[selected].mean()) if selected.any() else None,'observed_rate':float(truth[selected].mean()) if selected.any() else None})
    skill=1-brier/reference if reference>0 else None
    message='Heldout onset warning evaluation. '+('Brier score improves on the training-prevalence baseline.' if skill is not None and skill>0 else 'No positive Brier skill over the prevalence baseline was measured.')
    if not leads:message+=' No heldout event onset was warned at the calibration-selected threshold.'
    return dict(result,status='heldout_evaluated',message=message,
                **metrics,brier_score=brier,reference_brier_score=reference,brier_skill_score=skill,threshold=threshold,
                event_onsets=len(onsets),events_with_advance_warning=len(leads),event_recall=len(leads)/len(onsets) if onsets else None,
                mean_warning_lead_hours=float(np.mean(leads)) if leads else None,false_warning_hours=metrics['false_alerts']*cadence,
                reliability_bins=bins,predictions=[{'time':data['times'][int(i)],'index':int(i),'probability':float(p),'outcome':bool(target[i])} for i,p in zip(test,probability)],
                comparisons=[{'method':'calibrated_logistic_onset','brier_score':brier,'precision':metrics['precision'],'recall':metrics['recall']},{'method':'training_prevalence','brier_score':reference,'precision':None,'recall':None}])


def evaluate(data):
    from sklearn.ensemble import IsolationForest
    from importlib.metadata import version
    import sys
    cadence=float(data['cadence_hours']);times=[stamp(t) for t in data['times']];n=len(times)
    if n<64 or n>100000:raise ValueError('Historical evaluation requires 64 to 100000 ordered samples')
    if any(abs((b-a).total_seconds()-cadence*3600)>.01 for a,b in zip(times,times[1:])):raise ValueError('Historical timeline must preserve a regular native cadence')
    matrix=np.array([[float(v) if v is not None else np.nan for v in c['values']] for c in data['channels']],dtype=float).T
    if len(matrix)!=n or len(data['labels'])!=n:raise ValueError('Historical channels and labels must align')
    labels=np.asarray(data['labels'],dtype=bool);train_end,test_start=split_indices(data)
    if train_end<24 or test_start-train_end<8 or n-test_start<8:raise ValueError('Insufficient chronological training/calibration/test observations')
    normal=np.arange(n)<train_end;normal&=~labels
    medians=np.array([np.nanmedian(c[normal]) if np.isfinite(c[normal]).any() else 0 for c in matrix.T])
    spread=np.array([max(float(np.nanstd(c[normal])),abs(float(m))*.05,1e-6) if np.isfinite(c[normal]).any() else 1. for c,m in zip(matrix.T,medians)])
    period=max(1,round(24/cadence)) if cadence<24 else 7
    primary=matrix[:,0];quality=np.isfinite(primary);filled=np.where(np.isfinite(matrix),matrix,medians)
    z=(filled-medians)/spread
    seasonal=np.full(n,medians[0])
    for phase in range(period):
        rows=normal & quality & (np.arange(n)%period==phase)
        if rows.sum()>=3:seasonal[np.arange(n)%period==phase]=float(np.mean(primary[rows]))
    residual=primary-seasonal
    sigma=max(float(np.nanstd(residual[normal&quality])),abs(medians[0])*.05,1e-6)
    z_primary=np.nan_to_num(abs(residual)/sigma,nan=0)
    normal_rows=normal & quality
    if normal_rows.sum()<24:raise ValueError('At least 24 observed normal training samples are required')
    model=IsolationForest(random_state=42,n_estimators=80,contamination=.03).fit(z[normal_rows])
    scores=-model.score_samples(z)
    calibration=np.arange(n);cal_mask=(calibration>=train_end)&(calibration<test_start)&quality&~labels
    threshold=float(np.quantile(scores[cal_mask],.99)) if cal_mask.sum()>=8 else float(np.quantile(scores[normal_rows],.99))
    flags={'seasonal_z_score':(z_primary>=3)&quality,'isolation_forest':(scores>=threshold)&quality,
           'quality_aware_fusion':((z_primary>=3)|(np.max(abs(z),axis=1)>=3))&quality}
    valid=(np.arange(n)>=test_start)&quality
    windows=event_windows(labels,test_start);comparisons=[]
    for name,alarms in flags.items():
        metrics=classification(alarms[valid],labels[valid]);delays=[]
        for begin,end in windows:
            hits=np.flatnonzero(alarms[begin:end]&quality[begin:end])
            if len(hits):delays.append(float(hits[0]*cadence))
        comparisons.append(dict(method=name,**metrics,mean_detection_delay_hours=float(np.mean(delays)) if delays else None,event_recall=len(delays)/len(windows) if windows else None))
    X=features(matrix,period,medians)
    forecast=numeric_forecast(primary,train_end,test_start,cadence,period,medians[0]);forecast.update(target=data['channels'][0]['label'],unit=data['channels'][0]['unit'])
    advanced=warning(data,X,quality,labels,train_end,test_start,cadence)
    return {'case_id':data['id'],'dataset_mode':'historical','dataset_hash':data['dataset_hash'],'method_version':METHOD_VERSION,
            'cadence_hours':cadence,'training_observations':train_end,'calibration_observations':test_start-train_end,'test_observations':n-test_start,
            'software_versions':{'python':sys.version.split()[0],**{name:version(name) for name in ('numpy','scikit-learn','pandas')}},
            'parameters':{'seed':42,'seasonal_period_samples':period,'normalizer_medians':medians.tolist(),'normalizer_scales':spread.tolist(),'z_threshold':3,'isolation_forest_trees':80,'isolation_calibration_quantile':.99,'warning_horizon_hours':6,'warning_threshold_selection':'maximum calibration F1 over 201 probability quantiles','forecast_trees':35,'forecast_max_depth':2,'forecast_quantiles':[.1,.5,.9],'quantile_crossing_correction':'interval encloses all three predicted quantiles'},
            'split':{'training':train_end,'calibration':test_start-train_end,'test':n-test_start},'split_time':data['times'][test_start],
            'detection':{'status':'heldout_evaluated','label_definition':data['label_definition'],'label_kind':data['label_kind'],'comparisons':comparisons,
                         'missing_test_samples':int((~quality[test_start:]).sum()),'test_event_windows':len(windows),'predictions':[{'time':data['times'][i],'label':bool(labels[i]),'quality':bool(quality[i]),'alarms':{name:bool(alarms[i]) for name,alarms in flags.items()}} for i in range(test_start,n)]},
            'forecast':forecast,'advance_warning':advanced,
            'limitations':data['limitations']+['Models and normalization fit training observations only; IF thresholds and warning calibration use the separate calibration interval.','Anomaly normal-training selection uses the supplied training labels. Missing primary measurements are excluded from scoring, not treated as zero.','Numeric forecasts use at most 96 uniformly spaced heldout origins and no future actuals in recursive paths. These are retrospective archive tests.','Warning features use strictly earlier samples. Targets crossing split boundaries are purged; ongoing labelled windows are excluded from onset-warning metrics.','False-alert counts are sample counts at the native cadence, not independent incident counts. No aggregate cross-case accuracy is inferred.','These are retrospective point estimates on few events, not statistical proof of generalization or validated live advance-warning capability.']}
