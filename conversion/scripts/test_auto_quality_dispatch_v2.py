"""Real queue schema, semantic dedup, transactional rollback and human feedback."""
import copy
import json
import sqlite3
import tempfile
import xml.etree.ElementTree as E
from pathlib import Path

import auto_quality_dispatch_v2 as d


XML = '<mxfile host="old"><diagram id="page"><mxGraphModel pageWidth="200" pageHeight="100"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" parent="1" vertex="1" value="Alpha" style="shape=rectangle;fillColor=#ffffff;fontSize=12;"><mxGeometry x="10" y="20" width="40" height="30" as="geometry"/></mxCell><mxCell id="b" parent="1" vertex="1" value="Beta"><mxGeometry x="120" y="20" width="40" height="30" as="geometry"/></mxCell><mxCell id="e" parent="1" edge="1" source="a" target="b" style="endArrow=block;strokeWidth=1;"><mxGeometry relative="1" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'

def record(identifier, xml=XML):
    return {'id':identifier,'source_pair_sha256':identifier,'source_format':'html',
            'source_code_sha256':'a'*64,'source_image_sha256':'b'*64,
            'source_data_sha256':'d'*64, 'source_record':{'code_sha256':'a'*64,'image_sha256':'b'*64},
            'code_file':'clean/'+identifier+'/diagram.drawio','code_sha256':d.sha(xml.encode()),
            'image_file':'clean/'+identifier+'/image.png','image_sha256':'c'*64,
            'html_source_repair_v2':{'output_code_sha256':d.sha(xml.encode()),
                                   'source_code_sha256':'a'*64,'source_image_sha256':'b'*64},
            'root_review':{'source':'human','comment':'Keep the diagram footer intact.'}}


def failure():
    return {'state':'repair_required','accepted':False,'at':'2026-10-31T06:00:00+00:00',
            'policy':'fixture-policy','failures':['raster_anomaly:local_text_line_ssim_below_0.55'],
            'checks':{'source':{'supported':True,'ok':True,'failures':[]},
                      'visual':{'ok':False,'failures':['local_text_line_ssim_below_0.55'],
                       'worst_text_regions':[{'cell':'text'+str(i),'box':[i,2,i+10,12],'ssim':0.4} for i in range(30)]}}}


def write_record(root, identifier, xml=XML):
    r=record(identifier,xml)
    path=root/r['code_file'];path.parent.mkdir(parents=True,exist_ok=True);path.write_text(xml)
    return r


def baseline(root, identifier, current, xml=XML):
    folder=root/'conversion/harness_sessions'/('v5_'+identifier+'_old')/'baseline';folder.mkdir(parents=True,exist_ok=True)
    r={**current,'code_sha256':d.sha(xml.encode()),'html_source_repair_v2':{}}
    (folder/'conversion.json').write_text(json.dumps(r));(folder/'diagram.drawio').write_text(xml)
    return str(folder.parent.relative_to(root))


checks=[]
base=record('key')
key=d.semantic_revision_key(base,XML)
# XML serialization and style-property ordering alone cannot launch a new call.
serialized=XML.replace('host="old"','host="new" modified="later"').replace('shape=rectangle;fillColor=#ffffff;fontSize=12;','fontSize=12.0;shape=rectangle;fillColor=#ffffff;').replace('x="10" y="20"','y="20.0" x="1e1"')
assert d.semantic_revision_key(base,serialized)==key
assert d.semantic_revision_key({**base,'image_sha256':'e'*64},serialized)==key
assert d.semantic_revision_key({**base,'source_data_sha256':'e'*64},XML)!=key
for changed in (XML.replace('Alpha','Changed'),XML.replace('target="b"','target="a"'),
                XML.replace('parent="1" vertex="1" value="Beta"','parent="a" vertex="1" value="Beta"'),
                XML.replace('x="10"','x="11"'),XML.replace('fillColor=#ffffff','fillColor=#ff0000')):
    assert d.semantic_revision_key(base,changed)!=key
