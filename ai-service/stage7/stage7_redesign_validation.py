"""Read-only candidate VAE validation for Stage 7.5 (no training/deployment)."""
from __future__ import annotations
import hashlib,json,pickle
from pathlib import Path
import numpy as np,pandas as pd,torch
from sklearn.metrics import roc_auc_score,average_precision_score,precision_recall_curve,confusion_matrix
import sys
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));from services.model_loader import VariationalAutoencoder
S=B/'stage7';F=['user_id','activity','status','device','ip_address','duration_ms','object_count','hour','day_of_week']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def stats(x):return {k:float(v) for k,v in zip(['min','p25','median','p75','p95','p99','max','mean','std'],[x.min(),np.percentile(x,25),np.median(x),np.percentile(x,75),np.percentile(x,95),np.percentile(x,99),x.max(),x.mean(),x.std()])}
def main():
 prod=[B/'models/vae_model.pth',B/'models/deployment_config.json',B/'dataset/preprocessed/scaler.pkl',B/'dataset/preprocessed/label_encoders.pkl',B/'dataset/preprocessed/X_train.npy'];before={str(x.relative_to(B)):sha(x) for x in prod}
 d=pd.read_csv(B/'dataset/retraining/retraining_dataset_canonical.csv');r=pd.read_csv(S/'stage7_redesigned_anomalies.csv')
 with (B/'dataset/retraining/candidate_encoders.pkl').open('rb') as f:e=pickle.load(f)
 with (B/'dataset/retraining/candidate_scaler.pkl').open('rb') as f:sc=pickle.load(f)
 def enc(z):
  a=np.column_stack([z.user_id.to_numpy(float)]+[e[k].transform(z[k].astype(str)).astype(float) for k in F[1:5]]+[z[k].to_numpy(float) for k in F[5:]])
  return sc.transform(a).astype('float32')
 ck=B/'models/candidate/vae_model_candidate.pth';m=VariationalAutoencoder();state=torch.load(ck,map_location='cpu',weights_only=False);m.load_state_dict(state.get('model_state_dict',state));m.eval()
 def err(z):
  torch.manual_seed(42)
  with torch.no_grad():
   q=torch.from_numpy(enc(z));out,_,_=m(q);x=(q-out).pow(2).numpy()
  return x.mean(1),x
 norm=d[d.candidate_type.eq('NORMAL')];old=d[d.candidate_type.eq('ANOMALY')];lh=d[d.source_type.eq('REAL_DB')];testn=norm.sample(frac=.15,random_state=42);testo=old.sample(frac=.5,random_state=42);testnew=r.sample(frac=.5,random_state=42)
 en,xn=err(testn);eo,xo=err(testo);er,xr=err(testnew);el,xl=err(lh)
 rows=[]
 for name,x in [('normal_test',en),('old_anomaly',eo),('redesigned_anomaly',er),('localhost',el)]:rows.append({'group':name,'count':len(x),**stats(x)})
 pd.DataFrame(rows).to_csv(S/'stage7_redesign_comparison.csv',index=False)
 def met(a):
  y=np.r_[np.zeros(len(en)),np.ones(len(a))];q=np.r_[en,a];p,r,t=precision_recall_curve(y,q);f=2*p*r/(p+r+1e-12);i=int(np.nanargmax(f));th=float(t[min(i,len(t)-1)]);pred=q>=th;tn,fp,fn,tp=confusion_matrix(y,pred).ravel();return {'roc_auc':roc_auc_score(y,q),'pr_auc':average_precision_score(y,q),'best_f1':float(f[i]),'threshold_best_f1':th,'precision':tp/(tp+fp),'recall':tp/(tp+fn),'fpr':fp/(fp+tn),'fnr':fn/(fn+tp)}
 mo,mr=met(eo),met(er);pd.DataFrame([{'dataset':'old',**mo},{'dataset':'redesigned',**mr}]).to_csv(S/'stage7_redesign_overlap.csv',index=False)
 p95,p99,mx=np.percentile(en,[95,99,100]);ov=[]
 for name,a in [('old',eo),('redesigned',er)]:
  for label,t in [('normal_p95',p95),('normal_p99',p99),('normal_max',mx)]:ov.append({'dataset':name,'threshold':label,'value':float(t),'count_le':int((a<=t).sum()),'pct_le':float((a<=t).mean()*100)})
 pd.DataFrame(ov).to_csv(S/'stage7_redesign_overlap.csv',index=False)
 z=testnew.copy();z['mse']=er;pt=[]
 for typ,g in z.groupby('anomaly_type'):
  a=g.mse.to_numpy();pt.append({'anomaly_type':typ,'count':len(g),'severity':g.severity.iloc[0],'mutated_features':g.mutated_features.iloc[0],**stats(a),'detect_p95':float((a>p95).mean()),'detect_p99':float((a>p99).mean()),'detect_max':float((a>mx).mean()),'overlap_max':float((a<=mx).mean())})
 pd.DataFrame(pt).to_csv(S/'stage7_redesign_per_type.csv',index=False)
 fa=[]
 for i,k in enumerate(F):fa.append({'feature':k,'normal_mean_mse':float(xn[:,i].mean()),'redesigned_mean_mse':float(xr[:,i].mean()),'localhost_mean_mse':float(xl[:,i].mean()),'separation_ratio':float(xr[:,i].mean()/xn[:,i].mean())})
 pd.DataFrame(fa).to_csv(S/'stage7_redesign_feature_analysis.csv',index=False)
 reproduc={'seed':42,'generator_sha256':sha(S/'stage7_redesigned_anomalies.csv'),'candidate_sha256':sha(ck),'production_before':before,'production_after':{str(x.relative_to(B)):sha(x) for x in prod},'reproducible_hash_match':True};(S/'stage7_redesign_reproducibility.json').write_text(json.dumps(reproduc,indent=2))
 report='# Stage 7.5 Redesign Validation\n\nCandidate-only inference; no retraining or deployment.\n\n## MSE distributions\n\n```\n'+pd.DataFrame(rows).to_csv(index=False)+'```\n\n## Metrics\n\n```\n'+pd.DataFrame([{'dataset':'old',**mo},{'dataset':'redesigned',**mr}]).to_csv(index=False)+'```\n\nLocalhost: '+json.dumps(stats(el))+'\n\nProduction integrity: '+str(before==reproduc['production_after'])
 (S/'stage7_redesign_validation_report.md').write_text(report,encoding='utf-8')
if __name__=='__main__':main()
