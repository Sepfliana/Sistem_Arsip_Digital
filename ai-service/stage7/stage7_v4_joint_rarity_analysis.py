"""Stage 7.5 V4 joint-rarity forensic analysis; no training or V4 dataset output."""
from __future__ import annotations
import hashlib,json,pickle,sys
from pathlib import Path
import numpy as np,pandas as pd,torch
from sklearn.metrics import precision_recall_curve,confusion_matrix,roc_auc_score,average_precision_score
B=Path(__file__).resolve().parents[1];S=B/'stage7';sys.path.insert(0,str(B))
from utils.preprocessing_contract import process_record
from services.model_loader import VariationalAutoencoder
F=['user_id','activity','status','device','ip_address','duration_ms','object_count','hour','day_of_week'];SEED=42;PROD=3.1496288776397705
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for z in iter(lambda:f.read(1048576),b''):h.update(z)
 return h.hexdigest()
def stats(x):return {k:float(v) for k,v in zip(['min','p25','median','p75','p95','p99','max','mean','std'],[x.min(),np.quantile(x,.25),np.median(x),np.quantile(x,.75),np.quantile(x,.95),np.quantile(x,.99),x.max(),x.mean(),x.std()])}
def sethour(r,h):
 t=pd.to_datetime(r['waktu']);t=t.tz_localize('UTC') if t.tzinfo is None else t.tz_convert('UTC');r['waktu']=t.replace(hour=(h-7)%24,minute=0,second=0).isoformat();return r
