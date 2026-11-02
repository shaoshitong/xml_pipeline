"""Finite, resumable 2023-present AI source scan; use official draw.io import only.

The existing frozen 200-paper job finishes first. This worker then paginates
the remaining date partitions without an agent, preserving all prior once claims.
"""
from pathlib import Path
import calendar, collections, datetime, fcntl, hashlib, json, os, re, sqlite3
import sys, time, urllib.parse, xml.etree.ElementTree as ET

R = Path('/backup/shaoshitong/img2code_20261029')
S = R/'conversion/scripts'
sys.path[:0] = [str(S), str(R/'env'), str(R/'evaluation/assets/pdf_inventory_python_v1')]
import arxiv_sourceonly_bulk_200_v1_1 as builtin

OLD = R/'clean/arxiv_research_figures_v1/new_bulk_200_v1'
D = R/'clean/arxiv_research_figures_v1/recent_ai_source_expansion_v2'
NS = {'a':'http://www.w3.org/2005/Atom', 'o':'http://a9.com/-/spec/opensearch/1.1/',
      'r':'http://arxiv.org/schemas/atom'}
CATEGORIES = {'cs.CV', 'cs.LG', 'cs.AI', 'cs.CL'}
BUDGET = 512*1024**3
sha = lambda b: hashlib.sha256(b).hexdigest()
now = builtin.now
atomic = builtin.atomic

def months(until):
    out = []
    for year in range(2023, until.year+1):
        for month in range(1, 13):
            if (year, month) > (until.year, until.month):
                continue
            end = min(datetime.date(year, month, calendar.monthrange(year, month)[1]), until)
            out.append({'key':f'{year:04d}{month:02d}', 'from':f'{year:04d}{month:02d}010000',
                        'to':end.strftime('%Y%m%d')+'2359', 'start':0, 'state':'pending', 'failures':0})
    return list(reversed(out))

def split_days(unit):
    lo=datetime.datetime.strptime(unit['from'][:8], '%Y%m%d').date()
    hi=datetime.datetime.strptime(unit['to'][:8], '%Y%m%d').date()
    assert lo < hi, 'daily_partition_exceeds_API_result_limit'
    return [{'key':(lo+datetime.timedelta(days=i)).strftime('%Y%m%d'),
             'from':(lo+datetime.timedelta(days=i)).strftime('%Y%m%d')+'0000',
             'to':(lo+datetime.timedelta(days=i)).strftime('%Y%m%d')+'2359',
             'start':0, 'state':'pending', 'failures':0} for i in range((hi-lo).days+1)]

def parse_feed(body, unit=None):
    root=ET.fromstring(body)
    assert root.tag == '{'+NS['a']+'}feed', 'not_Atom_feed'
    total=int(root.findtext('o:totalResults', '-1', NS))
    assert total >= 0, 'API_error_or_missing_totalResults'
    records=[]
    for e in root.findall('a:entry', NS):
        versioned=e.findtext('a:id', '', NS).rsplit('/',1)[-1]
        assert re.fullmatch(r'\d{4}\.\d{4,5}v\d+', versioned), 'API_error_or_invalid_versioned_ID'
        cats=[c.get('term') for c in e.findall('a:category', NS)]
        date=e.findtext('a:published', '', NS)
        assert set(cats)&CATEGORIES and date[:4]>='2023', 'response_outside_category_or_year_scope'
        if unit:
            declared=re.sub(r'[^0-9]', '', date)[:12]
            assert unit['from'] <= declared <= unit['to'], 'response_outside_requested_date_partition'
        license_url=e.findtext('r:license', '', NS)
        records.append({'versioned_id':versioned,'arxiv_id':versioned.split('v')[0],
                        'version':int(versioned.rsplit('v',1)[1]),
                        'title':' '.join(e.findtext('a:title','',NS).split()),
                        'publication_date':date,'updated':e.findtext('a:updated','',NS),
                        'categories':cats,'license_urls':[license_url] if license_url else [],
                        'discovery':'official_arxiv_API_date_partition',
                        'abs_url':'https://arxiv.org/abs/'+versioned})
    return total, records

