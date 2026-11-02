"""Behavioral boundary fixtures; optional real upstream parse-only smoke."""
import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import tempfile
from unittest import mock

import asymptote_support as support


def run():
    count = 0
    def check(value, expected, name):
        nonlocal count
        assert value == expected, (name, value, expected)
        count += 1
    curve = 'import graph; size(200); real f(real x) {return sin(x);} draw(graph(f,-3,3)); xaxis("x"); yaxis("y");'
    check(support.is_asymptote(curve), True, 'typed_curve')
    check(support.is_asymptote('import graph; size(20); draw((0,0)--(1,1));'), True, 'native_path')
    check(support.is_asymptote('import graph; size(2cm); draw(unitcircle);'), True, 'native_unit')
    check(support.is_asymptote('from graph access xaxis,yaxis; real f(real x) {return x;}'), True, 'native_from_access')
    check(support.is_asymptote('import math; reality=1; print(reality);'), False, 'type_keyword_boundary')
    check(support.is_asymptote('import math; real = 1; print(real);'), False, 'ordinary_math_python')
    check(support.is_asymptote('import math;\ndef f(x):\n return x\n'), False, 'python_function')
    check(support.is_asymptote('import math; code="import graph; real f(real x) {return x;}";'), False, 'string_language_marker')
    check(support.is_asymptote('// import graph; real f(real x) {return x;}\nimport math; x=1;'), False, 'comment_language_marker')
    check(support.is_asymptote('from math import sin; real = 3;'), False, 'python_from_import')
    check(support.is_asymptote('import matplotlib.pyplot as plt\n# import graph; real x=1;\nplt.plot([0,1],[1,2])\n'), False, 'python_outer_import_and_hash_comment')
    check(support.is_asymptote('import math; # import graph; real x=1;\nprint(1)\n'), False, 'python_semicolon_and_hash_comment')
    check(support.is_asymptote('import math;\nsnippet="""import graph; real f(real x) {return x;} draw("x"); xaxis(); yaxis();"""\nprint(snippet)\n'), False, 'python_triple_quoted_asy')
    check(support.is_asymptote('import math;\n# real x=1;\nx=;\n'), False, 'broken_python_comment_not_asy')
    numpy_chart = 'import numpy as np; import matplotlib.pyplot as plt; x=np.arange(3); plt.plot(x,x); np.size(x); np.histogram(x);'
    check(support.is_asymptote(numpy_chart), False, 'numpy_qualified_names_not_asy')
    check(support.is_asymptote('import math; import numpy as np; np.size([1,2]); np.histogram([1,2]);'), False, 'python_math_with_numpy_names')
    check(support.visual_facts(numpy_chart)['chart'], False, 'numpy_histogram_not_native_evidence')
    check(support.visual_facts(curve)['chart'], True, 'curve_and_axes')
    check(support.visual_facts('import graph; real x=1; draw(unitcircle); xaxis(); yaxis();')['chart'], False, 'geometry_axes_not_chart')
    check(support.visual_facts('import graph; real x=1; draw(graph(x));')['chart'], False, 'graph_without_axes_not_chart')
    check(support.visual_facts('import graph; real x=1; label("draw(graph(x)); xaxis(); yaxis();",(0,0));')['chart'], False, 'quoted_visual_terms')
    check(support.visual_facts('import graph; real x=1; // draw(graph(x)); xaxis(); yaxis();')['chart'], False, 'comment_visual_terms')
    check(support.visual_facts('import stats; real[] a={1,2,3}; histogram(a);')['chart'], True, 'native_histogram')
    check(support.visual_facts('import graph; real graph(real x) {return x;} draw(graph(1)); xaxis(); yaxis();')['chart'], False, 'overridden_graph')
    check(support.visual_facts('import graph; real histogram(real x) {return x;} histogram(2);')['chart'], False, 'overridden_histogram')
    check(support.visual_facts('import graph; real x=1; obj.graph(x); draw(x); xaxis(); yaxis();')['chart'], False, 'unrelated_graph_method')
    check(support.visual_facts('import graph as g; real x=1; draw(g.graph(x)); g.xaxis(); g.yaxis();')['chart'], True, 'native_module_alias')
    check(support.visual_facts(curve + 'label("(",(0,0));')['chart'], True, 'literal_parenthesis')
    check(support.visual_facts('import graph; real x=1; /* unterminated')['chart'], False, 'unterminated_comment')
    pie = '''import graph;
size(150);
real[] data={2,3,5};
pen[] colors={red,blue,green};
string[] labels={"A","B","C"};
real sum=0;
for(real x:data) sum+=x;
real angle=0;
for(int i=0;i<data.length;++i) {
  real fraction=data[i]/sum;
  fill(arc((0,0),1,degrees(angle),degrees(angle+2pi*fraction))--(0,0)--cycle,colors[i]);
  label(labels[i],1.2*dir(angle+pi*fraction));
  angle+=2pi*fraction;
}
'''
    check(support.visual_facts(pie)['chart'], True, 'data_normalized_multisector_pie')
    check(support.visual_facts(pie)['pie_data_evidence']['data_items'], 3, 'pie_data_cardinality')
    renamed_pie = pie.replace('data','weights').replace('sum','total').replace('fraction','share').replace('angle','start')
    check(support.visual_facts(renamed_pie)['chart'], True, 'pie_does_not_memorize_variable_names')
    check(support.visual_facts(pie.replace('  label(labels[i],1.2*dir(angle+pi*fraction));',''))['chart'], True, 'pie_indexed_colors_without_labels')
    check(support.visual_facts(pie.replace('colors[i]', 'black'))['chart'], True, 'pie_indexed_labels_without_color_variation')
    check(support.visual_facts('import graph; real radius=1; filldraw(scale(radius)*unitcircle,red);')['chart'], False, 'ordinary_filled_circle')
    check(support.visual_facts('import graph; real radius=1; filldraw(arc((0,0),radius,0,90)--(0,0)--cycle,red);')['chart'], False, 'ordinary_geometric_sector')
    check(support.visual_facts(pie.replace('data[i]/sum', '0.1'))['chart'], False, 'sectors_without_data_normalization')
    check(support.visual_facts(pie.replace('real fraction=data[i]/sum;', 'real fraction=data[i]/sum; fraction=0.1;'))['chart'], False, 'normalized_fraction_then_overwritten')
    check(support.visual_facts(pie.replace('for(real x:data) sum+=x;', 'for(real x:data) sum+=x; sum=1;'))['chart'], False, 'data_sum_then_overwritten')
    check(support.visual_facts(pie.replace('degrees(angle)', 'angle').replace('degrees(angle+2pi*fraction)', 'angle+2pi*fraction'))['chart'], False, 'radian_values_passed_as_degree_arc')
    degree_pie = pie.replace('degrees(angle)', 'angle').replace('degrees(angle+2pi*fraction)', 'angle+360*fraction').replace('angle+=2pi*fraction;', 'angle+=360*fraction;')
    check(support.visual_facts(degree_pie)['chart'], True, 'correct_direct_360_degree_arc')
    for order in itertools.permutations(('2', 'pi', 'fraction')):
        product = '*'.join(order)
        check(support.visual_facts(pie.replace('2pi*fraction', product))['chart'], True, 'pie_scalar_factor_order_' + '_'.join(order))
    check(support.visual_facts(pie.replace('2pi*fraction','fraction*2pi'))['chart'], True, 'actual_coefficient_order_fraction_times_2pi')
    check(support.visual_facts(pie.replace('2pi*fraction','fraction*2*pi*0.5'))['chart'], False, 'extra_scalar_factor_is_not_full_turn')
    check(support.visual_facts(pie.replace('2pi*fraction','fraction*2*pi+0.1'))['chart'], False, 'extra_angle_offset_is_not_slice')
    check(support.visual_facts(pie.replace('2pi*fraction','fraction*2*pi/2'))['chart'], False, 'extra_division_is_not_full_turn')
    check(support.visual_facts(pie.replace('angle+=2pi*fraction;', 'real other=2pi*fraction;'))['chart'], False, 'repeated_overlapping_sector_not_full_pie')
    check(support.visual_facts(pie.replace('{2,3,5}', '{0,0,0}'))['chart'], False, 'pie_without_positive_data')
    check(support.visual_facts(pie.replace('pen[] colors={red,blue,green};', 'pen[] colors={red,red,red};').replace('  label(labels[i],1.2*dir(angle+pi*fraction));',''))['chart'], False, 'one_color_unlabelled_circle_not_proof')
    check(support.visual_facts('import graph; real radius=1; label('+json.dumps(pie)+',(0,0));')['chart'], False, 'pie_calls_only_inside_label')
    check(support.visual_facts('import graph; real radius=1; /*'+pie+'*/ filldraw(unitcircle,red);')['chart'], False, 'pie_calls_only_inside_comment')
    check(support.visual_facts('import graph; real[] x={1,2,3}; real[] y={2,4,8}; dot(x,y); xaxis(); yaxis();')['chart'], False, 'dot_arrays_still_need_separate_visual_evidence')
    with tempfile.TemporaryDirectory(prefix='asy-boundary-', dir=Path(__file__).parent) as directory:
        raw = Path(directory)
        (raw / 'data.csv').write_text('1,2\n3,4\n')
        (raw / 'figure.svg').write_text('<svg/>')
        (raw / 'valid chart data.csv').write_text('1,2\n3,4\n')
        modules = frozenset({'graph', 'graph3', 'geometry', 'stats', 'plain', 'settings'})
        with mock.patch.object(support, '_builtin_modules', return_value=modules):
            def dep(code): return support.dependency_issue(code, raw)
            check(dep(curve), None, 'standard_library')
            check(dep('from graph access xaxis,yaxis; real x=1;'), None, 'standard_from_access')
            check(dep('import graph as g; real x=1;'), None, 'standard_alias')
            check(dep('include graph; real x=1;'), None, 'standard_bare_include')
            check(dep('import custom_module; real x=1;'), 'nonstandard_asymptote_module_dependency', 'custom_import')
            check(dep('import "https://example.org/code.asy"; real x=1;'), 'external_asymptote_module_dependency', 'remote_import')
            check(dep('include "custom.asy"; real x=1;'), 'nonstandard_asymptote_module_dependency', 'custom_include')
            check(dep('import graph; real x=1; label("input read eval include custom;",(0,0));'), None, 'words_in_label')
            check(dep('import graph; // input("missing"); eval("...");\nreal x=1;'), None, 'words_in_comment')
            check(dep('import graph; file data=input("data.csv");'), None, 'existing_file')
            check(dep('import graph; file data=input("' + 'x' * 310 + '.csv");'), 'unresolved_asymptote_input_dependency', 'overlong_314_character_filename')
            check(dep('import graph; file data=input("valid chart data.csv");'), None, 'existing_asset_with_spaces_control')
            check(dep('import graph; file data=input("missing.csv");'), 'missing_local_asymptote_input_dependency', 'missing_file')
            check(dep('import graph; file data=input("https://example.org/data.csv");'), 'external_asymptote_input_dependency', 'external_file')
            check(dep('import graph; file data=input(filename);'), 'unresolved_asymptote_input_dependency', 'symbolic_file')
            check(dep('import graph; input custom;'), 'unresolved_asymptote_input_dependency', 'input_statement')
            check(dep('import graph; graphic("figure.svg");'), None, 'existing_native_graphic')
            check(dep('import graph; graphic("figure.svg"+suffix);'), 'unresolved_asymptote_input_dependency', 'dynamic_graphic')
            check(dep('import graph; eval("real x=1;");'), 'dynamic_asymptote_code_or_resource_dependency', 'dynamic_eval')
            check(dep('import graph; system("command");'), 'dynamic_asymptote_code_or_resource_dependency', 'external_command')
            check(dep('from plain access input as getfile; file f=getfile("missing.csv");'), 'aliased_asymptote_input_or_dynamic_dependency', 'aliased_native_input')
            check(dep('from plain access system as launch; launch("command");'), 'aliased_asymptote_input_or_dynamic_dependency', 'aliased_native_system')
            check(dep('from plain access graphic as image; image("missing.png");'), 'aliased_asymptote_input_or_dynamic_dependency', 'aliased_native_graphic')
            check(dep('import graph; real x=getreal("x");'), 'interactive_asymptote_input_dependency', 'interactive_data')
            check(dep(r'import graph; label("\\input{missing.tex}",(0,0));'), 'missing_local_asymptote_input_dependency', 'tex_input')
            check(dep(r'import graph; label("\\includegraphics{figure.svg}",(0,0));'), None, 'tex_existing_figure')
            check(dep(r'import graph; label("\\input{\\variable}",(0,0));'), 'unresolved_asymptote_tex_dependency', 'symbolic_tex_input')
            check(dep(r'import graph; label("\\directlua{...}",(0,0));'), 'unresolved_asymptote_tex_dependency', 'tex_dynamic_input')
            check(dep(r'import graph; label("\\in"+"put{missing.tex}",(0,0));'), 'missing_local_asymptote_input_dependency', 'tex_literal_concat')
            check(dep(r'import graph; label(("\\in")+("put{missing.tex}"),(0,0));'), 'missing_local_asymptote_input_dependency', 'tex_parenthesized_literal_concat')
            check(dep(r'import graph; label("\\include"+"graphics{figure.svg}",(0,0));'), None, 'tex_existing_literal_concat')
            check(dep(r'import graph; label("\\in",(0,0)); label("put{missing.tex}",(0,0));'), None, 'separate_tex_strings_not_joined')
            check(support.dependency_issue('import graph; input("mapped.csv");', raw, {'mapped.csv': raw / 'data.csv'}), None, 'proven_mapped_asset')
        check(support.syntax_issue(curve, task_root=raw), 'asymptote_parser_unavailable', 'missing_parser_fails_closed')
        fake = raw / 'runtime/asymptote-2.85'
        for folder in ('root/usr/bin', 'root/usr/share/asymptote', 'root/usr/lib/x86_64-linux-gnu'):
            (fake / folder).mkdir(parents=True, exist_ok=True)
        (fake / 'root/usr/bin/asy').write_text('not a trusted binary')
        (fake / 'empty_config.asy').write_text('nonempty configuration')
        support._parse.cache_clear()
        check(support.syntax_issue(curve, task_root=raw), 'asymptote_parser_integrity_mismatch', 'wrong_runtime_fails_closed')
    check(support.syntax_issue('real x="\ud800";'), 'invalid_asymptote_source_encoding', 'bad_encoding')
    return count


