import unittest

from compiler_native_text_node_cdp_v2 import physical_fonts


class Session:
    def __init__(self, *, child=None, pushed=None, actual=None, final=None):
        self.child = child or {'nodeType': 3, 'nodeValue': 'A\u0301 שלום',
                               'nodeId': 0, 'backendNodeId': 72}
        self.pushed = [91] if pushed is None else pushed
        self.actual = dict(self.child, nodeId=91) if actual is None else actual
        self.final = final
        self.calls = []
        self.descriptions = 0
        self.fonts = [{'postScriptName': 'ArialMT', 'glyphCount': 6, 'isCustomFont': False},
                      {'postScriptName': 'NotoSansHebrew-Regular', 'glyphCount': 4,
                       'isCustomFont': False}]

    def send(self, method, params):
        self.calls.append((method, params))
        if method == 'DOM.describeNode':
            if params['nodeId'] == 30:
                self.descriptions += 1
                node = self.final if self.descriptions > 1 and self.final is not None else self.child
                return {'node': {'nodeId': 30, 'children': [node]}}
            return {'node': self.actual}
        if method == 'DOM.pushNodesByBackendIdsToFrontend':
            return {'nodeIds': self.pushed}
        if method == 'CSS.getPlatformFontsForNode':
            if params['nodeId'] != 91:
                raise RuntimeError('invalid_frontend')
            return {'fonts': self.fonts}
        raise AssertionError(method)


class TextNodeFontTests(unittest.TestCase):
    def run_fonts(self, session):
        return physical_fonts(session, 30, 0, 'A\u0301 שלום')

    def test_zero_frontend_id_materialized_and_fallback_inventory_retained(self):
        session = Session()
        self.assertEqual(self.run_fonts(session), session.fonts)
        self.assertIn(('DOM.pushNodesByBackendIdsToFrontend', {'backendNodeIds': [72]}), session.calls)
        self.assertEqual([params['nodeId'] for name, params in session.calls
                          if name == 'CSS.getPlatformFontsForNode'], [91])

    def test_existing_frontend_is_still_bound_to_backend(self):
        self.assertEqual(len(self.run_fonts(Session(child={'nodeType': 3, 'nodeValue': 'A\u0301 שלום',
                                                         'nodeId': 68, 'backendNodeId': 72}))), 2)

    def test_changed_text_rejected_before_font_query(self):
        session = Session(child={'nodeType': 3, 'nodeValue': 'other', 'backendNodeId': 72})
        with self.assertRaisesRegex(ValueError, 'binding_changed'):
            self.run_fonts(session)
        self.assertFalse(any(name == 'CSS.getPlatformFontsForNode' for name, _ in session.calls))

    def test_element_cannot_replace_text_node(self):
        with self.assertRaisesRegex(ValueError, 'binding_changed'):
            self.run_fonts(Session(child={'nodeType': 1, 'nodeValue': 'A\u0301 שלום', 'backendNodeId': 72}))

    def test_wrong_backend_rejected(self):
        with self.assertRaisesRegex(ValueError, 'materialized_identity_changed'):
            self.run_fonts(Session(actual={'nodeType': 3, 'nodeValue': 'A\u0301 שלום', 'backendNodeId': 73}))

    def test_late_parent_membership_change_rejected(self):
        with self.assertRaisesRegex(ValueError, 'parent_membership_changed'):
            self.run_fonts(Session(final={'nodeType': 3, 'nodeValue': 'A\u0301 שלום', 'backendNodeId': 73}))

    def test_unmaterialized_backend_rejected(self):
        for pushed in ([], [0], [True], [91, 92]):
            with self.subTest(pushed=pushed), self.assertRaisesRegex(ValueError, 'not_materialized'):
                self.run_fonts(Session(pushed=pushed))

    def test_missing_parent_rejected(self):
        with self.assertRaisesRegex(ValueError, 'parent_missing'):
            physical_fonts(Session(), 0, 0, 'A\u0301 שלום')

    def test_changed_child_position_rejected(self):
        with self.assertRaisesRegex(ValueError, 'child_index_changed'):
            physical_fonts(Session(), 30, 1, 'A\u0301 שלום')


if __name__ == '__main__':
    unittest.main()