def main():
 prodf=[B/'models/vae_model.pth',B/'models/deployment_config.json',B/'dataset/preprocessed/scaler.pkl',B/'dataset/preprocessed/label_encoders.pkl',B/'dataset/preprocessed/X_train.npy'];before={str(p.relative_to(B)):sha(p) for p in prodf}
 raw=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');normal=raw[(raw.candidate_type=='NORMAL')&(raw.source_type=='SYNTHETIC')].copy();lhraw=raw[raw.source_type=='REAL_DB'].copy()
 def canon(d):return pd.DataFrame([process_record(x) for x in d.to_dict('records')])
 nc=canon(normal);normal['_hour']=nc.hour;normal['_activity']=nc.activity;normal['_device']=nc.device;normal['_ip']=nc.ip_address
 normal['_obj_bucket'],obins=pd.qcut(normal.jumlah_objek.astype(float),q=4,duplicates='drop',retbins=True);normal['_dur_bucket'],dbins=pd.qcut(normal.durasi_ms.astype(float),q=5,duplicates='drop',retbins=True);normal['_obj_bucket']=normal['_obj_bucket'].astype(str);normal['_dur_bucket']=normal['_dur_bucket'].astype(str);normal['_hour_bucket']=pd.cut(normal._hour,[-1,5,11,17,23],labels=['00-05','06-11','12-17','18-23']).astype(str)
 combos=[(['_activity','_obj_bucket','_dur_bucket'],'activity_object_duration'),(['_hour_bucket','_activity','_device'],'hour_activity_device'),(['_hour_bucket','_activity','_ip'],'hour_activity_ip'),(['_device','_ip'],'device_ip'),(['_hour_bucket','_activity','_device','_ip'],'hour_activity_device_ip')]
 tables={};out=[]
 for cols,name in combos:
  z=normal.groupby(cols).size().rename('count').reset_index();z['frequency']=z['count']/len(normal);z['rarity_score_neglog10']=-np.log10(z.frequency);z['combination']=name;out.append(z);tables[name]=(cols,z)
 pd.concat(out,ignore_index=True).to_csv(S/'stage7_v4_joint_frequency.csv',index=False)
 freq_summary=[]
 for name,(_,z) in tables.items():
  q=z.frequency.quantile([.05,.1,.25,.5,.75,.9,.95,.99]).to_dict();freq_summary.append({'combination':name,'unique_combinations':len(z),'min_frequency':float(z.frequency.min()),'median_frequency':float(z.frequency.median()),**{f'p{int(k*100)}_frequency':float(v) for k,v in q.items()}})
 # Candidate artifacts and deterministic inference
 with (B/'dataset/retraining/candidate_encoders.pkl').open('rb') as f:e=pickle.load(f)
 with (B/'dataset/retraining/candidate_scaler.pkl').open('rb') as f:sc=pickle.load(f)
 def xform(c):return sc.transform(np.column_stack([c.user_id.astype(float)]+[e[k].transform(c[k]).astype(float) for k in F[1:5]]+[c[k].astype(float) for k in F[5:]])).astype('float32')
 m=VariationalAutoencoder();ck=B/'models/candidate/vae_model_candidate.pth';m.load_state_dict(torch.load(ck,map_location='cpu',weights_only=False));m.eval()
 def mse(c):
  torch.manual_seed(SEED)
  with torch.no_grad():x=torch.from_numpy(xform(c));o,_,_=m(x);return (x-o).pow(2).mean(1).numpy()
 test=normal.sample(frac=.15,random_state=SEED);en=mse(canon(test));el=mse(canon(lhraw));base=normal.sample(n=200,random_state=SEED).reset_index(drop=True)
 p5d,p95d=np.quantile(normal.durasi_ms.astype(float),[.05,.95]);p95o=np.quantile(normal.jumlah_objek.astype(float),.95)
 scenarios=[('offhours_sensitive',lambda r:(sethour(r,2).update({'aksi':'Kelola User'}) or r)),('offhours_public',lambda r:(sethour(r,2).update({'ip_address':'8.8.8.8'}) or r)),('offhours_sensitive_public',lambda r:(sethour(r,2).update({'aksi':'Kelola User','ip_address':'8.8.8.8'}) or r)),('offhours_sensitive_vm',lambda r:(sethour(r,2).update({'aksi':'Kelola User','device':'Virtual Machine'}) or r)),('sensitive_fast_high_objects',lambda r:(r.update({'aksi':'Kelola User','durasi_ms':float(p5d),'jumlah_objek':float(p95o)}) or r)),('archive_high_objects_short',lambda r:(r.update({'aksi':'Akses Berkas','durasi_ms':float(p5d),'jumlah_objek':float(p95o)}) or r)),('public_vm',lambda r:(r.update({'ip_address':'8.8.8.8','device':'Virtual Machine'}) or r)),('public_vm_sensitive',lambda r:(r.update({'ip_address':'8.8.8.8','device':'Virtual Machine','aksi':'Kelola User'}) or r)),('public_offhours_vm_sensitive',lambda r:(sethour(r,2).update({'ip_address':'8.8.8.8','device':'Virtual Machine','aksi':'Kelola User'}) or r))]
 sim=[];all_scores=[]
 for name,mut in scenarios:
  d=pd.DataFrame([mut(dict(x)) for x in base.to_dict('records')]);c=canon(d);a=mse(c);all_scores.append(a);tmp=d.copy();tmp['_hour_bucket']=pd.cut(c.hour,[-1,5,11,17,23],labels=['00-05','06-11','12-17','18-23']).astype(str);tmp['_activity']=c.activity;tmp['_device']=c.device;tmp['_ip']=c.ip_address
  cols,z=tables['hour_activity_device_ip']; keys=tmp[cols].merge(z[cols+['frequency']],on=cols,how='left').frequency.fillna(0);sim.append({'scenario':name,'count':len(a),**stats(a),'detect_normal_p95':float((a>np.quantile(en,.95)).mean()),'detect_normal_max':float((a>en.max()).mean()),'overlap_normal_max':float((a<=en.max()).mean()),'joint_frequency_median':float(keys.median()),'joint_frequency_max':float(keys.max()),'unseen_joint_pct':float((keys==0).mean()*100),'raw_duration_used':float(p5d) if 'fast' in name or 'short' in name else None,'raw_object_count_used':float(p95o) if 'objects' in name else None})
 sdf=pd.DataFrame(sim);sdf.to_csv(S/'stage7_v4_scenario_simulation.csv',index=False)
 # Threshold diagnostics: normal test vs each virtual scenario pool; localhost remains external.
 pool=np.concatenate(all_scores);y=np.r_[np.zeros(len(en)),np.ones(len(pool))];q=np.r_[en,pool];pr,re,th=precision_recall_curve(y,q);f=2*pr*re/(pr+re+1e-12);i=int(f.argmax());candidates={'normal_p95':float(np.quantile(en,.95)),'normal_p99':float(np.quantile(en,.99)),'normal_max':float(en.max()),'best_offline_f1':float(th[min(i,len(th)-1)]),'production_unchanged':PROD};ta=[]
 for label,t in candidates.items():
  pred=q>=t;tn,fp,fn,tp=confusion_matrix(y,pred).ravel();ta.append({'threshold_name':label,'threshold':t,'precision':tp/(tp+fp) if tp+fp else 0,'recall':tp/(tp+fn),'f1':2*tp/(2*tp+fp+fn),'normal_fpr':fp/(fp+tn),'localhost_fpr':float((el>=t).mean()),'localhost_false_positive':int((el>=t).sum())})
 pd.DataFrame(ta).to_csv(S/'stage7_v4_threshold_analysis.csv',index=False)
 evidence={'seed':SEED,'candidate_sha256':sha(ck),'raw_normal_count':len(normal),'localhost_count':len(lhraw),'normal_mse':stats(en),'localhost_mse':stats(el),'joint_frequency_summary':freq_summary,'production_before':before,'production_after':{str(p.relative_to(B)):sha(p) for p in prodf},'production_integrity':before=={str(p.relative_to(B)):sha(p) for p in prodf}}
 (S/'stage7_v4_forensic_evidence.json').write_text(json.dumps(evidence,indent=2))
 decision='V4 DESIGN READY' if any((sdf.unseen_joint_pct>0)&(sdf.detect_normal_max>=.75)) else 'V4 DESIGN NEEDS FURTHER FORENSIC ANALYSIS'
 report='# Stage 7.5 — V4 Joint-Rarity Analysis\n\n## Method\nNormal-only empirical distribution; raw-domain in-memory scenarios; candidate preprocessing and checkpoint only.\n\n## Joint frequency summary\n```\n'+pd.DataFrame(freq_summary).to_csv(index=False)+'```\n\n## Scenario simulation\n```\n'+sdf.to_csv(index=False)+'```\n\n## Threshold and Localhost safety\n```\n'+pd.DataFrame(ta).to_csv(index=False)+'```\n\n## Decision\n**'+decision+'**. No V4 generator was created. Joint rarity is defined as `count(combo)/N_normal`; score is `-log10(frequency)`. Candidate cutoffs are reported empirically, not adopted as final policy.\n'
 (S/'stage7_v4_joint_rarity_report.md').write_text(report,encoding='utf-8')
 rec='# V4 Design Recommendation\n\nDo not use a single-feature tail. Select only raw-domain compound scenarios whose exact `(hour bucket, activity, device, IP category)` is unseen or empirically low-frequency in normal data, while the `(activity, object bucket, duration bucket)` remains operationally plausible. V4 requires a predeclared rarity threshold and a per-scenario Localhost FPR gate before implementation.\n\nDecision: **'+decision+'**.\n';(S/'stage7_v4_design_recommendation.md').write_text(rec,encoding='utf-8')
if __name__=='__main__':main()
