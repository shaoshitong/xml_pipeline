import math,unittest
from svg_native_bezier_ir_v1 import compile_path


def cubic(p,t):
    return [sum(weight*q[axis]for weight,q in zip(((1-t)**3,3*t*(1-t)**2,3*t*t*(1-t),t**3),p))for axis in(0,1)]


class NativeBezierIRTests(unittest.TestCase):
    def check_cubic(self,source,expected,matrix=(1,0,0,1,0,0)):
        ir=compile_path(source,matrix);self.assertEqual(ir['mode'],'native_cubic_bezier')
        points=ir['points'];intervals=ir['subdivisions'][0]['source_parameter_intervals']
        for i,(start,end) in enumerate(intervals):
            for t in (0,.13,.5,.83,1):
                actual=cubic(points[3*i:3*i+4],t);wanted=cubic(expected,start+(end-start)*t)
                self.assertLess(math.dist(actual,wanted),1e-9)
        self.assertTrue(ir['native_waypoint_filter_invariant'])
        self.assertTrue(all(max(abs(p[0]-q[0]),abs(p[1]-q[1]))>=1 for p,q in zip(points,points[1:])))
        return ir

    def test_cubic_is_preserved_over_all_native_segments(self):
        self.check_cubic('M0 0 C0 100 100 100 100 0',[(0,0),(0,100),(100,100),(100,0)])

    def test_quadratic_degree_elevation_is_exact(self):
        self.check_cubic('M0 0 Q90 90 180 0',[(0,0),(60,60),(120,60),(180,0)])

    def test_affine_transform_is_applied_to_controls(self):
        self.check_cubic('M0 0 C0 10 10 10 10 0',[(30,40),(60,80),(80,90),(50,50)],(2,1,3,4,30,40))

    def test_multiple_curve_and_line_commands_stay_in_order(self):
        ir=compile_path('M0 0 L10 0 Q20 0 20 10 C20 20 30 20 30 10')
        self.assertEqual(len(ir['subdivisions']),3);self.assertEqual(ir['points'][0],[0,0]);self.assertEqual(ir['points'][-1],[30,10])

    def test_native_terminal_control_preserves_analytic_tangent(self):
        ir=compile_path('M0 0 C0 100 100 100 100 0');first,next_=ir['points'][:2];previous,last=ir['points'][-2:]
        self.assertAlmostEqual(first[0],next_[0]);self.assertGreater(next_[1],first[1]);self.assertAlmostEqual(previous[0],last[0]);self.assertLess(last[1],previous[1])

    def test_degenerate_endpoint_derivative_remains_exact(self):
        with self.assertRaisesRegex(ValueError,'control_filter_would_change'):
            compile_path('M0 0 C0 0 10 10 10 10')

    def test_straight_owners_keep_original_polyline_route(self):
        self.assertEqual(compile_path('M0 0 L10 10 L20 10')['mode'],'source_sampled_polyline')

    def test_arc_route_does_not_claim_exact_cubic_equivalence(self):
        self.assertEqual(compile_path('M10 0 A10 10 0 0 1 0 10')['mode'],'source_sampled_polyline')

    def test_capped_complexity_is_explicit_pending(self):
        with self.assertRaisesRegex(ValueError,'resource_bound'):compile_path('M0 0 C0 100 100 100 100 0',maximum_points=10)

    def test_closed_or_disconnected_path_rejected(self):
        for path in ('M0 0 Q10 0 10 10 Z','M0 0 Q10 0 10 10 M20 20 L30 30'):
            with self.assertRaises(ValueError):compile_path(path)

    def test_nonfinite_configuration_rejected(self):
        with self.assertRaises(ValueError):compile_path('M0 0 Q1 1 2 0',maximum_span=math.inf)


if __name__=='__main__':unittest.main()
