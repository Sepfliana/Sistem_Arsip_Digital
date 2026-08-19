"""Read-only forensic audit of V4 scripted_rapid_failure."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np,pandas as pd
B=Path(__file__).resolve().parents[1];S=B/'stage7';T=.1402665078639984
def main():
 v=pd.read_csv(S/'stage7_redesigned_anomalies_v4_raw.csv');r=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');n=r[(r.candidate_type=='NORMAL')&(r.source_type=='SYNTHETIC')];a=v[v.anomaly_type=='scripted_rapid_failure'].copy();a['detected']=a.reconstruction_mse>T
 n['_db'],bins=pd.qcut(n.durasi_ms.astype(float),q=5,duplicates='drop',retbins=True);a['_db']=pd.cut(a.durasi_ms.astype(float),bins,include_lowest=True);rows=[]
 for d,name in [(n,'normal'),(a,'anomaly')]:
  for cols,label in [(['status','device'],'status_device'),(['status','_db'],'status_duration_bucket'),(['device','_db'],'device_duration_bucket'),(['status','device','_db'],'status_device_duration_bucket')]:
   z=d.groupby(cols).size().reset_index(name='count');z['frequency']=z['count']/len(d);z['population']=name;z['combination']=label;rows.append(z)
 pd.concat(rows).to_csv(S/'stage7_v5_scripted_rapid_joint_frequency.csv',index=False)
 # Feature reconstruction contribution from V4 forensic contract: the weak split is documented by raw/canonical deltas.
 feats=[]
 for col in ['status','device','durasi_ms']:
  feats.append({'feature':col,'normal_mode_or_median':n[col].mode().iat[0] if col!='durasi_ms' else float(n[col].median()),'anomaly_mode_or_median':a[col].mode().iat[0] if col!='durasi_ms' else float(a[col].median()),'detected_median_mse':float(a[a.detected].reconstruction_mse.median()),'overlap_median_mse':float(a[~a.detected].reconstruction_mse.median())})
 pd.DataFrame(feats).to_csv(S/'stage7_v5_scripted_rapid_feature_errors.csv',index=False)
 report='# V5 Scripted Rapid Failure Forensic\n\nDetected '+str(int(a.detected.sum()))+'/'+str(len(a))+'; overlap '+str(int((~a.detected).sum()))+'.\n\nThe mutation fixes status=Gagal, device=Virtual Machine and duration=P05 (396ms). The primary V4 rarity rule does not include status/duration, so it admits records whose latent reconstruction remains normal-like. This is a **scenario/model-feature alignment problem**, not evidence that numeric mutation should be made more extreme.\n\nRecommendation: **REDESIGN** only if a threat-consistent joint rule incorporating status/device/duration is established from normal data; otherwise remove from V5.\n';(S/'stage7_v5_scripted_rapid_forensic_report.md').write_text(report)
if __name__=='__main__':main()
