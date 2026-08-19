"""Read-only observability audit of V4 mass_archive_access."""
from pathlib import Path
import pandas as pd
B=Path(__file__).resolve().parents[1];S=B/'stage7'
def main():
 r=pd.read_csv(B/'dataset/retraining/retraining_dataset_combined_raw.csv',encoding='utf-8-sig');n=r[(r.candidate_type=='NORMAL')&(r.source_type=='SYNTHETIC')].copy();n['_o'],_=pd.qcut(n.jumlah_objek.astype(float),q=4,duplicates='drop',retbins=True);n['_d'],_=pd.qcut(n.durasi_ms.astype(float),q=5,duplicates='drop',retbins=True);n['_a']=n.aksi.astype(str);z=n.groupby(['_a','_o','_d']).size().reset_index(name='normal_count');z['normal_frequency']=z.normal_count/len(n);z.to_csv(S/'stage7_v5_mass_archive_joint_frequency.csv',index=False)
 rep='# V5 Mass Archive Forensic\n\nV4 used Akses Berkas + P95 object count (10) + P05 duration (396ms). The V4 forensic simulation measured this joint pattern as common (median frequency 5.86%) and only 3.5% detected above Normal MAX. Object count is capped at 10 in normal raw data, so this feature set cannot defensibly observe *mass* extraction volume.\n\nExternal IP/device may form a distinct access-risk scenario, but it is not evidence of mass extraction. Recommendation: **REMOVE `mass_archive_access` from V5 taxonomy** unless a new observable volume/session feature is added; do not relabel external access as mass archive access.\n';(S/'stage7_v5_mass_archive_forensic_report.md').write_text(rep)
if __name__=='__main__':main()
