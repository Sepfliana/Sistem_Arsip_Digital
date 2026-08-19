"""V5 direct-disk candidate validation; read-only production."""
from __future__ import annotations
import hashlib,json,pickle,sys
from pathlib import Path
import numpy as np,pandas as pd,torch
from sklearn.metrics import roc_auc_score,average_precision_score,precision_recall_curve,confusion_matrix
B=Path(__file__).resolve().parents[1];S=B/'stage7';sys.path.insert(0,str(B))
from utils.preprocessing_contract import process_record
from services.model_loader import VariationalAutoencoder
F=['user_id','activity','status','device','ip_address','duration_ms','object_count','hour','day_of_week'];PROD=3.1496288776397705
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def st(x):return {k:float(v) for k,v in zip(['min','p25','median','p75','p95','p99','max','mean','std'],[x.min(),np.quantile(x,.25),np.median(x),np.quantile(x,.75),np.quantile(x,.95),np.quantile(x,.99),x.max(),x.mean(),x.std()])}
def main():
 prod=[B/'models/vae_model.pth',B/'models/deployment_config.json',B/'dataset/preprocessed/scaler.pkl',B/'dataset/preprocessed/label_encoders.pkl',B/'dataset/preprocessed/X_train.npy'];before={str(p.relative_to(B)):sha(p) for p in prod};raw=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');v=pd.read_csv(S/'stage7_redesign_v5_raw.csv');n=raw[(raw.candidate_type=='NORMAL')&(raw.source_type=='SYNTHETIC')].sample(frac=.15,random_state=42);lh=raw[raw.source_type=='REAL_DB']
 def c(d):return pd.DataFrame([process_record(x) for x in d.to_dict('records')])
 with (B/'dataset/retraining/candidate_encoders.pkl').open('rb') as f:e=pickle.load(f)
 with (B/'dataset/retraining/candidate_scaler.pkl').open('rb') as f:sc=pickle.load(f)
 def x(d):return sc.transform(np.column_stack([d.user_id.astype(float)]+[e[k].transform(d[k]).astype(float) for k in F[1:5]]+[d[k].astype(float) for k in F[5:]])).astype('float32')
 m=VariationalAutoencoder();ck=B/'models/candidate/vae_model_candidate.pth';m.load_state_dict(torch.load(ck,map_location='cpu',weights_only=False));m.eval()
 def mse(d):
  torch.manual_seed(42)
  with torch.no_grad():q=torch.from_numpy(x(c(d)));o,_,_=m(q);return (q-o).pow(2).mean(1).numpy()
 en,ea,el=mse(n),mse(v),mse(lh);p95,p99,mx=np.quantile(en,[.95,.99,1]);v['reconstruction_mse']=ea;pt=[]
 for typ,g in v.groupby('anomaly_type'):
  a=g.reconstruction_mse.to_numpy();pt.append({'anomaly_type':typ,'count':len(a),**st(a),'detect_p95':float((a>p95).mean()),'detect_p99':float((a>p99).mean()),'detect_max':float((a>mx).mean()),'overlap_max':float((a<=mx).mean())})
 pd.DataFrame(pt).to_csv(S/'stage7_v5_per_type_analysis.csv',index=False);ov=[]
 for name,t in [('normal_p95',p95),('normal_p99',p99),('normal_max',mx)]:ov.append({'threshold':name,'value':float(t),'count_le':int((ea<=t).sum()),'pct_le':float((ea<=t).mean()*100)})
 pd.DataFrame(ov).to_csv(S/'stage7_v5_overlap_analysis.csv',index=False);y=np.r_[np.zeros(len(en)),np.ones(len(ea))];q=np.r_[en,ea];pr,re,th=precision_recall_curve(y,q);f=2*pr*re/(pr+re+1e-12);i=int(f.argmax());best=float(th[min(i,len(th)-1)]);pred=q>=best;tn,fp,fn,tp=confusion_matrix(y,pred).ravel();local={'mse':st(el),'production_threshold':{'value':PROD,'fpr':float((el>=PROD).mean()),'fp':int((el>=PROD).sum())},'normal_max':{'value':float(mx),'fpr':float((el>=mx).mean()),'fp':int((el>=mx).sum())},'best_offline':{'value':best,'fpr':float((el>=best).mean()),'fp':int((el>=best).sum())}};(S/'stage7_v5_localhost_safety.json').write_text(json.dumps(local,indent=2))
 rep={'seed':42,'hash':sha(S/'stage7_redesign_v5_raw.csv'),'candidate_hash':sha(ck),'production_before':before,'production_after':{str(p.relative_to(B)):sha(p) for p in prod},'metrics':{'roc_auc':roc_auc_score(y,q),'pr_auc':average_precision_score(y,q),'best_f1':float(f[i]),'best_threshold':best,'precision':tp/(tp+fp),'recall':tp/(tp+fn),'fpr':fp/(fp+tn),'fnr':fn/(fn+tp)}};(S/'stage7_v5_reproducibility.json').write_text(json.dumps(rep,indent=2))
 report='# Stage 7.5 — V5 Validation\n\nMass archive removed: the feature set cannot observe extraction volume. Scripted rapid failure excluded: joint-rare but model-indistinguishable.\n\n## Metrics\n```\n'+json.dumps(rep['metrics'],indent=2)+'\n```\n\n## Per type\n```\n'+pd.DataFrame(pt).to_csv(index=False)+'```\n\n## Localhost\n```\n'+json.dumps(local,indent=2)+'\n```\n\n**V5 DATASET ACCEPTED FOR CONTROLLED RETRAINING REVIEW** only if production hashes match and Localhost production FPR is zero; this is not authorization to retrain.\n';(S/'stage7_redesign_v5_validation_report.md').write_text(report)
if __name__=='__main__':main()
