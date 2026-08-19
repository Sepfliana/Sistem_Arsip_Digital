"""Safe deterministic Stage 7.5 generator; does not load models or production files."""
from __future__ import annotations
import hashlib,json,pickle,random
from pathlib import Path
import numpy as np
import pandas as pd
B=Path(__file__).resolve().parents[1];O=B/'stage7/stage7_redesigned_anomalies.csv';M=B/'stage7/stage7_redesign_metadata.json';SEED=42
P=(('external_ip_single_probe','Mild',150,('ip_address',)),('unusual_device_single','Mild',150,('device',)),('offhours_sensitive_access','Moderate',250,('hour','activity')),('offhours_external_login','Moderate',250,('hour','ip_address')),('scripted_rapid_failure','Moderate',250,('status','duration_ms','device')),('mass_exfiltration_scraping','Severe',225,('object_count','duration_ms','activity')),('credential_takeover_compound','Severe',225,('hour','ip_address','device','activity')))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 random.seed(SEED);np.random.seed(SEED);d=pd.read_csv(B/'dataset/retraining/retraining_dataset_canonical.csv')
 with (B/'dataset/retraining/candidate_encoders.pkl').open('rb') as f:e=pickle.load(f)
 c={k:set(map(str,e[k].classes_)) for k in ('activity','status','device','ip_address')};v={'ip':'Public IP Address','dev':'Virtual Machine','status':'Gagal','sensitive':'Kelola User','access':'Akses Berkas','takeover':'Keamanan & 2FA'}
 for col,key in (('ip_address','ip'),('device','dev'),('status','status'),('activity','sensitive'),('activity','access'),('activity','takeover')):
  if v[key] not in c[col]:raise ValueError(f'encoder lacks {col}={v[key]!r}')
 n=d[d.candidate_type.eq('NORMAL')];s=n.sample(sum(x[2] for x in P),random_state=SEED,replace=False).reset_index(drop=True);rows=[];i=0
 for typ,sev,count,fs in P:
  for _ in range(count):
   z=s.iloc[i].to_dict();i+=1;r=z.copy();r.update(candidate_type='ANOMALY',anomaly_type=typ,severity=sev,mutated_features=','.join(fs),num_mutated_features=len(fs),source_record_id=str(z['source_id']))
   if typ=='external_ip_single_probe':r['ip_address']=v['ip']
   elif typ=='unusual_device_single':r['device']=v['dev']
   elif typ=='offhours_sensitive_access':r.update(hour=random.randint(0,5),activity=v['sensitive'])
   elif typ=='offhours_external_login':r.update(hour=random.randint(0,5),ip_address=v['ip'])
   elif typ=='scripted_rapid_failure':r.update(status=v['status'],duration_ms=float(random.randint(1,20)),device=v['dev'])
   elif typ=='mass_exfiltration_scraping':r.update(object_count=float(random.randint(50,200)),duration_ms=float(random.randint(1,50)),activity=v['access'])
   else:r.update(hour=random.randint(0,5),ip_address=v['ip'],device=v['dev'],activity=v['takeover'])
   rows.append(r)
 r=pd.DataFrame(rows)
 if r.isna().any().any() or r.duplicated().any() or r.source_record_id.duplicated().any() or r.anomaly_type.eq('login_luar_jam').any():raise ValueError('integrity failed')
 r.to_csv(O,index=False);m={'generator':'stage7/generate_redesigned_anomalies_v2.py','random_seed':SEED,'total_anomalies':len(r),'sha256':sha(O),'severity_distribution':r.severity.value_counts().sort_index().to_dict(),'anomaly_type_counts':r.anomaly_type.value_counts().sort_index().to_dict(),'encoder_categories_verified':True,'source_records_unique':True};M.write_text(json.dumps(m,indent=2),encoding='utf-8');print(json.dumps(m,indent=2))
if __name__=='__main__':main()
