"""Authorized V5 experiment-only PyTorch VAE retraining. Never writes production/candidate."""
from __future__ import annotations
import hashlib,json,platform,pickle,random,sys
from pathlib import Path
import numpy as np,pandas as pd,torch
import torch.nn.functional as F
from torch.utils.data import DataLoader,TensorDataset
from sklearn.metrics import roc_auc_score,average_precision_score,precision_recall_curve,confusion_matrix
B=Path(__file__).resolve().parents[2];E=Path(__file__).resolve().parent;O=E/'retraining';sys.path.insert(0,str(B))
from services.model_loader import VariationalAutoencoder
from utils.preprocessing_contract import FEATURE_COLUMNS,process_record
SEED=42;EPOCHS=100;BS=64;LR=.001;BETA=.001;PROD=3.1496288776397705
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for z in iter(lambda:f.read(1048576),b''):h.update(z)
 return h.hexdigest()
def st(x):return {k:float(v) for k,v in zip(['min','p25','median','p75','p95','p99','max','mean','std'],[x.min(),np.quantile(x,.25),np.median(x),np.quantile(x,.75),np.quantile(x,.95),np.quantile(x,.99),x.max(),x.mean(),x.std()])}
def main():
 random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED);torch.use_deterministic_algorithms(True,warn_only=True);O.mkdir(exist_ok=True)
 prod=[B/'models/vae_model.pth',B/'models/deployment_config.json',B/'dataset/preprocessed/scaler.pkl',B/'dataset/preprocessed/label_encoders.pkl',B/'dataset/preprocessed/X_train.npy'];before={str(p.relative_to(B)):sha(p) for p in prod}
 with (E/'label_encoders_v5_experiment.pkl').open('rb') as f:enc=pickle.load(f)
 with (E/'scaler_v5_experiment.pkl').open('rb') as f:sc=pickle.load(f)
 def load(name):return pd.read_csv(E/name)
 tr,va,te,ava,ate=map(load,['train_normal_manifest.csv','validation_normal_manifest.csv','test_normal_manifest.csv','validation_anomaly_manifest.csv','test_anomaly_manifest.csv'])
 raw=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');lh=raw[raw.source_type=='REAL_DB']
 def xform(d):
  c=pd.DataFrame([process_record(x) for x in d.to_dict('records')]);x=np.column_stack([c.user_id.astype(float)]+[enc[k].transform(c[k]).astype(float) for k in ['activity','status','device','ip_address']]+[c[k].astype(float) for k in ['duration_ms','object_count','hour','day_of_week']]);return sc.transform(x).astype('float32')
 Xtr,Xv,Xt,Xva,Xta,Xlh=map(xform,[tr,va,te,ava,ate,lh]);device=torch.device('cuda' if torch.cuda.is_available() else 'cpu');m=VariationalAutoencoder().to(device);opt=torch.optim.Adam(m.parameters(),lr=LR);gen=torch.Generator().manual_seed(SEED);loader=DataLoader(TensorDataset(torch.from_numpy(Xtr)),batch_size=BS,shuffle=True,generator=gen);hist=[]
 for ep in range(EPOCHS):
  m.train();tot=rec=kl=0.
  for (x,) in loader:
   x=x.float().to(device);opt.zero_grad();o,mu,lv=m(x);r=F.mse_loss(o,x);k=-.5*torch.mean(1+lv-mu.pow(2)-lv.exp());loss=r+BETA*k;loss.backward();opt.step();tot+=loss.item()*len(x);rec+=r.item()*len(x);kl+=k.item()*len(x)
  m.eval();
  with torch.no_grad():q=torch.from_numpy(Xv).float().to(device);o,mu,lv=m(q);vr=F.mse_loss(o,q).item();vk=(-.5*torch.mean(1+lv-mu.pow(2)-lv.exp())).item()
  hist.append({'epoch':ep+1,'train_total':tot/len(Xtr),'train_reconstruction':rec/len(Xtr),'train_kl':kl/len(Xtr),'validation_normal_total':vr+BETA*vk,'validation_normal_reconstruction':vr,'validation_normal_kl':vk})
 ck=O/'vae_model_v5_experiment.pth';torch.save(m.state_dict(),ck);m2=VariationalAutoencoder().to(device);m2.load_state_dict(torch.load(ck,map_location=device,weights_only=False));m2.eval()
 def mse(X):
  torch.manual_seed(SEED)
  with torch.no_grad():q=torch.from_numpy(X).float().to(device);o,_,_=m2(q);return (q-o).pow(2).mean(1).cpu().numpy()
 ev,et,eva,eta,elh=map(mse,[Xv,Xt,Xva,Xta,Xlh]);yval=np.r_[np.zeros(len(ev)),np.ones(len(eva))];qval=np.r_[ev,eva];pr,re,th=precision_recall_curve(yval,qval);f=2*pr*re/(pr+re+1e-12);i=int(f.argmax());threshold=float(th[min(i,len(th)-1)]);y=np.r_[np.zeros(len(et)),np.ones(len(eta))];q=np.r_[et,eta];pred=q>=threshold;tn,fp,fn,tp=confusion_matrix(y,pred).ravel();metrics={'roc_auc':roc_auc_score(y,q),'pr_auc':average_precision_score(y,q),'threshold_selected_on_validation':threshold,'precision':tp/(tp+fp),'recall':tp/(tp+fn),'f1':2*tp/(2*tp+fp+fn),'fpr':fp/(fp+tn),'fnr':fn/(fn+tp)}
 dist=pd.DataFrame([{'group':'validation_normal',**st(ev)},{'group':'test_normal',**st(et)},{'group':'validation_anomaly',**st(eva)},{'group':'test_anomaly',**st(eta)},{'group':'localhost',**st(elh)}]);dist.to_csv(O/'evaluation_distributions.csv',index=False);pd.DataFrame(hist).to_csv(O/'training_loss.csv',index=False);(O/'training_history.json').write_text(json.dumps(hist,indent=2));cfg={'seed':SEED,'epochs':EPOCHS,'batch_size':BS,'learning_rate':LR,'beta_kl':BETA,'architecture':'9-64-32-8-32-64-9 ReLU Dropout(0.2)','device':str(device),'torch':torch.__version__,'python':platform.python_version(),'scaler':'experiment_v5 TRAIN_NORMAL only','encoder':'fixed preprocessing-contract vocabulary'};(O/'training_config.json').write_text(json.dumps(cfg,indent=2))
 meta={'checkpoint_sha256':sha(ck),'candidate_reference_sha256':sha(B/'models/candidate/vae_model_candidate.pth'),'checkpoint_reload':'PASS','metrics':metrics,'localhost':{'production_threshold_fpr':float((elh>=PROD).mean()),'production_threshold_fp':int((elh>=PROD).sum()),'validation_threshold_fpr':float((elh>=threshold).mean()),'validation_threshold_fp':int((elh>=threshold).sum())},'production_before':before,'production_after':{str(p.relative_to(B)):sha(p) for p in prod}};(O/'experiment_metadata.json').write_text(json.dumps(meta,indent=2));(O/'model_summary.json').write_text(json.dumps({'architecture':cfg['architecture'],'input_features':list(FEATURE_COLUMNS),'training_rows':len(Xtr)},indent=2))
 report='# V5 Controlled PyTorch Retraining Experiment\n\nExperiment-only checkpoint; no production deployment.\n\n## Final test metrics\n```\n'+json.dumps(metrics,indent=2)+'\n```\n\n## Localhost\n```\n'+json.dumps(meta['localhost'],indent=2)+'\n```\n\nProduction integrity: '+str(before==meta['production_after'])+'\n';(O/'training_report.md').write_text(report)
if __name__=='__main__':main()
