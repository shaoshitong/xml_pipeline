"""Additive Unicode-safe telemetry fix; v3 conversion/once logic is unchanged."""
from pathlib import Path
import collections,json,os,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');sys.path[:0]=[str(R/'conversion/scripts'),str(R/'env')]
import arxiv_parallel_pipeline_v3 as engine

def safe_statistics_write(path,value):
 # PDF metadata can contain lone UTF-16 surrogates. JSON escapes preserve them;
 # native PDF/XML/image bytes are never rewritten to repair display metadata.
 raw=(json.dumps(value,ensure_ascii=True,indent=2)+'\n').encode('ascii')
 tmp=path.with_name(path.name+'.tmp');tmp.write_bytes(raw);os.replace(tmp,path)

class UnicodeSafeState(engine.State):
 def save(self,finished=False):
  with self.mu:
   elapsed=time.perf_counter()-self.started
   stages={k:{**v,'samples_per_second':v['count']/v['seconds'] if v['seconds'] else None} for k,v in self.stats.items()}
   imports=stages.get('official_PDF_import',{}).get('count',0);alerts=[]
   if imports>=100 and not self.pdf_counts.get('qualified_native_xml_png_pair',0):
    alerts.append({'kind':'low_native_XML_recovery_rate','note':'Official importer supports embedded drawio XML; producer histogram retained for source-selection diagnosis. No model review invoked.'})
   x={'at_utc':engine.now(),'driver_revision':'3.1 Unicode-safe telemetry','profile':self.profile,'active_paper':self.active,
      'elapsed_wall_seconds':elapsed,'route':'arxiv -> VPS -> HKUST3','Mac_in_data_path':False,
      'download_threads':4,'native_import_workers':4,'new_source_network_bytes':self.net_bytes,
      'wall_source_MiB_s':self.net_bytes/1024**2/elapsed,'stages':stages,
      'timing_note':'Stage seconds are cumulative across workers and inclusive where marked; wall time is separate.',
      'pdf_states':dict(self.pdf_counts),'official_calls_total_including_history':self.official_calls,
      'paper_states':{k:v for k,v in self.paper_counts.items() if v},'PDF_creator_or_producer_histogram':dict(self.creators),
      'alerts':alerts,'finished':finished,'external_model_calls':0}
   safe_statistics_write(engine.CONTROL/(self.profile+'.performance.json'),x)

def selftest():
 data={'creator':'PDF metadata lone surrogate '+chr(0xd800),'Chinese':'科研框图','emoji':'\U0001f600',
       'seconds':.123,'preserve_original_PDF_XML_bytes':True}
 raw=json.dumps(data,ensure_ascii=True).encode('ascii');assert json.loads(raw)==data
 print(json.dumps({'Unicode_metadata_roundtrip_passed':True,'native_importer_changed':False,
                  'source_XML_PDF_image_bytes_changed':False,'external_models':0}))

if __name__=='__main__':
 if '--selftest' in sys.argv:selftest()
 else:
  engine.State=UnicodeSafeState
  engine.run()
