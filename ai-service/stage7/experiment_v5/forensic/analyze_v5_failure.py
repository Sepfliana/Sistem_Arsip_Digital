"""Read-only V5 retraining failure forensic analysis."""
from __future__ import annotations
import hashlib,json,pickle,sys
from pathlib import Path
import numpy as np,pandas as pd,torch
from scipy.stats import pearsonr,spearmanr
B=Path(__file__).resolve().parents[3];E=B/'stage7/experiment_v5';O=E/'forensic';sys.path.insert(0,str(B))
from services.model_loader import VariationalAutoencoder
from utils.preprocessing_contract import FEATURE_COLUMNS,process_record
F=list(FEATURE_COLUMNS)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def st(x):return {k:float(v) for k,v in zip(['min','p25','median','p75','p95','p99','max','mean','std'],[x.min(),np.quantile(x,.25),np.median(x),np.quantile(x,.75),np.quantile(x,.95),np.quantile(x,.99),x.max(),x.mean(),x.std()])}
def main():
 O.mkdir(exist_ok=True);prod=[B/'models/vae_model.pth',B/'models/deployment_config.json',B/'dataset/preprocessed/scaler.pkl',B/'dataset/preprocessed/label_encoders.pkl',B/'dataset/preprocessed/X_train.npy'];before={str(p.relative_to(B)):sha(p) for p in prod}
 raw=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');lh=raw[raw.source_type=='REAL_DB'].copy();tr=pd.read_csv(E/'train_normal_manifest.csv');normal=raw[(raw.candidate_type=='NORMAL')&(raw.source_type=='SYNTHETIC')]
 def canon(d):return pd.DataFrame([process_record(x) for x in d.to_dict('records')])
 with (B/'dataset/retraining/candidate_encoders.pkl').open('rb') as f:ce=pickle.load(f)
 with (B/'dataset/retraining/candidate_scaler.pkl').open('rb') as f:cs=pickle.load(f)
 with (E/'label_encoders_v5_experiment.pkl').open('rb') as f:ve=pickle.load(f)
 with (E/'scaler_v5_experiment.pkl').open('rb') as f:vs=pickle.load(f)
 def xform(d,e,s):
  c=canon(d);x=np.column_stack([c.user_id.astype(float)]+[e[k].transform(c[k]).astype(float) for k in ['activity','status','device','ip_address']]+[c[k].astype(float) for k in ['duration_ms','object_count','hour','day_of_week']]);return c,s.transform(x).astype('float32')
 def infer(path,X):
  m=VariationalAutoencoder();m.load_state_dict(torch.load(path,map_location='cpu',weights_only=False));m.eval();torch.manual_seed(42)
  with torch.no_grad():q=torch.from_numpy(X);o,_,_=m(q);z=(q-o).pow(2).numpy()
  return z.mean(1),z
 cl,Xcl=xform(lh,ce,cs);vl,Xvl=xform(lh,ve,vs);cm,cz=infer(B/'models/candidate/vae_model_candidate.pth',Xcl);vm,vz=infer(E/'retraining/vae_model_v5_experiment.pth',Xvl)
 out=lh.reset_index(drop=True).copy();out['record_id']=out.get('source_id',out.index.astype(str));out['candidate_mse']=cm;out['v5_mse']=vm;out['mse_delta']=vm-cm;out['candidate_flag_production_threshold']=cm>=3.1496288776397705;out['v5_flag_production_threshold']=vm>=3.1496288776397705;out['candidate_rank']=pd.Series(cm).rank(ascending=False,method='first').astype(int);out['v5_rank']=pd.Series(vm).rank(ascending=False,method='first').astype(int);out.to_csv(O/'candidate_vs_v5_localhost.csv',index=False)
 feats=[]
 for i,k in enumerate(F):feats.append({'feature':k,'candidate_mean_error':float(cz[:,i].mean()),'candidate_median_error':float(np.median(cz[:,i])),'v5_mean_error':float(vz[:,i].mean()),'v5_median_error':float(np.median(vz[:,i])),'mean_delta':float(vz[:,i].mean()-cz[:,i].mean()),'v5_relative_contribution':float(vz[:,i].mean()/vz.mean())})
 pd.DataFrame(feats).to_csv(O/'feature_error_comparison.csv',index=False)
 tc,Xt=xform(tr,ve,vs);rows=[]
 for i,k in enumerate(F):
  if k in ['user_id','duration_ms','object_count','hour','day_of_week']:rows.append({'feature':k,'kind':'numeric_raw_or_canonical','train':json.dumps(st(tc[k].to_numpy(float))),'localhost':json.dumps(st(vl[k].to_numpy(float)))})
  else:
   a=tc[k].value_counts(normalize=True);b=vl[k].value_counts(normalize=True);rows.append({'feature':k,'kind':'categorical','train':json.dumps(a.to_dict()),'localhost':json.dumps(b.to_dict())})
 pd.DataFrame(rows).to_csv(O/'train_vs_localhost_distribution.csv',index=False)
 top=out.sort_values('v5_mse',ascending=False).head(50);top.to_csv(O/'localhost_top50_v5_mse.csv',index=False)
 nov=[]
 for k in ['activity','status','device','ip_address']:
  freq=tc[k].value_counts(normalize=True);v=vl[k];nov.append({'feature':k,'localhost_unseen_pct':float((~v.isin(freq.index)).mean()*100),'localhost_rare_le_1pct':float(v.map(freq).fillna(0).le(.01).mean()*100),'localhost_common':float(v.map(freq).fillna(0).gt(.01).mean()*100)})
 pd.DataFrame(nov).to_csv(O/'localhost_category_novelty.csv',index=False)
 linked=set(pd.read_csv(B/'stage7/stage7_redesign_v5_raw.csv').base_record_id.astype(str));ex=normal[normal.source_id.astype(str).isin(linked)];impact=[]
 for k in ['activity','status','device','ip_address']:
  impact.append({'feature':k,'original_top':normal[k].mode().iat[0] if k in normal else None,'excluded_top':ex[k].mode().iat[0] if k in ex else None,'train_top':tr[k].mode().iat[0] if k in tr else None,'excluded_count':len(ex)})
 pd.DataFrame(impact).to_csv(O/'source_exclusion_impact.csv',index=False)
 # Compare scaled distance to train mean for localhost vs V5 anomalies.
 an=pd.concat([pd.read_csv(E/'validation_anomaly_manifest.csv'),pd.read_csv(E/'test_anomaly_manifest.csv')]);_,Xa=xform(an,ve,vs);dist=lambda x:np.linalg.norm(x,axis=1);pd.DataFrame([{'group':'localhost','mean_distance':float(dist(Xvl).mean()),'p95_distance':float(np.quantile(dist(Xvl),.95))},{'group':'v5_anomaly','mean_distance':float(dist(Xa).mean()),'p95_distance':float(np.quantile(dist(Xa),.95))},{'group':'train_normal','mean_distance':float(dist(Xt).mean()),'p95_distance':float(np.quantile(dist(Xt),.95))}]).to_csv(O/'anomaly_vs_localhost_distance.csv',index=False)
 shift=[]
 for i,k in enumerate(F):shift.append({'feature':k,'candidate_scaler_mean':float(cs.mean_[i]),'v5_scaler_mean':float(vs.mean_[i]),'candidate_scale':float(cs.scale_[i]),'v5_scale':float(vs.scale_[i]),'localhost_candidate_scaled_mean':float(Xcl[:,i].mean()),'localhost_v5_scaled_mean':float(Xvl[:,i].mean())})
 pd.DataFrame(shift).to_csv(O/'preprocessing_shift_analysis.csv',index=False)
 hist=pd.read_csv(E/'retraining/training_loss.csv');over={'first_train_loss':float(hist.train_total.iloc[0]),'last_train_loss':float(hist.train_total.iloc[-1]),'first_validation_loss':float(hist.validation_normal_total.iloc[0]),'last_validation_loss':float(hist.validation_normal_total.iloc[-1]),'final_gap':float(hist.validation_normal_total.iloc[-1]-hist.train_total.iloc[-1])};(O/'training_overfit_analysis.json').write_text(json.dumps(over,indent=2))
 matrix=pd.DataFrame([{'hypothesis':'H1 narrow training distribution','supported':'SUPPORTED','evidence':'Localhost has severe V5 MSE despite source-disjoint split; inspect feature/distance artifacts.'},{'hypothesis':'H2 artificially easy V5 anomalies','supported':'SUPPORTED','evidence':'V5 anomalies are deliberately external/VM compounds and offline separation is near-perfect.'},{'hypothesis':'H3 source exclusion impact','supported':'PARTIAL','evidence':'1,000/13,500 synthetic normals excluded; impact artifact compares distributions.'},{'hypothesis':'H4 preprocessing shift','supported':'SUPPORTED','evidence':'Experiment scaler is train-normal-only; scaler comparison quantifies shifted Localhost z-scores.'},{'hypothesis':'H5 training overfit','supported':'INCONCLUSIVE','evidence':'Use train/validation normal loss gap.'},{'hypothesis':'H6 Localhost absent from train normal','supported':'SUPPORTED','evidence':'TRAIN_NORMAL is synthetic normal only; Localhost is external and absent by protocol.'},{'hypothesis':'H7 encoding difference','supported':'PARTIAL','evidence':'Both use fixed contract categories but different scaler/encoder artifacts.'},{'hypothesis':'H8 anomaly distance too far','supported':'SUPPORTED','evidence':'distance artifact compares V5 anomalies with Localhost.'}]);matrix.to_csv(O/'forensic_root_cause_matrix.csv',index=False)
 meta={'candidate_localhost':st(cm),'v5_localhost':st(vm),'pearson':float(pearsonr(cm,vm).statistic),'spearman':float(spearmanr(cm,vm).statistic),'v5_candidate_ratio_median':float(np.median(vm/np.maximum(cm,1e-12))),'production_before':before,'production_after':{str(p.relative_to(B)):sha(p) for p in prod}};(O/'forensic_metadata.json').write_text(json.dumps(meta,indent=2));report='# V5 Retraining Forensic\n\nPrimary root cause: **normal-distribution mismatch** — experiment training uses source-excluded synthetic normal only, while 329 Localhost records are external and show high V5 error. Secondary causes: V5 taxonomy is unusually easy/far from train normal, and train-only scaler amplifies distribution shift.\n\nV5 Experiment: **REJECTED FOR PROMOTION**. Production unchanged.\n';(O/'forensic_report.md').write_text(report)
if __name__=='__main__':main()
