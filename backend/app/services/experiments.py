"""Chronological evaluation. No retrospective labels are manufactured."""
import math
import statistics
import numpy as np
from sklearn.ensemble import IsolationForest, GradientBoostingRegressor


def evaluate(values):
    if len(values)<96 or any(not math.isfinite(float(x)) for x in values):
        raise ValueError('At least 96 finite, chronologically ordered observations are required')
    y=np.asarray(values,dtype=float)
    split=int(len(y)*0.7)
    train=y[:split];test=y[split:]
    # All fitted parameters and thresholds come exclusively from the training window.
    mean=float(train.mean());sd=max(float(train.std()),abs(mean)*0.05,1e-6)
    z=np.abs((test-mean)/sd)
    forest=IsolationForest(n_estimators=100,random_state=42,contamination='auto').fit(train.reshape(-1,1))
    flags=forest.predict(test.reshape(-1,1))==-1
    X=np.array([[y[i-1],y[i-2],y[i-3],i%24] for i in range(3,len(y))])
    Xtrain=X[:split-3];Xtest=X[split-3:]
    actual=y[split:]
    models={}
    predictions={'persistence':y[split-1:-1], 'seasonal_24_observations':y[split-24:len(y)-24]}
    for quantile in (0.1,0.5,0.9):
        model=GradientBoostingRegressor(loss='quantile',alpha=quantile,n_estimators=60,max_depth=2,random_state=42)
        model.fit(Xtrain,train[3:]);models[quantile]=model.predict(Xtest)
    predictions['quantile_gradient_boosting']=models[0.5]
    metrics={name:{'mae':round(float(np.mean(abs(pred-actual))),4),'rmse':round(float(np.sqrt(np.mean((pred-actual)**2))),4)} for name,pred in predictions.items()}
    low=np.minimum(models[.1],models[.9]);high=np.maximum(models[.1],models[.9])
    return {'method_version':'chronological-v1','split':{'training':split,'test':len(test)},'forecast_metrics':metrics,'interval_nominal_coverage':0.8,'interval_observed_coverage':round(float(np.mean((actual>=low)&(actual<=high))),4),'anomaly_counts':{'z_score':int(sum(z>=3)),'isolation_forest':int(sum(flags))},'ground_truth_metrics':None,'limitations':['One-step rolling evaluation; each prediction uses only prior observations.','Seasonal period is 24 observations; use regularly spaced hourly input.','Precision, recall and advance-warning lead time require independently labelled incidents.']}
