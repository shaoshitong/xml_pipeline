import copy,math,os,unittest,xml.etree.ElementTree as E
import svg_native_triangle_marker_v1 as marker
import test_auto_quality_svg_closed_scene_v1 as fixtures

SOURCE='<defs><marker id="h" markerWidth="10" markerHeight="6" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 Z" fill="black" stroke="none"/></marker></defs><rect x="10" y="40" width="20" height="20" fill="white" stroke="black"/><rect x="90" y="40" width="20" height="20" fill="white" stroke="black"/><path d="M30,50 L90,50" stroke="black" fill="none" marker-end="url(#h)"/><text x="40" y="25">AB</text>'

@unittest.skipUnless(os.environ.get('IMG2CODE_SVG_SCENE_BROWSER_TESTS')=='1','Actual offline HKUST Chromium required')
class TriangleTests(unittest.TestCase):
    fixture=fixtures.BrowserTests.fixture
    check=fixtures.BrowserTests.check
    def case(self,source=SOURCE):
        root,record,dom,xml,stats=self.check(source);proof=marker.propose_from_scene(dom,xml);return dom,xml,proof
    def test_real_native_marker_replaces_floating_head_and_exact_source_replays(self):
        dom,xml,proof=self.case();self.assertTrue(proof['ok'],proof['failures']);self.assertTrue(proof['complete_source_marker_coverage']);self.assertEqual(len(proof['markers']),1);tree=E.fromstring(proof['candidate_xml']);cells={c.get('id'):c for c in tree.iter('mxCell')};row=proof['markers'][0];self.assertNotIn(row['source_head_object'],cells);self.assertEqual(marker.unpack(cells[row['edge']].get('style'))['endArrow'],'blockThin');self.assertTrue(marker.verify_candidate_from_scene(dom,xml,proof['candidate_xml'],proof)['ok'])
    def test_replay_rejects_wrong_marker_port_color_other_shape_text_and_proof(self):
        dom,xml,proof=self.case();self.assertTrue(proof['ok'],proof['failures'])
        for mode in ('marker','port','color','shape','text','wrong_head_proof'):
            tree=E.fromstring(proof['candidate_xml']);cells={c.get('id'):c for c in tree.iter('mxCell')};edge=cells[proof['markers'][0]['edge']];damaged=copy.deepcopy(proof)
            if mode in ('marker','port','color'):
                style=marker.unpack(edge.get('style'));style[{'marker':'endArrow','port':'entryX','color':'endFillColor'}[mode]]={'marker':'classic','port':'.9','color':'#ff0000'}[mode];edge.set('style',marker.pack(style))
            elif mode=='shape':cells['v1'].find('mxGeometry').set('x','11')
            elif mode=='text':next(c for c in cells.values() if c.get('value')).set('value','WRONG')
            else:damaged['consumed_source_head_ids']=[]
            changed=E.tostring(tree,encoding='unicode');damaged['candidate_code_sha256']=marker.sha(changed.encode())
            with self.assertRaises(marker.Unsupported,msg=mode):marker.verify_candidate_from_scene(dom,xml,changed,damaged)
    def test_marker_outside_source_viewport_cannot_be_replaced_by_unclipped_native_head(self):
        dom,xml,proof=self.case(SOURCE.replace('markerWidth="10"','markerWidth="5"'));self.assertFalse(proof['ok']);self.assertIn('source_marker_paint_exceeds_actual_marker_viewport',[f['reason'] for f in proof['failures']])
    def test_mid_marker_cannot_be_silently_lost_while_end_marker_is_repaired(self):
        dom,xml,proof=self.case(SOURCE.replace('M30,50 L90,50','M30,50 L60,50 L90,50').replace('marker-end="url(#h)"','marker-end="url(#h)" marker-mid="url(#h)"'));self.assertFalse(proof['ok']);self.assertIn('source_marker_mid_has_no_verified_native_endpoint_representation',[f['reason'] for f in proof['failures']])
    def test_wrong_direction_aspect_outline_curve_or_alpha_are_explicitly_unsupported(self):
        for source in (SOURCE.replace('L0,6 L9,3','L0,5 L9,3'),SOURCE.replace('fill="black" stroke="none"','fill="black" stroke="black"'),SOURCE.replace('M30,50 L90,50','M30,50 C50,50 70,50 90,50'),SOURCE.replace('fill="black" stroke="none"','fill="rgba(0,0,0,.5)" stroke="none"'),SOURCE.replace('orient="auto"','orient="180"')):
            dom,xml,proof=self.case(source);self.assertFalse(proof['ok'],source);self.assertTrue(proof['failures'])
    def test_marker_definition_and_source_ancestor_filter_are_not_silently_flattened(self):
        filter='<filter id="f"><feGaussianBlur stdDeviation="1"/></filter>'
        for source in (SOURCE.replace('<defs>','<defs>'+filter).replace('id="h"','id="h" filter="url(#f)"'),SOURCE.replace('<defs>','<defs>'+filter).replace('<rect x="10"','<g id="filtered" filter="url(#f)"><rect x="10"')+'</g>'):
            dom,xml,proof=self.case(source);self.assertFalse(proof['ok']);self.assertTrue(any('compositing' in f['reason'] or 'filter' in f['reason'] for f in proof['failures']),proof['failures'])
    def test_unbound_owner_missing_marker_or_fake_parent_does_not_pass(self):
        dom,xml,proof=self.case()
        for mode in ('unbound','missing','parent'):
            tree=E.fromstring(xml);cells={c.get('id'):c for c in tree.iter('mxCell')};row=proof['markers'][0]
            if mode=='unbound':cells[row['edge']].attrib.pop('target')
            elif mode=='missing':tree.find('.//root').remove(cells[row['source_head_object']])
            else:cells[row['source_head_object']].set('parent',row['edge'])
            rejected=marker.propose_from_scene(dom,E.tostring(tree,encoding='unicode'));self.assertFalse(rejected['ok'],mode)
    def test_ambiguous_source_outline_and_wrong_old_terminal_are_not_guessed(self):
        dom,xml,proof=self.case();broken=copy.deepcopy(dom);extra=copy.deepcopy(next(o for o in broken['objects'] if o['id']=='v2'));extra['id']='another_source_node';broken['objects'].append(extra)
        with self.assertRaises(marker.Unsupported):marker._terminal_binding('v2',proof['markers'][0]['source_geometry']['tip'],{o['id']:o for o in broken['objects']},{c.get('id'):c for c in E.fromstring(xml).iter('mxCell')},(0,0),(120,100))
        tree=E.fromstring(xml);next(c for c in tree.iter('mxCell') if c.get('edge')=='1').set('target','v1');self.assertFalse(marker.propose_from_scene(dom,E.tostring(tree,encoding='unicode'))['ok'])
    def test_two_ends_are_validated_against_same_input_revision(self):
        source=SOURCE.replace('orient="auto"','orient="auto-start-reverse"').replace('marker-end="url(#h)"','marker-start="url(#h)" marker-end="url(#h)"');dom,xml,proof=self.case(source);self.assertTrue(proof['ok'],proof['failures']);self.assertEqual(len(proof['markers']),2,proof['failures']);self.assertTrue(proof['complete_source_marker_coverage']);self.assertTrue(marker.verify_candidate_from_scene(dom,xml,proof['candidate_xml'],proof)['ok'])
    def test_rounded_and_ellipse_source_node_outline_has_bounded_true_geometry(self):
        for replacement in ('<rect x="90" y="40" width="20" height="20" rx="5" fill="white" stroke="black"/>','<circle cx="100" cy="50" r="10" fill="white" stroke="black"/>'):
            source=SOURCE.replace('<rect x="90" y="40" width="20" height="20" fill="white" stroke="black"/>',replacement);dom,xml,proof=self.case(source);self.assertTrue(proof['ok'],proof['failures']);self.assertTrue(proof['complete_source_marker_coverage']);self.assertLessEqual(proof['markers'][0]['source_outline_binding']['contour_Hausdorff_error_bound_px'],.02)
    def test_actual_upstream_native_marker_moves_rotates_and_restores(self):
        import svg_native_marker_edit_probe_v1 as probe
        dom,xml,proof=self.case();self.assertTrue(proof['ok'],proof['failures']);evidence=probe.audit(proof['candidate_xml'],proof['markers']);self.assertTrue(evidence['ok']);self.assertEqual(len(evidence['markers']),1)
        damaged=copy.deepcopy(proof['markers']);damaged[0]['source_geometry']['axis']=[-1,0]
        with self.assertRaisesRegex(ValueError,'tangent'):probe.audit(proof['candidate_xml'],damaged)

class OutlineGeometryTests(unittest.TestCase):
    def test_analytic_circle_is_within_the_claimed_curve_approximation_budget(self):
        obj={'id':'circle','tag':'circle','attrs':{'cx':0,'cy':0,'r':10},'matrix':[1,0,0,1,0,0]};points,bound=marker._outline(obj)
        maximum=max(min(marker._segment_distance((10*math.cos(t),10*math.sin(t)),a,b) for a,b in zip(points,points[1:]+points[:1])) for t in (i*math.pi/500 for i in range(1000)));self.assertLessEqual(maximum,bound);self.assertLessEqual(bound,.02)
    def test_self_intersection_collinear_overshoot_and_unbounded_arc_are_rejected(self):
        paths=['M0 0 L10 10 L0 10 L10 0 Z','M0 0 C100 0 -100 0 10 0 L10 10 L0 10 Z','M0 0 A10 10 0 0 1 20 0 L20 20 L0 20 Z']
        for d in paths:
            with self.assertRaises(marker.Unsupported,msg=d):marker._outline({'id':'bad','tag':'path','attrs':{},'d':d,'matrix':[1,0,0,1,0,0]})

if __name__=='__main__':unittest.main()