def native_smoke(root):
    runtime = Path(root) / 'runtime/asymptote-2.85'
    sentinel = runtime / 'asymptote_support_parse_sentinel.txt'
    assert not sentinel.exists()
    examples = [('valid_graph', 'import graph; real f(real x) {return sin(x);} draw(graph(f,-1,1));', True),
                ('invalid_syntax', 'real x=;', False),
                ('unresolved_import_not_executed', 'import absent_asymptote_fixture_module;', True),
                ('write_not_executed', 'file f=output("asymptote_support_parse_sentinel.txt"); write(f,"executed");', True)]
    result = []
    for name, code, expected in examples:
        facts = support.syntax_facts(code, task_root=root)
        assert (facts['issue'] is None) == expected, (name, facts)
        result.append({'name': name, **facts})
    assert not sentinel.exists(), 'parseonly executed a dataset-like fixture'
    return {'cases': result, 'sentinel_created': False, 'parser_sha256': hashlib.sha256((runtime / 'root/usr/bin/asy').read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--runtime-root', type=Path)
    parser.add_argument('--support', type=Path); args = parser.parse_args()
    if args.support:
        spec = importlib.util.spec_from_file_location('fixture_asy_support_candidate', args.support)
        support = importlib.util.module_from_spec(spec); spec.loader.exec_module(support)
    out = {'boundary_checks_passed': run()}
    if args.runtime_root: out['native_smoke'] = native_smoke(args.runtime_root)
    print(json.dumps(out, ensure_ascii=False))