# Named-style order and default reset can affect paint; never over-normalize.
assert d._style('text;fontSize=12;') != d._style('fontSize=12;text;')
assert d._style(';text;fontSize=12;') != d._style('text;fontSize=12;')
checks+=['serialization/style order/numeric spelling deduplicated',
         'candidate PNG AA hash ignored; original data identity retained',
         'text/topology/geometry/color/paint-style semantics retained']

with tempfile.TemporaryDirectory(prefix='model_dispatch_test_') as directory:
    root=Path(directory);db=sqlite3.connect(':memory:')
    # Exact schema used by the running v5/v6 pools, including historical fields.
    db.execute('CREATE TABLE harness_queue_v3(id TEXT PRIMARY KEY,state TEXT,attempts INT DEFAULT 0,priority INT DEFAULT 0,worker_pid INT,started_at TEXT,heartbeat TEXT,session_dir TEXT,error TEXT)')
    db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT,output_record TEXT,worker_pid INT)')
    d.initialize(db);db.commit()
    def queued(identifier,state,worker=None,session=None):
        db.execute('INSERT INTO harness_queue_v3 VALUES(?,?,?,?,?,?,?,?,?)',
                   (identifier,state,7,88,worker,'old-start','old-beat',session,'historic-error'))
    def call(r,rep=None):
        db.execute('BEGIN IMMEDIATE')
        result=d.route_failure(db,r,rep or failure(),root)
        db.commit()
        return result
    # New failure inserts once; feedback preserves human content and <=20 boxes.
    r=write_record(root,'new');updated,summary=call(r)
    assert summary['queue_changed'] and summary['dispatched']
    assert db.execute('SELECT state,attempts,priority FROM harness_queue_v3 WHERE id="new"').fetchone()==('held_for_source_v5',0,1000)
    assert updated['root_review']['source']=='human'
    assert updated['root_review']['comment']==r['root_review']['comment']
    automatic=updated['root_review']['automatic_quality']
    assert automatic['source']=='automatic_quality' and len(automatic['local_text_boxes'])==20
    assert r['root_review'].get('automatic_quality') is None
    db.execute("UPDATE harness_queue_v3 SET state='attempt_finished',attempts=1 WHERE id='new'");db.commit()
    _,again=call({**r,'image_sha256':'f'*64})
    assert not again['dispatched'] and again['reason']=='semantic_revision_already_dispatched'
    assert db.execute('SELECT state,attempts FROM harness_queue_v3 WHERE id="new"').fetchone()==('attempt_finished',1)
    checks+=['new genuine failure queued once', 'machine feedback bounded and human review preserved',
             'same graph with changed PNG cannot repeat model attempt']
    # Running state/ownership and every history column remain byte-for-byte intact.
    for identifier,state,owner in [('run','running',99),('owned','held_for_quality_v2',99),('other','held_for_canvas_v6',None)]:
        r=write_record(root,identifier);queued(identifier,state,owner);db.commit()
        before=db.execute('SELECT * FROM harness_queue_v3 WHERE id=?',(identifier,)).fetchone()
        _,summary=call(r)
        assert not summary['queue_changed']
        assert before==db.execute('SELECT * FROM harness_queue_v3 WHERE id=?',(identifier,)).fetchone()
    # Releasing our quality hold changes STATE ONLY; no attempts/history reset.
    r=write_record(root,'hold');queued('hold','held_for_quality_v2');db.commit()
    before=db.execute('SELECT * FROM harness_queue_v3 WHERE id="hold"').fetchone()
    _,summary=call(r);after=db.execute('SELECT * FROM harness_queue_v3 WHERE id="hold"').fetchone()
    assert summary['queue_changed'] and after[1]=='held_for_source_v5'
    assert before[:1]+before[2:]==after[:1]+after[2:]
    checks+=['running/owned/other queue rows unchanged', 'quality hold released without erasing attempt/history']
    # Same canonical baseline, including serialization-only changes, is not new.
    r=write_record(root,'same',serialized);session=baseline(root,'same',r,XML);queued('same','attempt_finished',session=session);db.commit()
    _,summary=call(r)
    assert not summary['dispatched'] and summary['reason']=='finished_attempt_has_same_semantic_baseline'
    # A changed genuine deterministic source repair may receive one new attempt.
    new_xml=XML.replace('Alpha','Alpha restored')
    r=write_record(root,'changed',new_xml);session=baseline(root,'changed',r,XML);queued('changed','attempt_finished',session=session);db.commit()
    before=db.execute('SELECT * FROM harness_queue_v3 WHERE id="changed"').fetchone()
    _,summary=call(r);after=db.execute('SELECT * FROM harness_queue_v3 WHERE id="changed"').fetchone()
    assert summary['dispatched'] and summary['reason']=='new_deterministic_semantic_revision_requeued'
    assert before[:1]+before[2:]==after[:1]+after[2:]
    ledger=json.loads(db.execute('SELECT feedback FROM '+d.TABLE+' WHERE id="changed"').fetchone()[0])
    assert ledger['dispatch_evidence']['finished_baseline']['session']==session
    checks+=['same finished baseline not requeued', 'changed proven deterministic source revision requeued once with provenance']
    # A model revision cannot self-trigger another attempt simply by failing QA.
    r=write_record(root,'model',new_xml);r.pop('html_source_repair_v2');session=baseline(root,'model',r,XML);queued('model','attempt_finished',session=session);db.commit()
    _,summary=call(r);assert not summary['dispatched']
    # Cross-case archives and unsupported checker features do not trigger calls.
    r=write_record(root,'cross',new_xml);session=baseline(root,'cross',r,XML)
    path=root/session/'baseline/conversion.json';bad=json.loads(path.read_text());bad['id']='other';bad['source_pair_sha256']='other';path.write_text(json.dumps(bad));queued('cross','attempt_finished',session=session);db.commit()
    _,summary=call(r);assert not summary['dispatched'] and summary['reason']=='finished_session_source_identity_mismatch'
    r=write_record(root,'unsupported');rep=failure();rep['failures']=['source_coverage_failure: unsupported_fresh_source_features'];rep['checks']['visual']={};rep['checks']['source']={'supported':True,'ok':False,'failures':[{'reason':'unsupported_fresh_source_features'}]}
    _,summary=call(r,rep);assert not summary['dispatched']
    assert db.execute('SELECT 1 FROM harness_queue_v3 WHERE id="unsupported"').fetchone() is None
    checks+=['model output cannot self-loop', 'cross-source archive rejected', 'checker limitations not treated as model-repair evidence']
    # Caller rollback removes BOTH queue dispatch and its dedup ledger. No hidden
    # commit can consume a revision before the jobs CAS actually succeeds.
    r=write_record(root,'rollback');db.execute('BEGIN IMMEDIATE')
    _,summary=d.route_failure(db,r,failure(),root);assert summary['dispatched'];db.rollback()
    assert db.execute('SELECT 1 FROM harness_queue_v3 WHERE id="rollback"').fetchone() is None
    assert db.execute('SELECT 1 FROM '+d.TABLE+' WHERE id="rollback"').fetchone() is None
    db.execute('BEGIN IMMEDIATE')
    r=write_record(root,'bad-hash');r['code_sha256']='f'*64
    try:d.route_failure(db,r,failure(),root)
    except ValueError:db.rollback()
    else:raise AssertionError('changed XML hash accepted')
    assert db.execute('SELECT 1 FROM harness_queue_v3 WHERE id="bad-hash"').fetchone() is None
    try:d.route_failure(db,write_record(root,'no-tx'),failure(),root)
    except RuntimeError:pass
    else:raise AssertionError('transaction ownership requirement ignored')
    checks+=['caller rollback undoes queue and ledger', 'hash exception leaves no partial dispatch', 'caller transaction is mandatory']
    db.close()
print(json.dumps({'ok':True,'checks':checks,'new_model_calls':0}))
