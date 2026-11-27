"""Hourly causal forecasts with rolling-origin, horizon-specific evaluation."""
from datetime import timedelta
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor


def predictors(values, at):
    return [values[at-1],values[at-2],values[at-3],values[at-24],at%24]


def forecast(values,times,horizon=6):
    if not 1<=horizon<=24:raise ValueError('Forecast horizon must be between 1 and 24 hours')
    if len(values)<96:raise ValueError('At least 96 complete hourly observations are required')
    y=np.asarray(values,dtype=float)
    if not np.isfinite(y).all():raise ValueError('Series must contain finite values')
    if any((b-a).total_seconds()!=3600 for a,b in zip(times,times[1:])):
        raise ValueError('Series must have consecutive hourly observations; gaps are not zero activity')
    # Keep workload bounded while retaining temporal ordering.
    y=y[-720:];times=times[-720:]
    split=int(len(y)*.7)
    indices=list(range(24,split))
    X=np.array([predictors(y,i) for i in indices]);target=y[indices]
    models={q:GradientBoostingRegressor(loss='quantile',alpha=q,n_estimators=40,max_depth=2,random_state=42).fit(X,target) for q in (.1,.5,.9)}
    errors={h:{'persistence':[],'seasonal_24_hours':[],'quantile_gradient_boosting':[]} for h in range(1,horizon+1)}
    coverage={h:[] for h in range(1,horizon+1)}
    # Each origin only observes the prefix; recursive predictions never receive future actuals.
    for origin in range(split,min(len(y)-horizon+1,split+168)):
        paths={q:list(y[:origin]) for q in models}
        for step in range(1,horizon+1):
            predictions={}
            for q,model in models.items():
                predictions[q]=float(model.predict([predictors(paths[q],len(paths[q]))])[0]);paths[q].append(predictions[q])
            actual=float(y[origin+step-1])
            estimates={'persistence':float(y[origin-1]),'seasonal_24_hours':float(y[origin+step-1-24]),'quantile_gradient_boosting':predictions[.5]}
            for method,value in estimates.items():errors[step][method].append(value-actual)
            low,high=sorted((predictions[.1],predictions[.9]));coverage[step].append(low<=actual<=high)
    metrics={}
    for h,methods in errors.items():
        metrics[str(h)]={method:{'mae':float(np.mean(abs(np.array(err)))),'rmse':float(np.sqrt(np.mean(np.array(err)**2))),'samples':len(err)} for method,err in methods.items() if err}
    # Final issuance refits on all available prior data, not on the holdout forecast errors.
    fullX=np.array([predictors(y,i) for i in range(24,len(y))])
    for model in models.values():model.fit(fullX,y[24:])
    paths={q:list(y) for q in models};points=[]
    for step in range(1,horizon+1):
        estimates={}
        for q,model in models.items():
            estimates[q]=float(model.predict([predictors(paths[q],len(paths[q]))])[0]);paths[q].append(estimates[q])
        low,high=sorted((estimates[.1],estimates[.9]))
        points.append({'time':(times[-1]+timedelta(hours=step)).isoformat(),'value':estimates[.5],'low':min(low,estimates[.5]),'high':max(high,estimates[.5])})
    return {'method':'Recursive quantile gradient boosting','points':points,'evaluation':{'forecast_metrics':metrics.get('1',{}),'by_horizon':metrics,'interval_nominal_coverage':.8,'interval_observed_coverage':float(np.mean(coverage[1])) if coverage[1] else None,'interval_coverage_by_horizon':{str(h):float(np.mean(v)) if v else None for h,v in coverage.items()},'training_observations':split,'test_observations':len(y)-split},'limitations':['Intervals are empirical quantile estimates; coverage is measured, not guaranteed.','Retrospective archive evaluation is not proof that the input was available live at its original observation time.','A statistical forecast does not establish cause or operational safety.']}
