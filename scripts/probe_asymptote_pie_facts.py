"""Read only code/metadata for the two visually reviewed Asy rows; no images."""
import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import re


def brackets(tokens, start, opening='(', closing=')'):
    depth = 0
    for index in range(start, len(tokens)):
        token = tokens[index]
        if token.kind != 'symbol': continue
        if token.value == opening: depth += 1
        elif token.value == closing:
            depth -= 1
            if depth == 0: return index
    return None


def arguments(tokens, start):
    end = brackets(tokens, start)
    if end is None: return [], None
    result = []; begin = start + 1; depth = 0
    for index in range(begin, end):
        token = tokens[index]
        if token.kind != 'symbol': continue
        if token.value in {'(', '[', '{'}: depth += 1
        elif token.value in {')', ']', '}'}: depth -= 1
        elif token.value == ',' and depth == 0:
            result.append(tokens[begin:index]); begin = index + 1
    if begin < end: result.append(tokens[begin:end])
    return result, end


def expression_facts(tokens, support):
    calls, _ = support._calls(tokens)
    strings = [token.value for token in tokens if token.kind == 'string']
    return {'token_count': len(tokens),
            'identifier_names': sorted({token.value for token in tokens if token.kind == 'id'})[:24],
            'numeric_literals': [token.value for token in tokens if token.kind == 'number'][:24],
            'call_counts': dict(collections.Counter(name for name, _ in calls)),
            'symbol_counts': dict(collections.Counter(token.value for token in tokens if token.kind == 'symbol')),
            'string_count': len(strings),
            'strings_with_numeric_percent': sum(bool(re.search(r'\d\s*\\?%', value)) for value in strings),
            'strings_with_percent_marker': sum('%' in value for value in strings),
            'strings_with_escaped_percent': sum(r'\%' in value or '%%' in value for value in strings),
            'strings_with_number_format_marker': sum(bool(re.search(r'%[-+0-9.#]*[fgdieE]', value)) for value in strings)}


def facts(code, support):
    tokens, _, error = support._lex(code); calls, _ = support._calls(tokens)
    call_counts = collections.Counter(name for name, _ in calls)
    targets = []
    for name, index in calls:
        if name not in {'arc', 'sector', 'fill', 'filldraw', 'draw', 'label', 'dot', 'format'}: continue
        args, _ = arguments(tokens, index + 1)
        targets.append({'function': name, 'line': code[:tokens[index].start].count('\n') + 1,
                        'argument_count': len(args),
                        'arguments': [expression_facts(arg, support) for arg in args]})
    declarations = []
    for index, token in enumerate(tokens):
        if token.kind != 'id' or token.value not in {'real', 'path', 'pair', 'pen', 'int', 'string', 'guide'}: continue
        j = index + 1; dimensions = 0
        while j + 1 < len(tokens) and tokens[j].value == '[' and tokens[j + 1].value == ']':
            dimensions += 1; j += 2
        if j + 1 >= len(tokens) or tokens[j].kind != 'id' or tokens[j + 1].value != '=': continue
        begin = j + 2; end = begin; depth = 0
        while end < len(tokens):
            current = tokens[end]
            if current.kind == 'symbol':
                if current.value in {'(', '[', '{'}: depth += 1
                elif current.value in {')', ']', '}'}:
                    if depth == 0: break
                    depth -= 1
                elif current.value == ';' and depth == 0: break
            end += 1
        declarations.append({'type': token.value, 'name': tokens[j].value, 'array_dimensions': dimensions,
                             'initializer': expression_facts(tokens[begin:end], support)})
    loops = []
    for index, token in enumerate(tokens[:-1]):
        if token.kind != 'id' or token.value not in {'for', 'while'} or tokens[index + 1].value != '(': continue
        end = brackets(tokens, index + 1)
        if end is None: continue
        body = []; body_end = None
        if end + 1 < len(tokens) and tokens[end + 1].value == '{':
            body_end = brackets(tokens, end + 1, '{', '}')
            if body_end is not None: body = tokens[end + 2:body_end]
        loops.append({'kind': token.value, 'header': expression_facts(tokens[index + 2:end], support),
                      'body': expression_facts(body, support), 'braced_body': body_end is not None})
    return {'lexical_error': error, 'current_visual_facts': support.visual_facts(code),
            'call_counts': dict(call_counts), 'cycle_token_count': sum(token.kind == 'id' and token.value == 'cycle' for token in tokens),
            'drawing_call_facts': targets[:40], 'typed_declaration_facts': declarations[:24], 'loop_facts': loops[:12],
            'string_summary': expression_facts([token for token in tokens if token.kind == 'string'], support)}


def main(args):
    import pyarrow.parquet as pq
    root = args.root.resolve(); module_path = args.support or root / 'scripts/asymptote_support.py'
    spec = importlib.util.spec_from_file_location('pie_facts_asy_support', module_path)
    support = importlib.util.module_from_spec(spec); spec.loader.exec_module(support)
    source = root / 'raw/allenai--CoSyn-400K/graphic/train-00000-of-00001.parquet'
    pf = pq.ParquetFile(source); requested = {0, 36}; offset = 0; results = []
    columns = [name for name in ('code', 'metadata') if name in pf.schema_arrow.names]
    for group in range(pf.num_row_groups):
        length = pf.metadata.row_group(group).num_rows
        selected = sorted(row for row in requested if offset <= row < offset + length)
        if selected:
            rows = pf.read_row_group(group, columns=columns).to_pylist()
            for index in selected:
                row = rows[index - offset]; code = row.get('code'); assert isinstance(code, str)
                digest = hashlib.sha256(code.encode()).hexdigest()
                if index == 0: assert digest == '737040eaa4affa71f3f6ed8eff0089f00b7fd44dcee6cb9e80a94e2bacf6c8f2'
                metadata = row.get('metadata') or {}
                results.append({'file': str(source.relative_to(root)), 'row': index, 'code_sha256': digest,
                                'code_chars': len(code), 'figure_type': metadata.get('figure_type') if isinstance(metadata, dict) else None,
                                **facts(code, support)})
                requested.remove(index)
        offset += length
        if not requested: break
    print(json.dumps({'read_only': True, 'read_columns': columns, 'image_column_read': False,
                      'scope': 'Exact code token metadata for visually reviewed rows; no source excerpts, image reads, execution, render or writes.',
                      'support_sha256': hashlib.sha256(module_path.read_bytes()).hexdigest(), 'rows': results}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--support', type=Path); main(parser.parse_args())
