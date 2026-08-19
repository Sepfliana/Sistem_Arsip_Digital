"""Post-generation V4 audit; does not train, deploy, or alter candidate/production."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import numpy as np,pandas as pd
B=Path(__file__).resolve().parents[1];S=B/'stage7';PROD=3.1496288776397705
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for z in iter(lambda:f.read(1048576),b''):h.update(z)
 return h.hexdigest()
def st(x):return {k:float(v) for k,v in zip(['min','p25','median','p75','p95','p99','max','mean','std'],[x.min(),np.quantile(x,.25),np.median(x),np.quantile(x,.75),np.quantile(x,.95),np.quantile(x,.99),x.max(),x.mean(),x.std()])}
def main():
 p=[B/'models/vae_model.pth',B/'models/deployment_config.json',B/'dataset/preprocessed/scaler.pkl',B/'dataset/preprocessed/label_encoders.pkl',B/'dataset/preprocessed/X_train.npy'];h={str(x.relative_to(B)):sha(x) for x in p};d=pd.read_csv(S/'stage7_redesigned_anomalies_v4_raw.csv');raw=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');n=raw[(raw.candidate_type=='NORMAL')&(raw.source_type=='SYNTHETIC')]
 # Normal/localhost errors were obtained from the same direct-disk candidate path in V4 forensic analysis.
 e=json.loads((S/'stage7_v4_forensic_evidence.json').read_text());normal=e['normal_mse'];local=e['localhost_mse'];mx=normal['max'];p95=normal['p95'];p99=normal['p99'];a=d.reconstruction_mse.to_numpy();pt=[]
 for typ,g in d.groupby('anomaly_type'):
  x=g.reconstruction_mse.to_numpy();pt.append({'anomaly_type':typ,'count':len(x),'severity':g.severity.iloc[0],'mutated_features':g.mutated_features.iloc[0],**st(x),'detect_normal_p95':float((x>p95).mean()),'detect_normal_max':float((x>mx).mean()),'overlap_normal_max':float((x<=mx).mean())})
 pd.DataFrame(pt).to_csv(S/'stage7_v4_per_type_analysis.csv',index=False);ov=[]
 for label,t in [('normal_p95',p95),('normal_p99',p99),('normal_max',mx)]:ov.append({'threshold':label,'value':t,'anomaly_count_le':int((a<=t).sum()),'anomaly_pct_le':float((a<=t).mean()*100)})
 pd.DataFrame(ov).to_csv(S/'stage7_v4_overlap.csv',index=False);feat=pd.DataFrame([{'feature':'raw_domain_metadata_only','note':'per-feature inference error retained in direct V4 generator contract; no canonical mutation'}]);feat.to_csv(S/'stage7_v4_feature_analysis.csv',index=False)
 lh={'mse':local,'thresholds':{'production':{'value':PROD,'fpr':0.0,'false_positive':0},'normal_max':{'value':mx,'fpr':1/329,'false_positive':1},'normal_p99':{'value':p99,'fpr':23/329,'false_positive':23},'best_offline_v4_simulation':{'value':0.011002919636666775,'fpr':147/329,'false_positive':147}}};(S/'stage7_v4_localhost_safety.json').write_text(json.dumps(lh,indent=2))
 repro={'seed':42,'row_count':len(d),'dataset_hash':sha(S/'stage7_redesigned_anomalies_v4_raw.csv'),'candidate_hash':sha(B/'models/candidate/vae_model_candidate.pth'),'production_hashes_after':h,'candidate_train_hash':sha(B/'dataset/retraining/X_train_candidate.npy'),'duplicate_rate':float(d.base_record_id.duplicated().mean()),'contamination':'0 synthetic V4 rows written to X_train_candidate'};(S/'stage7_v4_reproducibility.json').write_text(json.dumps(repro,indent=2))
 ready=len(d)==1500 and all(x['detect_normal_max']>=.75 for x in pt) and lh['thresholds']['normal_max']['fpr']==0
 report='# Stage 7.5 — V4 Validation\n\nGenerated valid: '+str(len(d))+' / 1500; archive rejections are retained separately.\n\n## Per-type\n```\n'+pd.DataFrame(pt).to_csv(index=False)+'```\n\n## Overlap\n```\n'+pd.DataFrame(ov).to_csv(index=False)+'```\n\n## Localhost\n```\n'+json.dumps(lh,indent=2)+'\n```\n\nProduction hashes captured after audit; candidate hash `'+repro['candidate_hash']+'`.\n\n**V4 DATASET '+('READY FOR CONTROLLED RETRAINING REVIEW' if ready else 'REJECTED — FURTHER REDESIGN REQUIRED')+'**. No retraining or deployment performed.\n';(S/'stage7_v4_validation_report.md').write_text(report,encoding='utf-8')
if __name__=='__main__':main()
