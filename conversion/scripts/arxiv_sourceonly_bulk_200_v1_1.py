"""Fixed source-only arXiv -> unmodified official draw.io embedded-XML pipeline."""
from pathlib import Path
import argparse,base64,collections,datetime,fcntl,hashlib,html,importlib.util,json,os,re,shutil,sqlite3,subprocess,sys,time,urllib.parse,xml.etree.ElementTree as ET,zlib
import requests
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/new_bulk_200_v1';S=R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v1/official_importer'
sys.path[:0]=[str(R/'conversion/scripts'),str(R/'evaluation/assets/pdf_inventory_python_v1')]
from arxiv_source_pilot import safe_extract,metadata_from_abs
from arxiv_bulk_official_xml_png_v1 import OfficialXmlPng
import fitz
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat();sha=lambda b:hashlib.sha256(b).hexdigest()
def enc(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def atomic(p,x):
    p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(q,p)
def once(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def models(xml):
    if len(xml.encode())>64*1024**2:raise ValueError('author_XML_above64MiB')
    root=ET.fromstring(xml)
    if root.tag=='mxGraphModel':return [root]
    if root.tag!='mxfile':raise ValueError('not_author_drawio_XML')
    out=[]
    for d in root.findall('diagram'):
        m=d.find('mxGraphModel')
        if m is None:
            s=(d.text or '').strip()
            if s.startswith('<'):m=ET.fromstring(s)
            else:
                dec=zlib.decompressobj(-15);payload=dec.decompress(base64.b64decode(s),64*1024**2+1)
                if len(payload)>64*1024**2 or dec.unconsumed_tail:raise ValueError('compressed_page_above64MiB')
                m=ET.fromstring(urllib.parse.unquote(payload.decode()))
        out.append(m)
    return out
def facts(xml):
    ms=models(xml);cells=[c for m in ms for c in m.iter('mxCell')];vs=[c for c in cells if c.get('vertex')=='1'];es=[c for c in cells if c.get('edge')=='1'];labels=[' '.join(html.unescape(re.sub('<[^>]+>',' ',c.get('value',''))).split()) for c in cells];labels=[s for s in labels if s]
    ims=[c for c in vs if 'shape=image' in c.get('style','') or re.search(r'(?:^|;)image=',c.get('style',''))];texts=[c for c in vs if re.search(r'(?:^|;)text(?:;|$)|shape=text',c.get('style',''))]
    groups={c.get('id') for c in vs if re.search(r'(?:^|;)group(?:=1)?(?:;|$)',c.get('style',''))};vmap={c.get('id'):c for c in vs}
    def under_group(c):
        p=c.get('parent');seen=set()
        while p in vmap and p not in seen:
            if p in groups:return True
            seen.add(p);p=vmap[p].get('parent')
        return False
    objects=sum(not under_group(c) and (c.get('id') in groups or c not in texts) for c in vs)
    chars=sum(map(len,labels));distinct=len(set(labels));complexity=(len(ims)>=4 and chars>=200 and distinct>=8) or (objects>=20 and len(es)>=15 and chars>=200 and distinct>=15) or (objects>=30 and chars>=350 and distinct>=20)
    return {'pages':len(ms),'vertices':len(vs),'edges':len(es),'image_vertices':len(ims),'text_vertices':len(texts),'independent_drawing_objects':objects,'label_characters':chars,'distinct_labels':distinct,'unicode_label_characters':sum(ord(c)>127 for s in labels for c in s),'complexity_match':complexity,'all_single_image_wrapper':len(ims)==1 and objects<=1,'objects_are_not_asserted_semantic_nodes':True}

class Pipeline:
    def __init__(self):
        D.mkdir(parents=True,exist_ok=True);self.lock=(D/'program.lock').open('a');fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.db=sqlite3.connect(D/'once.sqlite');self.db.execute('pragma journal_mode=WAL');self.db.execute('create table if not exists papers(id text primary key,status text,record text)');self.db.execute('create table if not exists pdfs(id text primary key,status text,record text)');self.db.commit()
        self.events=(D/'events.jsonl').open('a',buffering=1);self.session=requests.Session();self.session.headers['User-Agent']='img2code-native-drawio-sourceonly/1.0 bounded200research-papers 3.2s-singleconnection'
        # Preserve once claims from interrupted imports; never call an input hash twice.
        for ident,payload in self.db.execute("select id,record from pdfs where status='attempt_started'").fetchall():
            prior=json.loads(payload);prior.update(status='interrupted_import_not_repeated',reason='A previous once claim exists; retained for review without repeating official invocation.')
            self.db.execute('update pdfs set status=?,record=? where id=?',(prior['status'],enc(prior),ident))
        self.db.commit()
        prior_events=[json.loads(l) for l in (D/'events.jsonl').read_text().splitlines()]
        requested={r.get('paper') for r in prior_events if r.get('event')=='source_attempt'}
        for ident,payload in self.db.execute("select id,record from papers where status='attempt_started'").fetchall():
            target=D/'papers'/ident
            if ident in requested and not (target/'source.archive').exists():
                prior=json.loads(payload);prior.update(status='typed_skip_interrupted_source_attempt',reason='Prior source HTTP attempt existed; preserve it and skip without restarting download.')
                self.db.execute('update papers set status=?,record=? where id=?',(prior['status'],enc(prior),ident));atomic(target/'record.json',prior)
        self.db.commit()
        self.last=0.;self.renderer=None;self.active=None;self.budget=json.loads((D/'network_bytes.json').read_text()) if (D/'network_bytes.json').exists() else {'new_source_bytes_received':0};self.reuse={}
        for old in [R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v1',R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v2b']:
            for p in (old/'cases').glob('*/record.json'):
                r=json.loads(p.read_text())
                if r.get('status')=='unsupported_builtin_import':self.reuse[r['id']]=(p,r)
        self.emit('pipeline_started',pid=os.getpid(),script_sha256=sha(Path(__file__).read_bytes()))
    def emit(self,event,**kw):
        r={'at_utc':now(),'event':event,**kw};self.events.write(enc(r)+'\n');print(enc(r),flush=True)
    def summary(self,finished=False):
        pc=dict(self.db.execute('select status,count(*) from papers group by status'));fc=dict(self.db.execute('select status,count(*) from pdfs group by status'))
        rows=[json.loads(r[0]) for r in self.db.execute("select record from pdfs where status='qualified_native_xml_png_pair' order by id")]
        (D/'manifest.jsonl.tmp').write_text(''.join(enc(r)+'\n' for r in rows));os.replace(D/'manifest.jsonl.tmp',D/'manifest.jsonl')
        out={'schema':'arxiv_sourceonly_bulk_progress_v1','at_utc':now(),'finished':finished,'frozen_papers':200,'active_paper':self.active,'paper_states':pc,'pdf_states':fc,'unique_pdf_hashes':sum(fc.values()),'new_official_calls':sum(json.loads(r[0]).get('official_calls',0) for r in self.db.execute('select record from pdfs')),'new_source_bytes_received':self.budget['new_source_bytes_received'],'source_archives_completed':sum(1 for _ in (D/'papers').glob('*/source.archive')),'reused_source_papers':sum(json.loads(r[0]).get('reused_completed_source',False) for r in self.db.execute('select record from papers')),'author_xml_recoveries':sum(json.loads(r[0]).get('author_xml_recovered',False) for r in self.db.execute('select record from pdfs')),'qualified_native_xml_png_pairs':len(rows),'whole_paper_PDF_endpoint_requests':0,'source_endpoint_PDF_only_payloads_received_prior_to_guard':sum(1 for p in (D/'papers').glob('*/extraction.json') if json.loads(p.read_text()).get('format')=='pdf_only'),'external_model_calls':0,'custom_PDF_geometry_converter_used':False,'all_outputs_on_HKUST':True,'new_source_budget_bytes':10*1024**3,'source_limit_bytes':128*1024**2}
        atomic(D/'summary.json',out);return out
    def request(self,url,stream=False):
        time.sleep(max(0,3.2-(time.monotonic()-self.last)));self.last=time.monotonic();self.emit('request_start',url=url);self.summary()
        response=self.session.get(url,stream=stream,timeout=(30,180));response.raise_for_status();return response
    def source(self,paper,target):
        archive=target/'source.archive'
        if archive.exists():return archive
        if self.budget['new_source_bytes_received']>=10*1024**3:raise ValueError('typed_skip_total_source_budget_reached')
        url='https://arxiv.org/src/'+paper['versioned_id'];part=target/'source.archive.part';journal=target/'source_attempt.json'
        if journal.exists():raise ValueError('typed_skip_prior_source_attempt_without_completed_archive')
        once(journal,{'url':url,'at_utc':now(),'source_attempts':1,'no_automatic_redownload':True});self.emit('source_attempt',paper=paper['versioned_id'],url=url)
        with self.request(url,stream=True) as response:
            content_type=response.headers.get('Content-Type','').lower()
            once(target/'source_response_headers.json',{'content_type':content_type,'content_length':response.headers.get('Content-Length'),'response_url':response.url,'at_utc':now()})
            if 'application/pdf' in content_type:raise ValueError('typed_skip_src_endpoint_returned_PDF_content_type_before_body')
            length=int(response.headers.get('Content-Length') or 0)
            if length>128*1024**2:raise ValueError('typed_skip_source_ContentLength_above128MiB')
            count=0
            with part.open('wb') as out:
                for block in response.iter_content(64*1024):
                    if not block:continue
                    count+=len(block);self.budget['new_source_bytes_received']+=len(block);atomic(D/'network_bytes.json',self.budget)
                    if count==len(block) and block.startswith(b'%PDF-'):raise ValueError('typed_skip_src_endpoint_PDF_only_first_chunk')
                    if count>128*1024**2 or self.budget['new_source_bytes_received']>10*1024**3:raise ValueError('typed_skip_source_or_total_byte_limit')
                    out.write(block);out.flush();self.emit('source_bytes',paper=paper['versioned_id'],paper_bytes=count,total_new_source_bytes=self.budget['new_source_bytes_received']);self.summary()
        os.replace(part,archive);once(target/'source_receipt.json',{'url':url,'sha256':sha(archive.read_bytes()),'bytes':archive.stat().st_size,'at_utc':now()});return archive
    def pdf(self,path,paper,source_root):
        data=path.read_bytes();ident=sha(data);found=self.db.execute('select status from pdfs where id=?',(ident,)).fetchone()
        if found:return
        case=D/'cases'/ident;case.mkdir(parents=True,exist_ok=True);rec={'id':ident,'paper':paper['versioned_id'],'pdf_file':str(path.relative_to(R)),'pdf_sha256':ident,'pdf_bytes':len(data),'official_calls':0,'author_xml_recovered':False,'qualified':False,'at_utc':now()}
        self.db.execute('insert into pdfs values(?,?,?)',(ident,'attempt_started',enc(rec)));self.db.commit()
        try:
            parts=[p.lower() for p in path.relative_to(source_root).parts]
            if any(p in ['logo','logos'] for p in parts[:-1]) or 'logo' in path.stem.lower() or path.name.lower() in ['paper.pdf','main_paper.pdf']:
                rec.update(status='typed_skip_logo_support_or_wholepaper');return
            with fitz.open(path) as doc:
                if len(doc)!=1:rec.update(status='typed_skip_not_independent_single_page_figure',pdf_pages=len(doc));return
            if ident in self.reuse:
                prev,old=self.reuse[ident];rec.update(status='unsupported_builtin_import',reason='official_returned_no_embedded_diagram',reused_once_result=str(prev.relative_to(R)),reused_record_sha256=sha(prev.read_bytes()));return
            rec['official_calls']=1
            # Claim is committed before invocation: process interruption never repeats it.
            self.db.execute('update pdfs set record=? where id=?',(enc(rec),ident));self.db.commit()
            output=case/'author.drawio'
            q=subprocess.run(['/usr/bin/node','--max-old-space-size=768',str(S/'node_adapter.cjs'),str(S),str(path),str(output)],capture_output=True,text=True,timeout=35)
            if q.returncode:raise RuntimeError('official_importer_execution:'+q.stderr[-1000:])
            result=json.loads(q.stdout)
            if result['status']=='no_embedded_diagram':rec.update(status='unsupported_builtin_import',reason='official_returned_no_embedded_diagram');return
            xml=output.read_text();rec.update(author_xml_recovered=True,author_xml_file=str(output.relative_to(R)),author_xml_sha256=sha(output.read_bytes()),author_XML_unmodified=True,source_provenance='PDF_native_embedded_author_XML')
            stats=facts(xml);rec['structure']=stats
            with (D/'recovery_index.jsonl').open('a') as f:f.write(enc(rec)+'\n')
            if stats['pages']!=1 or stats['all_single_image_wrapper'] or not stats['complexity_match']:rec.update(status='recovered_XML_below_complexity_or_wrapper');return
            refs=[]
            for model in models(xml):
                for cell in model.iter('mxCell'):
                    refs+=re.findall(r'(?:^|;)image=([^;]+(?:;base64,[^;]+)?)',cell.get('style',''))
                    value=html.unescape(cell.get('value',''))
                    refs+=re.findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)',value,re.I)
                    refs+=re.findall(r'<(?:\w+:)?image\b[^>]*\b(?:xlink:)?href=["\']([^"\']+)',value,re.I)
            assets={}
            for ref in refs:
                if ref.startswith(('data:','#')):continue
                if ref.startswith(('http:','https:','file:','//')):raise ValueError('unclosed_external_author_asset')
                asset=(path.parent/urllib.parse.unquote(ref)).resolve()
                if not asset.is_relative_to(source_root.resolve()) or not asset.is_file():raise ValueError('unclosed_relative_author_asset')
                assets[urllib.parse.unquote(urllib.parse.urlparse(urllib.parse.urljoin('http://source.invalid/',ref)).path).lstrip('/')]=asset
            if self.renderer is None:self.renderer=OfficialXmlPng()
            evidence=self.renderer.render(xml,case,assets)
            if output.read_text()!=xml:raise ValueError('author_XML_changed')
            with fitz.open(path) as doc:doc[0].get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).save(case/'source_pdf_reference.png')
            from PIL import Image,ImageChops,ImageStat
            with Image.open(case/'source_pdf_reference.png') as a,Image.open(case/'official.png') as b:
                diff=ImageChops.difference(a.convert('RGB').resize((512,512)),b.convert('RGB').resize((512,512)));alignment={'mean_absolute_RGB_difference_resized512':sum(ImageStat.Stat(diff).mean)/3,'original_pdf_fidelity':'review_not_certified','metric_note':'Descriptive comparison only; no image fitting or source replacement.'}
            once(case/'pdf_alignment_review.json',alignment);shutil.copyfile(path,case/'source.pdf')
            rec.update(status='qualified_native_xml_png_pair',qualified=True,image_file=str((case/'official.png').relative_to(R)),image_sha256=evidence['png_sha256'],render_edit_evidence=str((case/'render_edit_evidence.json').relative_to(R)),original_PDF_fidelity='review_not_certified',assets_complete=True,XML_UTF8_bytes=len(xml.encode()),XML_Unicode_characters_preserved=stats['unicode_label_characters'],frozen_author_XML_hash_unchanged=True,external_models=0,custom_PDF_geometry_converter=False)
        except subprocess.TimeoutExpired:rec.update(status='typed_skip_official_timeout')
        except Exception as e:rec.update(status='technical_failure_review',reason=type(e).__name__+':'+str(e)[:1200])
        finally:
            rec.setdefault('status','typed_skip_unspecified');once(case/'record.json',rec);self.db.execute('update pdfs set status=?,record=? where id=?',(rec['status'],enc(rec),ident));self.db.commit();self.emit('pdf_finished',id=ident,paper=paper['versioned_id'],status=rec['status'],official_calls=rec['official_calls']);self.summary()
    def paper(self,paper):
        ident=paper['versioned_id'];old=self.db.execute('select status from papers where id=?',(ident,)).fetchone()
        if old and old[0]!='attempt_started':return
        self.active=ident;target=D/'papers'/ident;target.mkdir(parents=True,exist_ok=True);rec={'id':ident,'started_at_utc':now(),'metadata':paper,'source_only':True}
        if not old:self.db.execute('insert into papers values(?,?,?)',(ident,'attempt_started',enc(rec)));self.db.commit()
        try:
            if paper.get('reuse_source_folder'):
                source_root=R/paper['reuse_source_folder'];assert (source_root.parent/'source_index.json').exists();rec['reused_completed_source']=True
            else:
                metadata=target/'provenance.json'
                if not metadata.exists():
                    with self.request(paper['abs_url']) as response:body=response.content
                    if len(body)>2*1024**2:raise ValueError('abstract_metadata_over2MiB')
                    (target/'abstract.html').write_bytes(body);resolved=metadata_from_abs(body.decode(errors='replace'),ident);once(metadata,dict(paper,**{k:v for k,v in resolved.items() if k not in paper or k=='license_urls'}))
                rec['metadata']=json.loads(metadata.read_text());archive=self.source(paper,target);source_root=target/'source';marker=target/'extraction.json'
                if not marker.exists():once(marker,safe_extract(archive,source_root,max_total=512*1024**2,max_files=20000))
                extraction=json.loads(marker.read_text())
                if not extraction.get('extracted'):rec.update(status='typed_skip_no_extractable_source');return
            pdfs=sorted(source_root.rglob('*.pdf'));rec['pdf_paths_discovered']=len(pdfs)
            for path in pdfs:self.pdf(path,paper,source_root)
            rec['status']='source_completed';self.emit('source_completed',paper=ident,pdf_paths=len(pdfs),reused=rec.get('reused_completed_source',False))
        except Exception as e:rec.update(status='typed_skip_source_attempt',reason=type(e).__name__+':'+str(e)[:1200]);self.emit('source_skipped',paper=ident,reason=rec['reason'])
        finally:
            rec.setdefault('status','typed_skip_source_attempt');rec['finished_at_utc']=now();atomic(target/'record.json',rec);self.db.execute('update papers set status=?,record=? where id=?',(rec['status'],enc(rec),ident));self.db.commit();self.summary()
    def run(self,limit=None):
        freeze=json.loads((D/'freeze.json').read_text());raw=(D/'papers.jsonl').read_bytes();assert sha(raw)==freeze['papers_sha256'];test=json.loads((D/'procedure_selftest/success.json').read_text());assert test['success'] and test['official_render_edit']['edit_probe']['restored_actual_PNG_exact']
        papers=[json.loads(l) for l in raw.decode().splitlines()]
        try:
            for paper in papers[:limit]:self.paper(paper)
            self.active=None;summary=self.summary(finished=not limit or limit>=len(papers));self.emit('run_complete',**summary)
        finally:
            if self.renderer:self.renderer.close()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int);a=p.parse_args();Pipeline().run(a.limit)
