"""Source-bound IR admission, with no browsers, data or model invocation."""
import json
import unittest
import compiler_types_case_v1 as case


class Admission(unittest.TestCase):
    def job(self,fmt='html'):
        source=dict(pair_sha256='a'*64,format=fmt,code_sha256='b'*64,image_sha256='c'*64)
        native=dict(id='a'*64,source_pair_sha256='a'*64,source_format=fmt,format='drawio',
                    source_code_sha256='b'*64,source_image_sha256='c'*64,
                    code_file='clean/candidate.drawio',code_sha256='d'*64,
                    image_file='clean/candidate.png',image_sha256='e'*64)
        return dict(id='a'*64,format=fmt,category='scientific_diagram',input_record=json.dumps(source),output_record=json.dumps(native))

    def test_each_remaining_format_admits_only_source_bound_native_ir(self):
        for fmt in case.FORMATS:
            with self.subTest(format=fmt):
                self.assertTrue(case.static_support(self.job(fmt))['supported'])

    def test_active_python_scope_cannot_be_claimed_by_this_program(self):
        self.assertFalse(case.static_support(self.job('python'))['supported'])

    def test_no_candidate_is_explicitly_unsupported_not_a_success(self):
        job=self.job();job['output_record']=None
        self.assertIn('no_existing_native_ir',case.static_support(job)['reasons'])

    def test_source_or_pair_revision_drift_is_rejected(self):
        for field in ('id','source_pair_sha256','source_format','source_code_sha256','source_image_sha256'):
            job=self.job();native=json.loads(job['output_record']);native[field]='changed';job['output_record']=json.dumps(native)
            with self.subTest(field=field):self.assertFalse(case.static_support(job)['supported'])

    def test_ir_requires_actual_code_and_png_hash_descriptors(self):
        for field in ('code_file','code_sha256','image_file','image_sha256'):
            job=self.job();native=json.loads(job['output_record']);native.pop(field);job['output_record']=json.dumps(native)
            with self.subTest(field=field):self.assertFalse(case.static_support(job)['supported'])

    def test_web_and_other_categories_are_not_added(self):
        job=self.job();job['category']='web'
        self.assertFalse(case.static_support(job)['supported'])


if __name__=='__main__':unittest.main()
