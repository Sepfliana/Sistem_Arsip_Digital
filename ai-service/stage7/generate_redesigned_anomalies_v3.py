"""Stage 7.5 V3: mutate raw records, then emit candidate-contract evidence.

Never loads/trains a model and never writes outside stage7/.
"""
from __future__ import annotations
import hashlib,json,random
from pathlib import Path
import numpy as np,pandas as pd
import sys
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B))
from utils.preprocessing_contract import process_record,map_ip_category
S=B/'stage7';SEED=42
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for z in iter(lambda:f.read(1048576),b''):h.update(z)
 return h.hexdigest()
def quant(s):return {k:float(s.quantile(v)) for k,v in [('p05',.05),('p50',.5),('p95',.95),('p99',.99)]}
def set_wib_hour(row,h):
 t=pd.to_datetime(row['waktu']); t=t.tz_localize('UTC') if t.tzinfo is None else t.tz_convert('UTC'); row['waktu']=t.replace(hour=(h-7)%24,minute=0,second=0).isoformat()
 return row
def main():
 random.seed(SEED);np.random.seed(SEED)
 raw=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig')
 normal=raw[(raw.candidate_type=='NORMAL')&(raw.source_type=='SYNTHETIC')].copy(); total=1500
 if len(normal)<total:raise ValueError('insufficient synthetic raw normal sources')
 # Source split is deterministic and source IDs appear once.  V3 samples only raw normals.
 base=normal.sample(total,random_state=SEED,replace=False).reset_index(drop=True)
 gdur=quant(normal.durasi_ms.astype(float));gobj=quant(normal.jumlah_objek.astype(float)); rows=[];pos=0
 plan=[('external_access','Mild',200),('offhours_privileged_access','Moderate',250),('offhours_external_privileged','Moderate',250),('scripted_rapid_failure','Moderate',250),('mass_archive_access','Severe',275),('credential_takeover_compound','Severe',275)]
 for typ,sev,count in plan:
  for _ in range(count):
   r=base.iloc[pos].to_dict();pos+=1; original={k:r[k] for k in ['aksi','status','device','ip_address','durasi_ms','jumlah_objek','waktu']}; fs=[]
   if typ=='external_access':r['ip_address']='8.8.8.8';fs=['ip_address']
   elif typ=='offhours_privileged_access':set_wib_hour(r,random.randint(0,5));r['aksi']='Kelola User';fs=['waktu','aksi']
   elif typ=='offhours_external_privileged':set_wib_hour(r,random.randint(0,5));r['aksi']='Keamanan & 2FA';r['ip_address']='8.8.8.8';fs=['waktu','aksi','ip_address']
   elif typ=='scripted_rapid_failure':
    r['status']='Gagal';r['device']='Virtual Machine';r['durasi_ms']=max(1.0,float(normal.durasi_ms.quantile(.05)));fs=['status','device','durasi_ms']
   elif typ=='mass_archive_access':
    r['aksi']='Akses Berkas';pool=normal[normal.aksi.astype(str).str.contains('BERKAS|Berkas',na=False)]
    ref=pool if len(pool)>20 else normal;r['jumlah_objek']=float(ref.jumlah_objek.quantile(.95));r['durasi_ms']=float(ref.durasi_ms.quantile(.95));fs=['aksi','jumlah_objek','durasi_ms']
   else:
    set_wib_hour(r,random.randint(0,5));r['aksi']='Keamanan & 2FA';r['ip_address']='8.8.8.8';r['device']='Virtual Machine';fs=['waktu','aksi','ip_address','device']
   canon=process_record(r)
   if canon['ip_address'] not in ('Public IP Address','Private Network 192.168.x.x','Localhost / Loopback'):raise ValueError('invalid IP category')
   r.update(candidate_type='ANOMALY_V3',anomaly_type=typ,severity=sev,source_record_id=str(r['source_id']),mutated_features=','.join(fs),original_values=json.dumps(original,default=str),canonical_values=json.dumps(canon),raw_numeric_domain='raw_before_log1p')
   rows.append(r)
 out=pd.DataFrame(rows)
 if out.source_record_id.duplicated().any() or out.isna().any().any() or out.anomaly_type.str.contains('login_luar_jam').any():raise ValueError('integrity check failed')
 S.mkdir(exist_ok=True);out.to_csv(S/'stage7_redesigned_anomalies_v3_raw.csv',index=False,encoding='utf-8')
 pd.DataFrame([{'feature':'durasi_ms',**gdur},{'feature':'jumlah_objek',**gobj}]).to_csv(S/'stage7_v3_raw_domain_statistics.csv',index=False)
 meta={'seed':SEED,'total':len(out),'sha256':sha(S/'stage7_redesigned_anomalies_v3_raw.csv'),'source':'retraining_dataset_combined_raw.csv','raw_mutations_only':True,'counts':out.anomaly_type.value_counts().to_dict(),'severity':out.severity.value_counts().to_dict()}
 (S/'stage7_redesign_v3_reproducibility.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');print(json.dumps(meta,indent=2))
if __name__=='__main__':main()