class Expansion(builtin.Pipeline):
    def __init__(self):
        builtin.D=D
        super().__init__()
        self.db.execute('create index if not exists pdf_status on pdfs(status)')
        self.db.execute('create table if not exists inherited_papers(id text primary key,record text)')
        self.db.commit()
        self._last_summary=0.
        self._defer_summary=False
        self.stats=collections.Counter()
        for status, raw in self.db.execute('select status,record from pdfs'):
            row=json.loads(raw)
            self.stats['pdf:'+status]+=1
            self.stats['new_official_calls']+=row.get('official_calls',0)
            self.stats['author_xml_recoveries']+=bool(row.get('author_xml_recovered'))
            self.stats['imported_history_pdf_hashes']+=bool(row.get('imported_history'))
        self.pages=D/'discovery';self.pages.mkdir(exist_ok=True)
        self.session.headers['User-Agent']='img2code-native-drawio-sourceonly/2.0 (2023-present AI source scan; singleconnection; min3.2s)'
        self.emit('expanded_source_scan_started', own_script_sha256=sha(Path(__file__).read_bytes()),
                  scope='2023 through frozen acquisition date, cs.CV/cs.LG/cs.AI/cs.CL, all paginated date partitions',
                  artificial_paper_limit=None, new_source_budget_bytes=BUDGET)

    def inherit(self):
        marker=D/'inherited_history.json'
        if marker.exists():
            return
        with sqlite3.connect((OLD/'once.sqlite').as_uri()+'?mode=ro',uri=True) as old:
            old.execute('begin')
            paper_rows=old.execute('select id,record from papers').fetchall()
            pdf_rows=old.execute('select id,status,record from pdfs').fetchall()
        for ident,raw in paper_rows:
            self.db.execute('insert or ignore into inherited_papers values(?,?)',(ident.split('v')[0],raw))
        for ident,status,raw in pdf_rows:
            row=json.loads(raw)
            row.update(imported_history=True, prior_official_calls=row.get('official_calls',0), official_calls=0,
                       reused_once_ledger=str((OLD/'once.sqlite').relative_to(R)))
            cur=self.db.execute('insert or ignore into pdfs values(?,?,?)',(ident,status,builtin.enc(row)))
            if cur.rowcount:
                self.stats['pdf:'+status]+=1
                self.stats['author_xml_recoveries']+=bool(row.get('author_xml_recovered'))
                self.stats['imported_history_pdf_hashes']+=1
        self.db.commit()
        atomic(marker,{'at_utc':now(),'prior_papers':len(paper_rows),'prior_pdf_hashes':len(pdf_rows),
                       'all_previous_once_claims_preserved':True,'historical_calls_are_not_new_calls':True})

    def publish_manifest(self):
        rows=self.db.execute("select record from pdfs where status='qualified_native_xml_png_pair' order by id")
        tmp=D/'manifest.jsonl.tmp'
        with tmp.open('w') as f:
            for row in rows:f.write(row[0]+'\n')
        os.replace(tmp,D/'manifest.jsonl')

    def summary(self, finished=False, force=False):
        if not hasattr(self,'stats') or self._defer_summary:
            return {}
        if not force and not finished and time.monotonic()-self._last_summary < 10:
            return {}
        self._last_summary=time.monotonic()
        states={k[4:]:v for k,v in self.stats.items() if k.startswith('pdf:')}
        pc=dict(self.db.execute('select status,count(*) from papers group by status'))
        cursor=json.loads((D/'cursor.json').read_text()) if (D/'cursor.json').exists() else {}
        out={'schema':'arxiv_recent_ai_source_expansion_v2','at_utc':now(),'finished':finished,
             'phase':'scanning_date_partitions','active_paper':self.active,'paper_states':pc,'pdf_states':states,
             'unique_pdf_hashes_including_prior_history':sum(states.values()),
             'new_official_calls':self.stats['new_official_calls'],
             'inherited_pdf_hashes':self.stats['imported_history_pdf_hashes'],
             'author_xml_recoveries_including_prior':self.stats['author_xml_recoveries'],
             'new_source_bytes_received':self.budget['new_source_bytes_received'],
             'qualified_native_xml_png_pairs_including_prior':states.get('qualified_native_xml_png_pair',0),
             'date_partitions':len(cursor.get('units',[])),
             'completed_partitions':sum(x['state'] in ['done','partitioned'] for x in cursor.get('units',[])),
             'failed_partitions':sum(x['state']=='typed_failure' for x in cursor.get('units',[])),
             'api_response_pages_frozen':cursor.get('pages_frozen',0),'artificial_paper_limit':None,
             'new_source_budget_bytes':BUDGET,'whole_paper_PDF_endpoint_requests':0,
             'external_model_calls':0,'custom_PDF_geometry_converter_used':False,'all_outputs_on_HKUST':True}
        atomic(D/'summary.json',out)
        return out

    def source(self, paper, target):
        archive=target/'source.archive'
        if archive.exists():
            return archive
        if self.budget['new_source_bytes_received'] >= BUDGET:
            raise ValueError('typed_skip_total_512GiB_source_budget_reached')
        st=os.statvfs(R)
        if st.f_bavail*st.f_frsize < 250*1024**3:
            raise ValueError('typed_skip_available_disk_below250GiB')
        url='https://arxiv.org/src/'+paper['versioned_id']
        journal=target/'source_attempt.json';part=target/'source.archive.part'
        if journal.exists():
            raise ValueError('typed_skip_prior_source_attempt_without_completed_archive')
        builtin.once(journal,{'url':url,'at_utc':now(),'source_attempts':1,'no_automatic_redownload':True})
        self.emit('source_attempt',paper=paper['versioned_id'],url=url)
        count=0;checkpoint=0
        try:
            with self.request(url,stream=True) as response:
                ct=response.headers.get('Content-Type','').lower()
                builtin.once(target/'source_response_headers.json',{'content_type':ct,
                             'content_length':response.headers.get('Content-Length'),'response_url':response.url,'at_utc':now()})
                if 'application/pdf' in ct:
                    raise ValueError('typed_skip_src_endpoint_returned_PDF_content_type_before_body')
                if int(response.headers.get('Content-Length') or 0)>128*1024**2:
                    raise ValueError('typed_skip_source_ContentLength_above128MiB')
                with part.open('wb') as out:
                    for block in response.iter_content(64*1024):
                        if not block:continue
                        count+=len(block);self.budget['new_source_bytes_received']+=len(block)
                        if count==len(block) and block.startswith(b'%PDF-'):
                            raise ValueError('typed_skip_src_endpoint_PDF_only_first_chunk')
                        if count>128*1024**2 or self.budget['new_source_bytes_received']>BUDGET:
                            raise ValueError('typed_skip_source_or_total_byte_limit')
                        out.write(block)
                        if count-checkpoint>=8*1024**2:
                            checkpoint=count;out.flush();atomic(D/'network_bytes.json',self.budget)
                            self.emit('source_bytes',paper=paper['versioned_id'],paper_bytes=count,
                                      total_new_source_bytes=self.budget['new_source_bytes_received']);self.summary()
            os.replace(part,archive)
            builtin.once(target/'source_receipt.json',{'url':url,'sha256':sha(archive.read_bytes()),
                         'bytes':archive.stat().st_size,'at_utc':now()})
            return archive
        finally:
            atomic(D/'network_bytes.json',self.budget)

    def pdf(self, path, paper, source_root):
        ident=sha(path.read_bytes())
        if self.db.execute('select 1 from pdfs where id=?',(ident,)).fetchone():
            return
        self._defer_summary=True
        try:
            super().pdf(path,paper,source_root)
        finally:
            self._defer_summary=False
            row=self.db.execute('select status,record from pdfs where id=?',(ident,)).fetchone()
            if row:
                status,raw=row;record=json.loads(raw)
                self.stats['pdf:'+status]+=1
                self.stats['new_official_calls']+=record.get('official_calls',0)
                self.stats['author_xml_recoveries']+=bool(record.get('author_xml_recovered'))
                if status=='qualified_native_xml_png_pair':self.publish_manifest()
            self.summary()

    def paper(self,paper):
        ident=paper['versioned_id']
        if self.db.execute('select 1 from inherited_papers where id=?',(paper['arxiv_id'],)).fetchone():return
        old=self.db.execute('select status from papers where id=?',(ident,)).fetchone()
        if old and old[0]!='attempt_started':return
        self.active=ident;target=D/'papers'/ident;target.mkdir(parents=True,exist_ok=True)
        rec={'id':ident,'started_at_utc':now(),'metadata':paper,'source_only':True}
        if not old:
            self.db.execute('insert into papers values(?,?,?)',(ident,'attempt_started',builtin.enc(rec)));self.db.commit()
        try:
            metadata=target/'provenance.json'
            if not metadata.exists():
                with self.request(paper['abs_url']) as response:body=response.content
                if len(body)>2*1024**2:raise ValueError('abstract_metadata_over2MiB')
                (target/'abstract.html').write_bytes(body)
                resolved=builtin.metadata_from_abs(body.decode(errors='replace'),ident)
                builtin.once(metadata,dict(paper,**{k:v for k,v in resolved.items() if k not in paper or k=='license_urls'}))
            rec['metadata']=json.loads(metadata.read_text())
            archive=self.source(paper,target);source_root=target/'source';marker=target/'extraction.json'
            if not marker.exists():builtin.once(marker,builtin.safe_extract(archive,source_root,max_total=512*1024**2,max_files=20000))
            if not json.loads(marker.read_text()).get('extracted'):
                rec.update(status='typed_skip_no_extractable_source');return
            pdfs=sorted(p for p in source_root.rglob('*') if p.is_file() and p.suffix.lower()=='.pdf')
            rec['pdf_paths_discovered']=len(pdfs)
            for path in pdfs:self.pdf(path,paper,source_root)
            rec['status']='source_completed';self.emit('source_completed',paper=ident,pdf_paths=len(pdfs))
        except Exception as e:
            rec.update(status='typed_skip_source_attempt',reason=type(e).__name__+':'+str(e)[:1200])
            self.emit('source_skipped',paper=ident,reason=rec['reason'])
        finally:
            rec.setdefault('status','typed_skip_source_attempt');rec['finished_at_utc']=now()
            atomic(target/'record.json',rec)
            self.db.execute('update papers set status=?,record=? where id=?',(rec['status'],builtin.enc(rec),ident));self.db.commit()
            self.active=None;self.summary(force=True)

    def discover(self,unit):
        folder=self.pages/unit['key']/str(unit['start']);folder.mkdir(parents=True,exist_ok=True)
        frozen=folder/'page.json'
        if frozen.exists():
            page=json.loads(frozen.read_text());body=(folder/'response.atom').read_bytes()
            assert sha(body)==page['response_sha256']
            assert sha((folder/'papers.jsonl').read_bytes())==page['papers_sha256']
            return page, [json.loads(l) for l in (folder/'papers.jsonl').read_text().splitlines()]
        query='(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:cs.CL) AND submittedDate:['+unit['from']+' TO '+unit['to']+']'
        params={'search_query':query,'start':unit['start'],'max_results':200,
                'sortBy':'submittedDate','sortOrder':'descending'}
        url='https://export.arxiv.org/api/query?'+urllib.parse.urlencode(params)
        with self.request(url,stream=True) as response:
            blocks=[];size=0
            for block in response.iter_content(64*1024):
                size+=len(block)
                if size>16*1024**2:raise ValueError('metadata_response_above16MiB')
                blocks.append(block)
            body=b''.join(blocks)
        total,records=parse_feed(body,unit)
        raw=''.join(builtin.enc(p)+'\n' for p in records).encode()
        (folder/'response.atom').write_bytes(body);(folder/'papers.jsonl').write_bytes(raw)
        page={'at_utc':now(),'url':url,'partition':dict(unit),'total_results':total,'entries':len(records),
              'response_sha256':sha(body),'papers_sha256':sha(raw),'no_native_results_used_for_selection':True}
        builtin.once(frozen,page);self.emit('metadata_page_frozen',partition=unit['key'],start=unit['start'],entries=len(records),total_results=total)
        return page,records

    def run_expansion(self):
        self.inherit()
        self.publish_manifest()
        freeze=json.loads((D/'freeze.json').read_text())
        cursorfile=D/'cursor.json'
        if cursorfile.exists():cursor=json.loads(cursorfile.read_text())
        else:
            cursor={'units':months(datetime.date.fromisoformat(freeze['until_date_UTC'])),'position':0,'pages_frozen':0}
            atomic(cursorfile,cursor)
        try:
            while any(u['state']=='pending' for u in cursor['units']):
                if self.budget['new_source_bytes_received'] >= BUDGET:
                    self.emit('resource_limit_reached',reason='512GiB_new_source_network_budget');break
                st=os.statvfs(R)
                if st.f_bavail*st.f_frsize<250*1024**3:
                    self.emit('resource_limit_reached',reason='available_disk_below250GiB');break
                i=cursor['position']%len(cursor['units']);unit=cursor['units'][i]
                cursor['position']=(i+1)%len(cursor['units'])
                if unit['state']!='pending':continue
                try:
                    page,records=self.discover(unit)
                    if page['total_results']>20000:
                        cursor['units'].extend(split_days(unit));unit['state']='partitioned'
                    else:
                        for paper in records:self.paper(paper)
                        unit['start']+=len(records)
                        if not records or unit['start']>=page['total_results']:unit['state']='done'
                    cursor['pages_frozen']+=1
                except Exception as e:
                    unit['failures']+=1;unit['last_error']=type(e).__name__+':'+str(e)[:1200]
                    if unit['failures']>=3:unit['state']='typed_failure'
                    self.emit('metadata_partition_failure',partition=unit['key'],attempt=unit['failures'],reason=unit['last_error'])
                atomic(cursorfile,cursor);self.summary(force=True)
            # A page is immutable; future resumes replay it only through once claims.
            finished=not any(u['state']=='pending' for u in cursor['units'])
            summary=self.summary(finished=finished,force=True)
            self.publish_manifest()
            self.emit('run_complete',**summary)
        finally:
            if self.renderer:self.renderer.close()

