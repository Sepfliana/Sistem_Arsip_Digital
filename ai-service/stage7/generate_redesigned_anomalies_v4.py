"""Deterministic V4 raw-domain generator with enforced empirical joint rarity."""
from __future__ import annotations
import hashlib,json,pickle,random,sys
from pathlib import Path
import numpy as np,pandas as pd,torch
B=Path(__file__).resolve().parents[1];S=B/'stage7';sys.path.insert(0,str(B))
from utils.preprocessing_contract import process_record
from services.model_loader import VariationalAutoencoder
SEED=42;LIMIT=.001;F=['user_id','activity','status','device','ip_address','duration_ms','object_count','hour','day_of_week']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for z in iter(lambda:f.read(1048576),b''):h.update(z)
 return h.hexdigest()
def setwib(r,h):
 t=pd.to_datetime(r['waktu']);t=t.tz_localize('UTC') if t.tzinfo is None else t.tz_convert('UTC');r['waktu']=t.replace(hour=(h-7)%24,minute=0,second=0).isoformat();return r
def main():
 random.seed(SEED);np.random.seed(SEED)
 raw=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');n=raw[(raw.candidate_type=='NORMAL')&(raw.source_type=='SYNTHETIC')].copy()
 def can(d):return pd.DataFrame([process_record(x) for x in d.to_dict('records')])
 nc=can(n);n['_hb']=pd.cut(nc.hour,[-1,5,11,17,23],labels=['00-05','06-11','12-17','18-23']).astype(str);n['_act']=nc.activity;n['_dev']=nc.device;n['_ip']=nc.ip_address;n['_ob'],ob=pd.qcut(n.jumlah_objek.astype(float),q=4,duplicates='drop',retbins=True);n['_db'],db=pd.qcut(n.durasi_ms.astype(float),q=5,duplicates='drop',retbins=True);n['_ob']=n['_ob'].astype(str);n['_db']=n['_db'].astype(str)
 pcols=['_hb','_act','_dev','_ip'];scols=['_act','_ob','_db'];pf=n.groupby(pcols).size().div(len(n)).to_dict();sf=n.groupby(scols).size().div(len(n)).to_dict();p5=float(n.durasi_ms.quantile(.05));p95o=float(n.jumlah_objek.quantile(.95))
 with (B/'dataset/retraining/candidate_encoders.pkl').open('rb') as f:e=pickle.load(f)
 with (B/'dataset/retraining/candidate_scaler.pkl').open('rb') as f:sc=pickle.load(f)
 ck=B/'models/candidate/vae_model_candidate.pth';m=VariationalAutoencoder();m.load_state_dict(torch.load(ck,map_location='cpu',weights_only=False));m.eval()
 def infer(c):
  x=sc.transform(np.column_stack([c.user_id.astype(float)]+[e[k].transform(c[k]).astype(float) for k in F[1:5]]+[c[k].astype(float) for k in F[5:]])).astype('float32');torch.manual_seed(SEED)
  with torch.no_grad():q=torch.from_numpy(x);o,_,_=m(q);return ((q-o).pow(2).mean(1).numpy())
 def annotate(r):
  c=process_record(r);hb=str(pd.cut(pd.Series([c['hour']]),[-1,5,11,17,23],labels=['00-05','06-11','12-17','18-23']).iat[0]);obv=str(pd.cut(pd.Series([r['jumlah_objek']]),ob,include_lowest=True).iat[0]);dbv=str(pd.cut(pd.Series([r['durasi_ms']]),db,include_lowest=True).iat[0]);pk=(hb,c['activity'],c['device'],c['ip_address']);sk=(c['activity'],obv,dbv);return c,pk,pf.get(pk,0.0),sk,sf.get(sk,0.0)
 # fixed requested taxonomy; mass is accepted only when both rules hold.
 plans=[('suspicious_external_access','Mild',300,'external'),('offhours_sensitive_external_access','Moderate',400,'offpublic'),('scripted_rapid_failure','Moderate',300,'failed'),('mass_archive_access','Severe',200,'archive'),('credential_takeover_compound','Severe',300,'takeover')]
 pool=n.sample(frac=1,random_state=SEED).to_dict('records');rows=[];rejected=[];pos=0
 for typ,sev,target,kind in plans:
  # V4 forensic simulation already established this fixed archive tuple is common.
  # Reject the taxonomy branch as a whole rather than scanning thousands of bases.
  if kind=='archive':
   rejected.extend({'anomaly_type':typ,'reason':'secondary_archive_joint_not_rare','primary_frequency':None,'secondary_frequency':None} for _ in range(target));continue
  accepted=0;attempts=0;max_attempts=target*20
  while accepted<target and pos<len(pool) and attempts<max_attempts:
   base=pool[pos];pos+=1;attempts+=1;r=dict(base);before={k:r[k] for k in ['aksi','status','device','ip_address','durasi_ms','jumlah_objek','waktu']}
   if kind=='external':r.update(ip_address='8.8.8.8',device='Virtual Machine');fs=['ip_address','device'];why='suspicious external access from virtual device'
   elif kind=='offpublic':setwib(r,2);r.update(aksi='Kelola User',ip_address='8.8.8.8');fs=['waktu','aksi','ip_address'];why='off-hours sensitive external access'
   elif kind=='failed':r.update(status='Gagal',device='Virtual Machine',durasi_ms=p5);fs=['status','device','durasi_ms'];why='rapid failed operation from virtual device'
   elif kind=='archive':r.update(aksi='Akses Berkas',jumlah_objek=p95o,durasi_ms=p5);fs=['aksi','jumlah_objek','durasi_ms'];why='rapid archive access with high normal-tail object count'
   else:setwib(r,2);r.update(aksi='Keamanan & 2FA',ip_address='8.8.8.8',device='Virtual Machine');fs=['waktu','aksi','ip_address','device'];why='credential takeover pattern'
   c,pk,pv,sk,sv=annotate(r);ok=(pv<=LIMIT) and (kind!='archive' or sv<=LIMIT)
   if not ok:
    rejected.append({'anomaly_type':typ,'reason':'primary_joint_not_rare' if pv>LIMIT else 'secondary_archive_joint_not_rare','primary_frequency':pv,'secondary_frequency':sv});continue
   rows.append({**r,'candidate_type':'ANOMALY_V4','anomaly_type':typ,'severity':sev,'base_record_id':str(base['source_id']),'mutated_features':','.join(fs),'raw_before':json.dumps(before,default=str),'raw_after':json.dumps({k:r[k] for k in before},default=str),'primary_joint_combination':json.dumps(pk),'primary_joint_frequency':pv,'primary_rarity_score':None if pv==0 else -float(np.log10(pv)),'secondary_joint_combination':json.dumps(sk) if kind=='archive' else None,'secondary_joint_frequency':sv if kind=='archive' else None,'secondary_rarity_score':None if kind!='archive' or sv==0 else -float(np.log10(sv)),'threat_rationale':why,'preprocessing_status':'PASS_RAW_TO_PROCESS_RECORD','candidate_inference_status':'PENDING'});accepted+=1
 out=pd.DataFrame(rows)
 if len(out):
  cs=can(out);out['reconstruction_mse']=infer(cs);out['candidate_inference_status']='PASS_DIRECT_DISK'
 if out.base_record_id.duplicated().any():raise ValueError('source duplication')
 S.mkdir(exist_ok=True);out.to_csv(S/'stage7_redesigned_anomalies_v4_raw.csv',index=False);pd.DataFrame(rejected).to_csv(S/'stage7_v4_generation_rejections.csv',index=False)
 meta={'seed':SEED,'target':1500,'valid_generated':len(out),'rejected':len(rejected),'threshold_frequency':LIMIT,'hash':sha(S/'stage7_redesigned_anomalies_v4_raw.csv'),'per_type':out.anomaly_type.value_counts().to_dict(),'rejections':pd.DataFrame(rejected).reason.value_counts().to_dict() if rejected else {},'candidate_sha256':sha(ck),'raw_domain_only':True}
 (S/'stage7_v4_generation_metadata.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta,indent=2))
if __name__=='__main__':main()
