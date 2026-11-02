import builtins
import dis
import unittest

from tikz_node_paint_export_contract_v4 import registration


class ExportReaderLinkageTests(unittest.TestCase):
    def test_all_export_reader_global_dependencies_are_linked(self):
        missing = sorted({instruction.argval for instruction in dis.get_instructions(registration)
                          if instruction.opname == 'LOAD_GLOBAL'
                          and instruction.argval not in registration.__globals__
                          and not hasattr(builtins, instruction.argval)})
        self.assertEqual(missing, [])


if __name__ == '__main__':
    unittest.main()
