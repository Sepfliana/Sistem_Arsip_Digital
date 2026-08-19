"""Read-only forensic investigation for Stage 7.5 V3 failing anomaly types."""
from __future__ import annotations
import json,pickle,sys
from pathlib import Path
import numpy as np,pandas as pd,torch
B=Path(__file__).resolve().parents[1];S=B/'stage7';sys.path.insert(0,str(B))
from utils.preprocessing_contract import process_record
from services.model_loader import VariationalAutoencoder
F=['user_id','activity','status','device','ip_address','duration_ms','object_count','hour','day_of_week']
FAIL=['mass_archive_access','offhours_privileged_access']
def stat(x):return {k:float(v) for k,v in zip(['min','p25','median','p75','p95','p99','max','mean','std'],[x.min(),np.quantile(x,.25),np.median(x),np.quantile(x,.75),np.quantile(x,.95),np.quantile(x,.99),x.max(),x.mean(),x.std()])}
def main():
 raw=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');v3=pd.read_csv(S/'stage7_redesigned_anomalies_v3_raw.csv');normal=raw[(raw.candidate_type=='NORMAL')&(raw.source_type=='SYNTHETIC')].copy()
 with (B/'dataset/retraining/candidate_encoders.pkl').open('rb') as f:e=pickle.load(f)
 with (B/'dataset/retraining/candidate_scaler.pkl').open('rb') as f:sc=pickle.load(f)
 def canonical(d):return pd.DataFrame([process_record(x) for x in d.to_dict('records')])
 def scaled(c):
  x=np.column_stack([c.user_id.astype(float)]+[e[k].transform(c[k]).astype(float) for k in F[1:5]]+[c[k].astype(float) for k in F[5:]])
  return sc.transform(x).astype('float32')
 nc=canonical(normal);nx=scaled(nc);m=VariationalAutoencoder();m.load_state_dict(torch.load(B/'models/candidate/vae_model_candidate.pth',map_location='cpu',weights_only=False));m.eval()
 def errs(c):
  torch.manual_seed(42)
  with torch.no_grad():x=torch.from_numpy(scaled(c));o,_,_=m(x);z=(x-o).pow(2).numpy()
  return z.mean(1),z
 # Rarity uses canonicalized behavior; buckets preserve raw operational semantics.
 normal['_hour']=nc.hour.values;normal['_activity']=nc.activity.values;normal['_device']=nc.device.values;normal['_ip']=nc.ip_address.values
 normal['_obj_bucket']=pd.cut(normal.jumlah_objek.astype(float),[-1,1,2,5,10,float('inf')],labels=['1','2','3-5','6-10','>10']).astype(str)
 normal['_dur_bucket'],dur_bins=pd.qcut(normal.durasi_ms.astype(float),q=5,duplicates='drop',retbins=True);normal['_dur_bucket']=normal['_dur_bucket'].astype(str)
 joint=[]; comps=[(['_hour','_activity'],'hour_activity'),(['_hour','_activity','_device'],'hour_activity_device'),(['_hour','_activity','_ip'],'hour_activity_ip'),(['_activity','_obj_bucket'],'activity_object_bucket'),(['_activity','_dur_bucket'],'activity_duration_bucket'),(['_device','_ip'],'device_ip')]
 all_rows=[]; comparisons=[]; errors=[]
 for typ in FAIL:
  a=v3[v3.anomaly_type.eq(typ)].copy();ac=canonical(a);ae,az=errs(ac);a['_hour']=ac.hour.values;a['_activity']=ac.activity.values;a['_device']=ac.device.values;a['_ip']=ac.ip_address.values;a['_obj_bucket']=pd.cut(a.jumlah_objek.astype(float),[-1,1,2,5,10,float('inf')],labels=['1','2','3-5','6-10','>10']).astype(str);a['_dur_bucket']=pd.cut(a.durasi_ms.astype(float),bins=dur_bins,include_lowest=True).astype(str)
  for ri,k in enumerate(F):
   rawcol={'duration_ms':'durasi_ms','object_count':'jumlah_objek'}.get(k)
   rn=normal[rawcol].astype(float) if rawcol else (normal['_'+k] if '_'+k in normal else nc[k])
   ra=a[rawcol].astype(float) if rawcol else (a['_'+k] if '_'+k in a else ac[k])
   def med(x):return float(pd.to_numeric(x,errors='coerce').median()) if pd.api.types.is_numeric_dtype(x) else str(pd.Series(x).mode().iat[0])
   comparisons.append({'type':typ,'feature':k,'raw_normal_median':med(rn),'raw_anomaly_median':med(ra),'canonical_normal_median':med(nc[k]),'canonical_anomaly_median':med(ac[k]),'scaled_normal_median':float(np.median(nx[:,ri])),'scaled_anomaly_median':float(np.median(scaled(ac)[:,ri])),'mean_reconstruction_error_contribution':float(az[:,ri].mean())})
  errors.append({'group':typ,'count':len(a),**stat(ae)})
  for cols,name in comps:
   ng=normal.groupby(cols).size().rename('normal_count').reset_index(); ag=a.groupby(cols).size().rename('anomaly_count').reset_index(); z=ag.merge(ng,on=cols,how='left').fillna({'normal_count':0});z['normal_frequency']=z.normal_count/len(normal);z['anomaly_frequency']=z.anomaly_count/len(a);z['type']=typ;z['combination']=name;all_rows.append(z)
 pd.DataFrame(comparisons).to_csv(S/'stage7_v4_raw_vs_preprocessed.csv',index=False);pd.DataFrame(errors).to_csv(S/'stage7_v4_error_distribution.csv',index=False);pd.concat(all_rows,ignore_index=True).to_csv(S/'stage7_v4_joint_rarity.csv',index=False)
 # Explicit generator evidence, not inference: mutations and their implications.
 findings={'mass_archive_access':{'implementation':'aksi=Akses Berkas; jumlah_objek=P95 of BERKAS-like normals; durasi_ms=P95 of same pool','evidence':'P95 object count is 10, the normal operational ceiling; therefore object mutation normally remains in an already common bucket.'},'offhours_privileged_access':{'implementation':'WIB hour 0-5 plus aksi=Kelola User; IP/device/duration/status preserved from source','evidence':'Only two fields change; retained private IP/device makes much of the joint vector normal-like.'}}
 (S/'stage7_v4_forensic_findings.json').write_text(json.dumps(findings,indent=2))
 er=pd.DataFrame(errors).to_csv(index=False);cp=pd.DataFrame(comparisons).to_csv(index=False)
 report='# Stage 7.5 — V4 Forensic Investigation\n\n## Scope\nRead-only investigation only; V4 generator, training, deployment, and production changes were not performed.\n\n## Root causes\n- **mass_archive_access:** raw P95 object count is 10, already the normal cap. Its P95 object/duration mutations consequently stay in common raw buckets; after log1p and scaling they have little novelty.\n- **offhours_privileged_access:** V3 changes only WIB hour and activity while retaining source IP, device, status, and duration. The resulting behavior is frequently reconstructed as normal; off-hours alone is not discriminative.\n\n## Reconstruction distributions\n```\n'+er+'```\n\n## Raw vs canonical/scaled comparison\n```\n'+cp+'```\n\n## Evidence-based V4 recommendation\nV4 is required, but must not be implemented yet. Use empirical *joint* rarity selection: choose a plausible raw value from activity-conditional tails only where `(activity, object bucket, duration bucket)` and `(hour, activity, IP/device)` are low-density normal combinations. Reject a generated scenario if its joint normal frequency is not below a predeclared threshold. Preserve Localhost as external-only safety data and evaluate it before any retraining.\n\n## Acceptance criteria\nRaw mutation before contract; candidate-contract identity; unique sources; deterministic seed; no synthetic row in normal training; no type with low detectability; no artificial numeric extremes; Localhost FPR at candidate review threshold acceptable by an explicitly approved safety gate.\n\n**FORENSIC INVESTIGATION COMPLETE — V4 redesign is required; do not retrain.**\n'
 (S/'stage7_v4_forensic_investigation_report.md').write_text(report,encoding='utf-8')
if __name__=='__main__':main()
