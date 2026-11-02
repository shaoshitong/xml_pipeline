import math,unittest
from svg_source_endpoint_direction_v1 import directions,marker_angle


class EndpointDirectionTests(unittest.TestCase):
    def assertVector(self,actual,expected):
        for a,b in zip(actual,expected):self.assertAlmostEqual(a,b,places=12)

    def test_cubic_uses_control_not_chord(self):
        p=directions('M0 0 C0 100 100 100 100 0')
        self.assertVector(p['start']['forward_local'],[0,1]);self.assertVector(p['end']['forward_local'],[0,-1])

    def test_quadratic_endpoint_controls(self):
        p=directions('M0 0 Q100 0 100 100');self.assertVector(p['start']['forward_local'],[1,0]);self.assertVector(p['end']['forward_local'],[0,1])

    def test_degenerate_controls_use_higher_derivative(self):
        p=directions('M0 0 C0 0 0 10 10 10')
        self.assertVector(p['start']['forward_local'],[0,1]);self.assertVector(p['end']['forward_local'],[1,0])

    def test_zero_final_derivative_uses_next_control(self):
        p=directions('M0 0 C0 10 10 10 10 10');self.assertVector(p['end']['forward_local'],[1,0])

    def test_zero_length_prefix_and_suffix_search_neighbors(self):
        p=directions('M0 0 L0 0 Q10 0 10 10 L10 10')
        self.assertVector(p['start']['forward_local'],[1,0]);self.assertVector(p['end']['forward_local'],[0,1])

    def test_entire_zero_path_uses_positive_local_x(self):
        p=directions('M2 3 L2 3 C2 3 2 3 2 3')
        self.assertVector(p['start']['forward_local'],[1,0]);self.assertVector(p['end']['forward_local'],[1,0])

    def test_smooth_relative_commands_expand_exactly(self):
        p=directions('m0 0 c0 5 5 5 5 0 s5 -5 5 0')
        self.assertVector(p['end']['forward_local'],[0,1]);self.assertVector(p['end']['point_local'],[10,0])

    def test_arc_tangent_and_zero_radius_line(self):
        p=directions('M10 0 A10 10 0 0 1 0 10')
        self.assertVector(p['start']['forward_local'],[0,1]);self.assertVector(p['end']['forward_local'],[-1,0])
        q=directions('M0 0 A0 5 0 0 1 10 0');self.assertVector(q['end']['forward_local'],[1,0])

    def test_rotation_and_translation(self):
        p=directions('M0 0 L10 0',[0,1,-1,0,20,30]);self.assertVector(p['end']['forward_screen'],[0,1]);self.assertVector(p['end']['point_screen'],[20,40])

    def test_nonuniform_shear_transforms_derivative_as_vector(self):
        p=directions('M0 0 Q1 1 3 1',[2,1,3,4,99,101]);length=math.hypot(5,5)
        self.assertVector(p['start']['forward_screen'],[5/length,5/length]);self.assertVector(p['end']['forward_screen'],[2/math.sqrt(5),1/math.sqrt(5)])

    def test_reflection(self):
        p=directions('M0 0 L10 0',[-1,0,0,1,0,0]);self.assertVector(p['end']['forward_screen'],[-1,0])

    def test_auto_start_and_auto_start_reverse_are_distinct(self):
        p=directions('M0 0 L10 0');self.assertEqual(marker_angle(p,'start','auto'),0);self.assertEqual(marker_angle(p,'start','auto-start-reverse'),180);self.assertEqual(marker_angle(p,'end','auto-start-reverse'),0)

    def test_closed_and_multiple_subpaths_remain_explicit(self):
        for code,reason in [('M0 0 L10 0 Z','closed_owner'),('M0 0 L1 1 M2 2 L3 3','multiple_subpaths')]:
            with self.assertRaisesRegex(ValueError,reason):directions(code)

    def test_nonfinite_or_singular_transform_rejected(self):
        for matrix in ([0,0,0,0,0,0],[math.nan,0,0,1,0,0]):
            with self.assertRaises(ValueError):directions('M0 0 L1 1',matrix)

    def test_move_only_is_not_drawn_segment(self):
        with self.assertRaisesRegex(ValueError,'empty_owner'):directions('M0 0')

    def test_reversing_source_reverses_endpoint_directions(self):
        forward=directions('M0 0 C0 10 10 10 10 0');reverse=directions('M10 0 C10 10 0 10 0 0')
        self.assertVector(reverse['start']['forward_local'],[-x for x in forward['end']['forward_local']])


if __name__=='__main__':unittest.main()
