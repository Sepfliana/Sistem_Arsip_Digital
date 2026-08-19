"""Build deterministic, source-disjoint V5 experiment manifests only; no training."""
from __future__ import annotations
import hashlib,json,pickle,random,sys
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.preprocessing import LabelEncoder,StandardScaler
B=Path(__file__).resolve().parents[2];E=Path(__file__).resolve().parent;sys.path.insert(0,str(B))
from utils.preprocessing_contract import ACTIVITY_CLASSES,STATUS_CLASSES,DEVICE_CLASSES,IP_CLASSES,FEATURE_COLUMNS,process_record
SEED=42
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def write(df,name):
 p=E/name;df.to_csv(p,index=False);return sha(p)
def main():
 random.seed(SEED);np.random.seed(SEED);prod=[B/'models/vae_model.pth',B/'models/deployment_config.json',B/'dataset/preprocessed/scaler.pkl',B/'dataset/preprocessed/label_encoders.pkl',B/'dataset/preprocessed/X_train.npy'];before={str(p.relative_to(B)):sha(p) for p in prod}
 v=pd.read_csv(B/'stage7/stage7_redesign_v5_raw.csv');raw=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');normal=raw[(raw.candidate_type=='NORMAL')&(raw.source_type=='SYNTHETIC')].copy();linked=set(v.base_record_id.astype(str));sources=set(normal.source_id.astype(str));missing=linked-sources
 if missing:raise ValueError(f'lineage missing for {len(missing)} V5 base ids')
 lineage=v.reset_index(names='anomaly_row_id')[['anomaly_row_id','base_record_id','anomaly_type','mutated_features']].copy();lineage['source_dataset']='retraining_dataset_combined_raw.csv';lineage['source_split']='V5_ANOMALY_PENDING';lineage['mutation_description']=lineage.pop('mutated_features');lh=write(lineage,'source_lineage.csv')
 excluded=normal[normal.source_id.astype(str).isin(linked)].copy();eh=write(excluded[['source_id']].assign(reason='V5 anomaly base source; excluded from all normal partitions'),'excluded_normal_sources.csv');pool=normal[~normal.source_id.astype(str).isin(linked)].sample(frac=1,random_state=SEED).reset_index(drop=True)
 a=int(.7*len(pool));b=a+int(.15*len(pool));tr,va,te=pool.iloc[:a],pool.iloc[a:b],pool.iloc[b:];av=v.sample(frac=1,random_state=SEED).reset_index(drop=True);cut=len(av)//2;ava,ate=av.iloc[:cut],av.iloc[cut:]
 hashes={'train_normal_manifest.csv':write(tr,'train_normal_manifest.csv'),'validation_normal_manifest.csv':write(va,'validation_normal_manifest.csv'),'test_normal_manifest.csv':write(te,'test_normal_manifest.csv'),'validation_anomaly_manifest.csv':write(ava,'validation_anomaly_manifest.csv'),'test_anomaly_manifest.csv':write(ate,'test_anomaly_manifest.csv'),'source_lineage.csv':lh,'excluded_normal_sources.csv':eh}
 # Fixed contract vocabularies, not validation/test-fitted; scaler is fit solely on train normal.
 enc={'activity':LabelEncoder().fit(ACTIVITY_CLASSES),'status':LabelEncoder().fit(STATUS_CLASSES),'device':LabelEncoder().fit(DEVICE_CLASSES),'ip_address':LabelEncoder().fit(IP_CLASSES)}
 def matrix(d):
  c=pd.DataFrame([process_record(x) for x in d.to_dict('records')]);x=np.column_stack([c.user_id.astype(float)]+[enc[k].transform(c[k]).astype(float) for k in ['activity','status','device','ip_address']]+[c[k].astype(float) for k in ['duration_ms','object_count','hour','day_of_week']]);return c,x
 _,xt=matrix(tr);sc=StandardScaler().fit(xt)
 for name,d in [('train',tr),('validation_normal',va),('test_normal',te),('validation_anomaly',ava),('test_anomaly',ate)]:
  c,x=matrix(d);z=sc.transform(x);assert x.shape[1]==9 and list(c.columns)==list(FEATURE_COLUMNS) and not np.isnan(z).any() and not np.isinf(z).any(),name
 with (E/'label_encoders_v5_experiment.pkl').open('wb') as f:pickle.dump(enc,f)
 with (E/'scaler_v5_experiment.pkl').open('wb') as f:pickle.dump(sc,f)
 hashes['label_encoders_v5_experiment.pkl']=sha(E/'label_encoders_v5_experiment.pkl');hashes['scaler_v5_experiment.pkl']=sha(E/'scaler_v5_experiment.pkl')
 groups=[set(x.source_id.astype(str)) for x in (tr,va,te)];agroups=[set(x.base_record_id.astype(str)) for x in (ava,ate)];assert not any(g&h for g in groups for h in agroups);assert not(groups[0]&groups[1] or groups[0]&groups[2] or groups[1]&groups[2]);assert not(agroups[0]&agroups[1]);assert not v.base_record_id.duplicated().any()
 after={str(p.relative_to(B)):sha(p) for p in prod};meta={'seed':SEED,'normal_total':len(normal),'linked_sources':len(linked),'excluded_sources':len(excluded),'train_normal':len(tr),'validation_normal':len(va),'test_normal':len(te),'validation_anomaly':len(ava),'test_anomaly':len(ate),'feature_order':list(FEATURE_COLUMNS),'encoder_policy':'fixed preprocessing-contract vocabularies; no validation/test fitting','scaler_fit_source':'TRAIN_NORMAL only','hashes':hashes,'assertions':'PASS','production_hash_match':before==after};(E/'split_metadata.json').write_text(json.dumps(meta,indent=2));(E/'split_reproducibility.json').write_text(json.dumps({'seed':SEED,'manifest_hashes':hashes,'deterministic_rerun_required':True},indent=2));(E/'production_hash_snapshot.json').write_text(json.dumps({'before':before,'after':after,'match':before==after},indent=2))
 rep='# V5 Source-Aware Experimental Split\n\n**SOURCE-AWARE SPLIT READY.** All 1,000 V5 base sources are excluded from every normal partition, not deleted from production. Train has normal records only; validation/test anomalies are source-disjoint. Fixed contract encoders avoid anomaly-class fitting; scaler is fit on train-normal only.\n\nRETRAINING: NOT PERFORMED\nDEPLOYMENT: NOT PERFORMED\nPRODUCTION MODIFIED: NO\nTHRESHOLD MODIFIED: NO\nSERVICE RESTARTED: NO\nSTAGE 8: NOT STARTED\n';(E/'source_aware_split_report.md').write_text(rep)
if __name__=='__main__':main()
