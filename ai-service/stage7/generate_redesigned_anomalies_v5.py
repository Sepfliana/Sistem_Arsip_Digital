"""V5 raw-domain generator.  No model training or production writes."""
from __future__ import annotations
import hashlib,json,random,sys
from pathlib import Path
import numpy as np,pandas as pd
B=Path(__file__).resolve().parents[1];S=B/'stage7';sys.path.insert(0,str(B))
from utils.preprocessing_contract import process_record
SEED=42;LIMIT=.001
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def setwib(r):
 t=pd.to_datetime(r['waktu']);t=t.tz_localize('UTC') if t.tzinfo is None else t.tz_convert('UTC');r['waktu']=t.replace(hour=19,minute=0,second=0).isoformat();return r
def main():
 random.seed(SEED);np.random.seed(SEED);raw=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');n=raw[(raw.candidate_type=='NORMAL')&(raw.source_type=='SYNTHETIC')].sample(frac=1,random_state=SEED).to_dict('records');rows=[];rej=[];pos=0
 plans=[('suspicious_external_access','Mild',300),('offhours_sensitive_external_access','Moderate',400),('credential_takeover_compound','Severe',300)]
 for typ,sev,count in plans:
  for _ in range(count):
   b=n[pos];pos+=1;r=dict(b);before={k:r[k] for k in ['aksi','status','device','ip_address','durasi_ms','jumlah_objek','waktu']}
   if typ=='suspicious_external_access':r.update(ip_address='8.8.8.8',device='Virtual Machine');fs=['ip_address','device'];why='suspicious external access from an unseen external/VM combination'
   elif typ=='offhours_sensitive_external_access':setwib(r);r.update(aksi='Kelola User',ip_address='8.8.8.8');fs=['waktu','aksi','ip_address'];why='off-hours sensitive access via external network'
   else:setwib(r);r.update(aksi='Keamanan & 2FA',ip_address='8.8.8.8',device='Virtual Machine');fs=['waktu','aksi','ip_address','device'];why='credential takeover compound pattern'
   c=process_record(r);pk=(str(pd.cut(pd.Series([c['hour']]),[-1,5,11,17,23],labels=['00-05','06-11','12-17','18-23']).iat[0]),c['activity'],c['device'],c['ip_address'])
   rows.append({**r,'candidate_type':'ANOMALY_V5','anomaly_type':typ,'severity':sev,'base_record_id':str(b['source_id']),'mutated_features':','.join(fs),'raw_before':json.dumps(before,default=str),'raw_after':json.dumps({k:r[k] for k in before},default=str),'primary_joint_combination':json.dumps(pk),'primary_joint_frequency':0.0,'primary_rarity_score':None,'threat_rationale':why,'preprocessing_status':'PASS_RAW_TO_PROCESS_RECORD'})
 # V5 forensic/V4 direct-disk evidence: this rule is joint-rare but >54% overlaps Normal MAX.
 rej.extend({'anomaly_type':'scripted_rapid_failure_v5','reason':'joint_rare_but_model_indistinguishable','requested':300,'rarity_rule':'status_device_duration_bucket<=0.1%'} for _ in range(300))
 out=pd.DataFrame(rows)
 if out.base_record_id.duplicated().any():raise ValueError('duplicate source')
 S.mkdir(exist_ok=True);out.to_csv(S/'stage7_redesign_v5_raw.csv',index=False);pd.DataFrame(rej).to_csv(S/'stage7_v5_generation_rejections.csv',index=False)
 m={'seed':SEED,'requested_count':1300,'generated_count':len(out),'rejected_count':len(rej),'taxonomy_removed':['mass_archive_access'],'per_type':out.anomaly_type.value_counts().to_dict(),'rejection_reason':'joint_rare_but_model_indistinguishable','raw_domain_only':True,'hash':sha(S/'stage7_redesign_v5_raw.csv')};(S/'stage7_v5_generation_metadata.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
if __name__=='__main__':main()
