import copy
import unittest

from tikz_node_paint_events_v2 import legacy_events, ownership, parse_events


def event(kind, *fields):
    return {'kind': kind, 'fields': list(fields)}


def trace():
    path = r'\pgfsyssoftpath@rectcornertoken{0pt}{2pt}\pgfsyssoftpath@rectsizetoken{10pt}{3pt}'
    return [event('header', '1', '3.1.11a'), event('picture', '1', 'begin'),
            event('nodepaint', '1', '1', '1', 'fillstroke', path, path),
            event('node', '1', '1', '1', 'label', '', 'rectangle', r'A {\bfseries B}', '2pt', '3pt', '2'),
            event('nodeowner', '1', '1', '1'), event('picture', '1', 'end'),
            event('ownershipcomplete', '1', '1'), event('complete', '1', '0', '1')]


def encode(events):
    return '\n'.join('\\IIC' + e['kind'] + ''.join('{' + field + '}' for field in e['fields'])
                     for e in events)


class NodePaintOwnershipTests(unittest.TestCase):
    def test_actual_driver_paint_bound_to_exact_source_serial(self):
        events = parse_events(encode(trace()))
        self.assertEqual(events, trace())
        result = ownership(events)
        self.assertTrue(result['complete'])
        self.assertEqual(result['by_node']['1:1'][0]['mode'], 'fillstroke')
        self.assertEqual(result['executed_nodes'], 1)
        self.assertEqual(result['driver_paints'], 1)
        self.assertEqual(len(legacy_events(events)), 5)

    def test_missing_owner_cannot_silently_drop_label_paint(self):
        events = [e for e in trace() if e['kind'] != 'nodeowner']
        with self.assertRaisesRegex(ValueError, 'cover every'):
            ownership(events)

    def test_unknown_driver_owner_rejected(self):
        events = trace()
        events[2]['fields'][1] = '2'
        with self.assertRaisesRegex(ValueError, 'no matching node'):
            ownership(events)

    def test_cross_picture_driver_owner_rejected(self):
        events = trace()
        events[2]['fields'][0] = '2'
        with self.assertRaisesRegex(ValueError, 'no matching node'):
            ownership(events)

    def test_missing_driver_event_rejected(self):
        events = [e for e in trace() if e['kind'] != 'nodepaint']
        with self.assertRaisesRegex(ValueError, 'sequence is incomplete'):
            ownership(events)

    def test_duplicate_source_node_rejected(self):
        events = trace()
        events.insert(4, copy.deepcopy(events[3]))
        with self.assertRaisesRegex(ValueError, 'Duplicate executed node'):
            ownership(events)

    def test_incomplete_or_unknown_trace_rejected(self):
        for bad in (encode(trace())[:-2], encode(trace()) + '\n\\IICunknown{1}'):
            with self.subTest(bad=bad[-25:]), self.assertRaises(ValueError):
                parse_events(bad)

    def test_corrupt_counter_rejected(self):
        events = trace()
        events[-2]['fields'][1] = '2'
        with self.assertRaisesRegex(ValueError, 'sequence is incomplete'):
            ownership(events)


if __name__ == '__main__':
    unittest.main()
