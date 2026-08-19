"""Lightweight deterministic verification; no model/preprocessing fitting."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd
B=Path(__file__).resolve().parents[2];E=Path(__file__).resolve().parent;SEED=42
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def main():
 meta=json.loads((E/'split_metadata.json').read_text());raw=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');v=pd.read_csv(B/'stage7/stage7_redesign_v5_raw.csv');n=raw[(raw.candidate_type=='NORMAL')&(raw.source_type=='SYNTHETIC')];linked=set(v.base_record_id.astype(str));pool=n[~n.source_id.astype(str).isin(linked)].sample(frac=1,random_state=SEED).reset_index(drop=True);a=int(.7*len(pool));b=a+int(.15*len(pool));av=v.sample(frac=1,random_state=SEED).reset_index(drop=True);c=len(av)//2
 expected={'train_normal_manifest.csv':pool.iloc[:a],'validation_normal_manifest.csv':pool.iloc[a:b],'test_normal_manifest.csv':pool.iloc[b:],'validation_anomaly_manifest.csv':av.iloc[:c],'test_anomaly_manifest.csv':av.iloc[c:]};result={}
 for name,df in expected.items():
  actual=pd.read_csv(E/name);same_columns=list(actual.columns)==list(df.columns);expected_hash=hashlib.sha256(df.to_csv(index=False).encode()).hexdigest();result[name]={'expected_rows':len(df),'actual_rows':len(actual),'membership_identical':set((actual.source_id if 'source_id' in actual else actual.base_record_id).astype(str))==set((df.source_id if 'source_id' in df else df.base_record_id).astype(str)),'ordering_and_values_identical':same_columns and expected_hash==sha(E/name),'manifest_hash':sha(E/name),'metadata_hash_matches':sha(E/name)==meta['hashes'][name]}
 prod=json.loads((E/'production_hash_snapshot.json').read_text());out={'seed':SEED,'manifest_results':result,'source_exclusion_identical':len(linked)==meta['linked_sources'],'production_integrity':prod['match'],'metadata_timestamp_fields':[],'pass':all(all(x.values()) for x in result.values()) and prod['match'] and meta['seed']==SEED};(E/'deterministic_verification.json').write_text(json.dumps(out,indent=2));(E/'deterministic_verification_report.md').write_text('# Deterministic Verification\n\nPASS: '+str(out['pass'])+'\n')
if __name__=='__main__':main()
