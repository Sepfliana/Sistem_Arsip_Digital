"""Read-only V3 validation: raw -> process_record -> candidate artifacts -> VAE."""
from __future__ import annotations
import hashlib,json,pickle,sys
from pathlib import Path
import numpy as np,pandas as pd,torch
from sklearn.metrics import roc_auc_score,average_precision_score,precision_recall_curve,confusion_matrix
B=Path(__file__).resolve().parents[1];S=B/'stage7';sys.path.insert(0,str(B))
from utils.preprocessing_contract import process_record
from services.model_loader import VariationalAutoencoder
F=['user_id','activity','status','device','ip_address','duration_ms','object_count','hour','day_of_week'];T=3.1496288776397705
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def st(x):return {k:float(v) for k,v in zip(['min','p25','median','p75','p95','p99','max','mean','std'],[x.min(),np.quantile(x,.25),np.median(x),np.quantile(x,.75),np.quantile(x,.95),np.quantile(x,.99),x.max(),x.mean(),x.std()])}
def main():
 prod=[B/'models/vae_model.pth',B/'models/deployment_config.json',B/'dataset/preprocessed/scaler.pkl',B/'dataset/preprocessed/label_encoders.pkl',B/'dataset/preprocessed/X_train.npy'];before={str(p.relative_to(B)):sha(p) for p in prod}
 raw=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');v3=pd.read_csv(S/'stage7_redesigned_anomalies_v3_raw.csv');canon=pd.DataFrame([process_record(x) for x in v3.to_dict('records')])
 with (B/'dataset/retraining/candidate_encoders.pkl').open('rb') as f:e=pickle.load(f)
 with (B/'dataset/retraining/candidate_scaler.pkl').open('rb') as f:sc=pickle.load(f)
 def xform(d):
  a=np.column_stack([d.user_id.astype(float)]+[e[k].transform(d[k]).astype(float) for k in F[1:5]]+[d[k].astype(float) for k in F[5:]])
  return sc.transform(a).astype('float32')
 ck=B/'models/candidate/vae_model_candidate.pth';m=VariationalAutoencoder();m.load_state_dict(torch.load(ck,map_location='cpu',weights_only=False));m.eval()
 def mse(d):
  torch.manual_seed(42)
  with torch.no_grad():q=torch.from_numpy(xform(d));o,_,_=m(q);z=(q-o).pow(2).numpy()
  return z.mean(1),z
 # Formal external evaluation: normal test only; V3 never joins X_train_candidate.
 nraw=raw[(raw.candidate_type=='NORMAL')&(raw.source_type=='SYNTHETIC')].sample(frac=.15,random_state=42);ncan=pd.DataFrame([process_record(x) for x in nraw.to_dict('records')]);lhraw=raw[raw.source_type=='REAL_DB'];lhcan=pd.DataFrame([process_record(x) for x in lhraw.to_dict('records')]);en,xn=mse(ncan);ea,xa=mse(canon);el,xl=mse(lhcan)
 p95,p99,mx=np.quantile(en,[.95,.99,1]); rows=[{'group':'normal_test','count':len(en),**st(en)},{'group':'v3_anomaly','count':len(ea),**st(ea)},{'group':'localhost','count':len(el),**st(el)}];pd.DataFrame(rows).to_csv(S/'stage7_v3_anomaly_distribution.csv',index=False)
 y=np.r_[np.zeros(len(en)),np.ones(len(ea))];q=np.r_[en,ea];pr,re,th=precision_recall_curve(y,q);f=2*pr*re/(pr+re+1e-12);i=int(f.argmax());best=float(th[min(i,len(th)-1)]);pred=q>=best;tn,fp,fn,tp=confusion_matrix(y,pred).ravel()
 over=[]
 for label,z in [('normal_p95',p95),('normal_p99',p99),('normal_max',mx)]:over.append({'threshold':label,'value':float(z),'anomaly_le_count':int((ea<=z).sum()),'anomaly_le_pct':float((ea<=z).mean()*100)})
 pd.DataFrame(over).to_csv(S/'stage7_v3_overlap_analysis.csv',index=False)
 pt=[]
 for typ,idx in v3.groupby('anomaly_type').groups.items():
  a=ea[list(idx)];g=v3.loc[list(idx)];pt.append({'anomaly_type':typ,'count':len(a),'severity':g.severity.iloc[0],'mutated_features':g.mutated_features.iloc[0],**st(a),'detect_normal_max':float((a>mx).mean()),'overlap_normal_max':float((a<=mx).mean())})
 pd.DataFrame(pt).to_csv(S/'stage7_v3_per_type_analysis.csv',index=False)
 fa=[]
 for i,k in enumerate(F):fa.append({'feature':k,'normal_error':float(xn[:,i].mean()),'anomaly_error':float(xa[:,i].mean()),'localhost_error':float(xl[:,i].mean()),'ratio':float(xa[:,i].mean()/xn[:,i].mean())})
 pd.DataFrame(fa).to_csv(S/'stage7_v3_feature_mutation_analysis.csv',index=False)
 local={'count':len(el),**st(el),'fpr_production_threshold':float((el>T).mean()),'fpr_best_offline_threshold':float((el>=best).mean())};(S/'stage7_v3_localhost_safety_analysis.json').write_text(json.dumps(local,indent=2))
 result={'seed':42,'candidate_sha256':sha(ck),'v3_sha256':sha(S/'stage7_redesigned_anomalies_v3_raw.csv'),'pipeline':'raw record -> process_record(log1p) -> candidate encoders -> candidate StandardScaler -> VAE','train_file_unchanged':sha(B/'dataset/retraining/X_train_candidate.npy'),'metrics':{'roc_auc':roc_auc_score(y,q),'pr_auc':average_precision_score(y,q),'best_f1':float(f[i]),'best_threshold':best,'precision':tp/(tp+fp),'recall':tp/(tp+fn),'fpr':fp/(fp+tn),'fnr':fn/(fn+tp)},'production_hashes_before':before,'production_hashes_after':{str(p.relative_to(B)):sha(p) for p in prod}}
 (S/'stage7_redesign_v3_reproducibility.json').write_text(json.dumps(result,indent=2))
 # Acceptance requires Localhost safety, reduced overlap, and no weak type below 50% at Normal MAX.
 per_type_pass=all(row['detect_normal_max']>=.5 for row in pt)
 decision='CONDITIONALLY ACCEPTED' if local['fpr_production_threshold']==0 and (ea<=mx).mean()<.5 and per_type_pass else 'REJECTED'
 report='# Stage 7.5 — V3 Validation\n\n## Pipeline\nRaw synthetic mutation → `process_record()` (including `log1p`) → candidate encoders → candidate scaler → existing candidate VAE. No retraining.\n\n## MSE distribution\n```\n'+pd.DataFrame(rows).to_csv(index=False)+'```\n\n## Offline metrics\n```\n'+json.dumps(result['metrics'],indent=2)+'\n```\n\n## Localhost\n```\n'+json.dumps(local,indent=2)+'\n```\n\n## Decision\n**DATASET V3 '+decision+' FOR CONTROLLED RETRAINING REVIEW.**\n\nProduction hashes unchanged: `'+str(before==result['production_hashes_after'])+'`.'
 (S/'stage7_redesign_v3_validation_report.md').write_text(report,encoding='utf-8')
if __name__=='__main__':main()
