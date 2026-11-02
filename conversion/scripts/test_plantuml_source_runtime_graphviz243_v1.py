import unittest

import plantuml_source_runtime_graphviz243_v1 as runtime


class NativeSourceProvenanceTests(unittest.TestCase):
    def test_native_source_and_original_gold_match_without_rewriting_bytes(self):
        code = b'@startuml\r\ncomponent A\r\n@enduml\r\n'
        metadata = '@startuml\ncomponent A\n@enduml\n\nPlantUML version 1.2025.7(original)\n'
        report = runtime.native_png_provenance(metadata, code, runtime.PROVIDER)
        self.assertTrue(report['metadata_source_matches_original_code'])
        self.assertTrue(report['provider_in_profile'])
        self.assertEqual(report['metadata_PlantUML_version'], '1.2025.7(original)')
        self.assertEqual(code, b'@startuml\r\ncomponent A\r\n@enduml\r\n')

    def test_expanded_or_different_source_is_reported_without_calling_it_irrecoverable(self):
        report = runtime.native_png_provenance(
            '@startuml\ncomponent B\n@enduml\n\nPlantUML version 1.2025.7\n',
            '@startuml\ncomponent A\n@enduml', runtime.PROVIDER)
        self.assertFalse(report['metadata_source_matches_original_code'])
        self.assertTrue(report['provenance_is_not_quality_acceptance'])
        self.assertNotIn('irrecoverable', report)

    def test_missing_metadata_does_not_invent_a_version_or_correspondence(self):
        report = runtime.native_png_provenance('', '@startuml\n@enduml', 'other')
        self.assertFalse(report['provider_in_profile'])
        self.assertIsNone(report['metadata_source_matches_original_code'])
        self.assertIsNone(report['metadata_PlantUML_version'])

    def test_java_environment_does_not_receive_private_library_overrides(self):
        env = runtime.environment()
        self.assertEqual(env['GRAPHVIZ_DOT'], str(runtime.DOT))
        self.assertNotIn('LD_LIBRARY_PATH', env)
        self.assertNotIn('GVBINDIR', env)


if __name__ == '__main__':
    unittest.main()