def selftest():
    # Test queue integrity with the real previously frozen official API response.
    fixture=(OLD/'discovery/api_probe_response.bin').read_bytes()
    total,records=parse_feed(fixture)
    assert total>=200 and len(records)==200
    assert len({p['arxiv_id'] for p in records})==200
    ms=months(datetime.date(2026,11,2));assert len(ms)==47
    ds=split_days({'from':'202402010000','to':'202402292359'})
    assert len(ds)==29 and ds[-1]['to']=='202402292359'
    with sqlite3.connect(':memory:') as db:
        db.execute('create table pdfs(id text primary key,status text,record text)')
        row=('hash','unsupported_builtin_import','{}')
        db.execute('insert or ignore into pdfs values(?,?,?)',row)
        db.execute('insert or ignore into pdfs values(?,?,?)',row)
        assert db.execute('select count(*) from pdfs').fetchone()[0]==1
    # Existing real positive/negative importer + native rendering/edit proof must remain valid.
    positive=json.loads((OLD/'procedure_selftest/success.json').read_text())
    assert positive['success'] and positive['official_render_edit']['edit_probe']['restored_actual_PNG_exact']
    report={'success':True,'official_real_feed_records':len(records),'leap_year_day_partition':True,
            'date_partitions_2023_through_20261102':len(ms),'cross_run_PDF_once_key_is_hash':True,
            'official_importer_and_render_edit_positive_unchanged':True,'external_models':0}
    print(builtin.enc(report))
    return report

def main():
    if '--selftest' in sys.argv:selftest();return
    D.mkdir(parents=True,exist_ok=True)
    # Avoid overlapping the existing source HTTP stream, without killing or polling it with an agent.
    with (D/'supervisor.lock').open('a') as owner:
        fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
        atomic(D/'summary.json',{'at_utc':now(),'phase':'queued_after_existing_200_paper_job',
               'predecessor':str(OLD),'artificial_paper_limit':None,'external_model_calls':0})
        with (OLD/'program.lock').open('a') as predecessor:
            fcntl.flock(predecessor,fcntl.LOCK_EX)
            # Keep this lock until done, so the old idempotent launcher cannot race us.
            cfg=json.loads((D/'freeze.json').read_text())
            for path,digest in cfg['pins'].items():
                assert sha((R/path).read_bytes())==digest, 'Pinned procedure changed while queued: '+path
            Expansion().run_expansion()

if __name__=='__main__':main()
