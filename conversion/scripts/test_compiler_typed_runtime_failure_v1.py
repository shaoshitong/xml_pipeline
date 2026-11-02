import copy
import unittest
import compiler_typed_runtime_failure_v1 as runtime


class TypedRuntimeTests(unittest.TestCase):
    def test_false_flag_and_nested_false_data_do_not_trigger(self):
        for value in (dict(infrastructure_failure=False),dict(detail=dict(infrastructure_failure=False)),
                      dict(detail=[dict(infrastructure_failure=False)]),dict(error="{'infrastructure_failure': False}")):
            self.assertFalse(runtime.is_infrastructure(value))

    def test_ordinary_detail_is_not_a_typed_error_envelope(self):
        for detail in (dict(error_type='ImportError',infrastructure_failure=True),[dict(exception_type='TargetClosedError')],
                       'ImportError','ImportError: this is text in the original picture','infrastructure_failure: False',
                       'infrastructure_capture_error: a label in the picture'):
            self.assertFalse(runtime.is_infrastructure(dict(reason='source_text_mismatch',detail=detail)))

    def test_original_source_record_and_generic_type_are_not_diagnostics(self):
        self.assertFalse(runtime.is_infrastructure(dict(record=dict(error_type='ImportError',infrastructure_failure=True),source=dict(message='Browser crashed'),type='ImportError')))

    def test_real_import_exception_and_subclass_are_runtime_failures(self):
        class MissingRuntime(ImportError):pass
        for error in (ImportError('missing'),ModuleNotFoundError('missing'),MissingRuntime('missing')):
            self.assertTrue(runtime.is_infrastructure(exception=error));self.assertTrue(runtime.is_infrastructure(error))

    def test_top_level_typed_exception_fields_are_authoritative(self):
        for value in (dict(error_type='ImportError'),dict(exception_type='builtins.ModuleNotFoundError'),dict(exception_type='TargetClosedError')):
            self.assertTrue(runtime.is_infrastructure(value))

    def test_true_top_level_flag_is_positive_evidence(self):
        self.assertTrue(runtime.is_infrastructure(dict(infrastructure_failure=True)))
        for value in (False,0,'False','false',None):self.assertFalse(runtime.is_infrastructure(dict(infrastructure_failure=value)))

    def test_explicit_reason_prefix_is_distinct_from_a_false_field_name(self):
        self.assertTrue(runtime.is_infrastructure(dict(reason='infrastructure_capture_payload_changed: source_dot')))
        self.assertFalse(runtime.is_infrastructure(dict(reason='infrastructure_failure: False')))
        self.assertFalse(runtime.is_infrastructure(dict(reason='source_failure',message='source report contains infrastructure_failure=False')))

    def test_definite_browser_runtime_messages_are_recognized(self):
        for value in (dict(error='Page.captureScreenshot: Target page, context or browser has been closed'),
                      dict(message='Browser crashed'),dict(detail='Page.captureScreenshot: Unable to capture screenshot'),
                      dict(error="BrowserType.launch: Executable doesn't exist at /missing/chrome"),
                      dict(message='Connection closed while reading from the driver')):
            self.assertTrue(runtime.is_infrastructure(value))

    def test_runtime_words_inside_source_prose_are_not_runtime_errors(self):
        for field in ('reason','error','message','detail'):
            self.assertFalse(runtime.is_infrastructure({field:'Source text is "Browser crashed" or "ImportError"'}))

    def test_standard_failure_records_are_explicit_error_envelopes(self):
        self.assertTrue(runtime.is_infrastructure(dict(failures=[dict(exception_type='ImportError',message='missing runtime') ])))
        self.assertTrue(runtime.is_infrastructure(dict(failures=['ModuleNotFoundError: No module named runtime'])))
        self.assertFalse(runtime.is_infrastructure(dict(failures=[dict(type='text',detail=dict(error_type='ImportError',infrastructure_failure=True))])))

    def test_a_source_failure_with_false_keys_is_ordinary(self):
        for reason in ('source_reference_pending:source_reference_canvas_mismatch','source_reference_pending:invisible_or_unlaid_graphviz_node_not_supported'):
            self.assertFalse(runtime.is_infrastructure(dict(ok=False,reason=reason,infrastructure_failure=False,detail=dict(infrastructure_failure=False,exception_type='ValueError'))))

    def test_real_traceback_import_error_is_recognized(self):
        text='Traceback (most recent call last):\n  File "runtime.py", line 1\nModuleNotFoundError: No module named playwright'
        self.assertTrue(runtime.is_infrastructure(dict(error=text)))
        self.assertFalse(runtime.is_infrastructure(dict(message='Source label lines:\nImportError: this is a label')))

    def test_plain_string_payload_does_not_implicitly_become_an_error(self):
        self.assertFalse(runtime.is_infrastructure('ImportError: diagram label'))

    def test_exception_argument_requires_an_actual_exception(self):
        with self.assertRaises(TypeError):runtime.diagnose(exception='ImportError')

    def test_source_failures_do_not_mutate_input_metadata(self):
        value=dict(ok=False,reason='source_failure',detail=dict(infrastructure_failure=True,error_type='ImportError'),record=dict(text='ImportError'))
        before=copy.deepcopy(value);self.assertFalse(runtime.is_infrastructure(value));self.assertEqual(value,before)


if __name__=='__main__':unittest.main()
