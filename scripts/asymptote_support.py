"""Conservative Asymptote language, chart and dependency checks.

Syntax uses a pinned task-private upstream parser in parseonly mode. It neither
runs a dataset program nor establishes that its supplied image matches its code.
The lexer below supplies evidence/asset checks, not a replacement Asy grammar.
"""
import ast
import collections
import functools
import hashlib
import io
import itertools
import math
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import tokenize

BINARY_SHA256 = 'b8f4d9637eded8ad4e40bcd3c287776af94375aee5bf004c1f19f8bf7c5318a3'
RUNTIME_VERSION = 'Debian asymptote 2.85+ds-1 / upstream parseonly'
MAX_CODE_BYTES = 2 * 1024 * 1024
Token = collections.namedtuple('Token', 'kind value start end')
_TYPES = r'(?:real|pair|path|guide|triple|pen|picture|transform|frame|file|bool3)'
_IDENTIFIER = re.compile(r'[A-Za-z_]\w*')
_NUMBER = re.compile(r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?')
_IMPORT_SIGNATURE = re.compile(r'\b(?:(?:import|access)\s+[A-Za-z_]\w*(?:\s+as\s+[A-Za-z_]\w*)?\s*;|from\s+[A-Za-z_]\w*\s+access\s+[^;]+;)')
_LEADING_IMPORT = re.compile(r'\A\s*(?:(?:import|access)\s+[A-Za-z_]\w*(?:\s+as\s+[A-Za-z_]\w*)?\s*;|from\s+[A-Za-z_]\w*\s+access\s+[^;]+;)')
_NATIVE_MODULE_HINTS = frozenset({'graph', 'graph3', 'geometry', 'three', 'palette',
    'solids', 'contour', 'patterns', 'stats', 'math', 'flowchart', 'labelpath3',
    'grid', 'markers', 'contour3', 'plain', 'settings'})


def _string_value(body, quote):
    # Preserve unknown escapes (notably TeX commands); decode only delimiters
    # and doubled slashes, for resource names and embedded TeX inspection.
    return re.sub(r'\\([\\' + re.escape(quote) + r'])', lambda m: m.group(1), body)


@functools.lru_cache(maxsize=128)
def _lex(code):
    """Tokenize outside strings/comments and preserve source offsets."""
    tokens = []
    masked = list(code)
    i = 0
    error = None
    while i < len(code):
        ch = code[i]
        if code.startswith('//', i):
            end = code.find('\n', i + 2)
            end = len(code) if end < 0 else end
            for n in range(i, end): masked[n] = ' '
            i = end
            continue
        if code.startswith('/*', i):
            end = code.find('*/', i + 2)
            if end < 0:
                error = 'unterminated_comment'; end = len(code)
            else: end += 2
            for n in range(i, end):
                if masked[n] != '\n': masked[n] = ' '
            i = end
            continue
        if ch in ('"', "'"):
            start = i; quote = ch; i += 1; body_start = i
            while i < len(code):
                if code[i] == '\\': i += 2; continue
                if code[i] == quote: break
                i += 1
            if i >= len(code):
                body = code[body_start:]; i = len(code); error = 'unterminated_string'
            else:
                body = code[body_start:i]; i += 1
            tokens.append(Token('string', _string_value(body, quote), start, i))
            for n in range(start, i):
                if masked[n] != '\n': masked[n] = ' '
            continue
        if ch.isspace(): i += 1; continue
        match = _IDENTIFIER.match(code, i)
        if match:
            value = match.group(0); tokens.append(Token('id', value, i, i + len(value))); i += len(value); continue
        match = _NUMBER.match(code, i)
        if match:
            value = match.group(0); tokens.append(Token('number', value, i, i + len(value))); i += len(value); continue
        two = code[i:i + 2]
        if two in {'--', '..', '::', '>=', '<=', '==', '!=', '++', '+=', '-=', '*=', '/='}:
            tokens.append(Token('symbol', two, i, i + 2)); i += 2
        else:
            tokens.append(Token('symbol', ch, i, i + 1)); i += 1
    return tuple(tokens), ''.join(masked), error


def _calls(tokens):
    """Call names, excluding ordinary typed function declarations."""
    calls = []
    declarations = set()
    stack = []; closings = {}
    for index, token in enumerate(tokens):
        if token.kind == 'symbol' and token.value == '(': stack.append(index)
        elif token.kind == 'symbol' and token.value == ')' and stack: closings[stack.pop()] = index
    for i, token in enumerate(tokens[:-1]):
        if token.kind != 'id' or tokens[i + 1].value != '(': continue
        closing = closings.get(i + 1)
        if i and tokens[i - 1].kind == 'id' and re.fullmatch(_TYPES + r'|void|int|bool|string', tokens[i - 1].value):
            declarations.add(token.value); continue
        if closing is not None and closing + 1 < len(tokens) and tokens[closing + 1].value == '{':
            if i and tokens[i - 1].kind == 'id' and tokens[i - 1].value not in {'return', 'else'}:
                declarations.add(token.value); continue
        calls.append((token.value, i))
    return calls, declarations


def _native_names(tokens):
    """Unqualified calls or calls on an explicitly imported native module."""
    aliases = set()
    for i, token in enumerate(tokens[:-1]):
        if token.kind != 'id' or token.value not in {'import', 'access'}: continue
        module = tokens[i + 1]
        if module.kind != 'id' or module.value not in _NATIVE_MODULE_HINTS: continue
        alias = module.value
        if i + 3 < len(tokens) and tokens[i + 2].value == 'as' and tokens[i + 3].kind == 'id':
            alias = tokens[i + 3].value
        aliases.add(alias)
    calls, declarations = _calls(tokens)
    names = {name for name, index in calls if not index or tokens[index - 1].value != '.'
             or (index >= 2 and tokens[index - 2].value in aliases)}
    return names - declarations, declarations


def _enclosure_end(tokens, start, opening='(', closing=')'):
    depth = 0
    for index in range(start, len(tokens)):
        token = tokens[index]
        if token.kind != 'symbol': continue
        if token.value == opening: depth += 1
        elif token.value == closing:
            depth -= 1
            if depth == 0: return index
    return None


def _split_items(tokens):
    items = []; begin = 0; depth = 0
    for index, token in enumerate(tokens):
        if token.kind != 'symbol': continue
        if token.value in {'(', '[', '{'}: depth += 1
        elif token.value in {')', ']', '}'}: depth -= 1
        elif token.value == ',' and depth == 0:
            items.append(tokens[begin:index]); begin = index + 1
    if begin < len(tokens): items.append(tokens[begin:])
    return items


def _call_arguments(tokens, index):
    end = _enclosure_end(tokens, index + 1)
    return _split_items(tokens[index + 2:end]) if end is not None else []


def _flat(tokens):
    return ' '.join(token.value if token.kind != 'string' else '__string_literal__' for token in tokens)


def _write_sites(tokens, name):
    sites = []
    operators = {'=', '+=', '-=', '*=', '/=', '++', '--'}
    for index, token in enumerate(tokens):
        if token.kind != 'id' or token.value != name or (index and tokens[index - 1].value == '.'): continue
        if index + 1 < len(tokens) and tokens[index + 1].value in operators: sites.append((token.start, tokens[index + 1].value))
        elif index and tokens[index - 1].value in {'++', '--'}: sites.append((token.start, tokens[index - 1].value))
    return sites


def _turn_pattern(fraction, degrees_wrapper):
    if not degrees_wrapper: return r'360(?:\.0*)? \* ' + fraction
    patterns = []
    # These are exactly the three known real scalar factors. An omitted '*'
    # is allowed only for Asy's numeric coefficient syntax (2pi / 2fraction).
    for factors in itertools.permutations(('2', 'pi', fraction)):
        pattern = factors[0]
        for left, right in zip(factors, factors[1:]):
            pattern += (r' (?:\* )?' if left == '2' else r' \* ') + right
        patterns.append(pattern)
    return '(?:' + '|'.join(patterns) + ')'


def _pie_data_evidence(tokens, native_names):
    """Observed data-normalized pie idiom, not arbitrary circles or sectors."""
    if 'arc' not in native_names or not native_names.intersection({'fill', 'filldraw'}): return None
    arrays = []
    for index, token in enumerate(tokens[:-5]):
        if token.kind != 'id' or token.value not in {'real', 'pen', 'string'}: continue
        if [part.value for part in tokens[index + 1:index + 3]] != ['[', ']']: continue
        name = tokens[index + 3]
        if name.kind != 'id' or [part.value for part in tokens[index + 4:index + 6]] != ['=', '{']: continue
        end = _enclosure_end(tokens, index + 5, '{', '}')
        if end is not None: arrays.append((token.value, name.value, _split_items(tokens[index + 6:end])))
    loops = []
    for index, token in enumerate(tokens[:-1]):
        if token.kind != 'id' or token.value != 'for' or tokens[index + 1].value != '(': continue
        end = _enclosure_end(tokens, index + 1)
        if end is None or end + 1 >= len(tokens): continue
        if tokens[end + 1].value == '{':
            body_end = _enclosure_end(tokens, end + 1, '{', '}')
            if body_end is None: continue
            body = tokens[end + 2:body_end]
        else:
            body_end = next((j for j in range(end + 1, len(tokens)) if tokens[j].kind == 'symbol' and tokens[j].value == ';'), None)
            if body_end is None: continue
            body = tokens[end + 1:body_end + 1]
        loops.append((tokens[index + 2:end], body))
    identifier = r'[A-Za-z_]\w*'
    for kind, data_name, items in arrays:
        if kind != 'real' or len(items) < 2: continue
        values = []
        for item in items:
            text = ''.join(token.value for token in item)
            if not re.fullmatch(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?', text): break
            values.append(float(text))
        if len(values) != len(items) or any(not math.isfinite(value) or value < 0 for value in values) or sum(value > 0 for value in values) < 2: continue
        data = re.escape(data_name); total_names = set()
        for header, body in loops:
            header_match = re.fullmatch(r'real (' + identifier + r') : ' + data, _flat(header))
            if not header_match: continue
            total_match = re.fullmatch('(' + identifier + r') \+= ' + re.escape(header_match.group(1)) + r' ;', _flat(body))
            if not total_match: continue
            total_name = total_match.group(1); initializers = []
            for index, token in enumerate(tokens[:-3]):
                if token.kind != 'id' or token.value != total_name or not index or tokens[index - 1].value != 'real': continue
                if tokens[index + 1].value == '=' and tokens[index + 2].kind == 'number' and re.fullmatch(r'0(?:\.0*)?', tokens[index + 2].value) and tokens[index + 3].value == ';':
                    initializers.append(token.start)
            expected = {(initializers[0], '='), (body[0].start, '+=')} if len(initializers) == 1 else set()
            if expected and set(_write_sites(tokens, total_name)) == expected and len(_write_sites(tokens, total_name)) == 2:
                total_names.add(total_name)
        if not total_names: continue
        for header, body in loops:
            header_match = re.fullmatch(r'int (?P<i>' + identifier + r') = 0 ; (?P=i) < ' + data + r' \. length ; (?:(?P=i) \+\+|\+\+ (?P=i))', _flat(header))
            if not header_match: continue
            index_name = header_match.group('i'); counter = re.escape(index_name); body_text = _flat(body)
            for total_name in total_names:
                fraction_match = re.search(r'\breal (' + identifier + r') = ' + data + r' \[ ' + counter + r' \] / ' + re.escape(total_name) + r' ;', body_text)
                if not fraction_match: continue
                fraction_name = fraction_match.group(1); fraction = re.escape(fraction_name)
                fraction_writes = _write_sites(body, fraction_name)
                if len(fraction_writes) != 1 or fraction_writes[0][1] != '=': continue
                body_calls, _ = _calls(body)
                for fill_name, fill_index in body_calls:
                    if fill_name not in {'fill', 'filldraw'} or fill_name not in native_names: continue
                    fill_args = _call_arguments(body, fill_index)
                    if len(fill_args) < 2: continue
                    path = fill_args[0]
                    if not any(token.kind == 'id' and token.value == 'cycle' for token in path) or sum(token.kind == 'symbol' and token.value == '--' for token in path) < 2: continue
                    arc_ok = False
                    for arc_name, arc_index in _calls(path)[0]:
                        if arc_name != 'arc': continue
                        arc_args = _call_arguments(path, arc_index)
                        if len(arc_args) != 4: continue
                        start = _flat(arc_args[2]); end = _flat(arc_args[3])
                        start_degrees = start.startswith('degrees ( ') and start.endswith(' )')
                        end_degrees = end.startswith('degrees ( ') and end.endswith(' )')
                        if start_degrees != end_degrees: continue
                        if start_degrees: start = start[10:-2]; end = end[10:-2]
                        turn = _turn_pattern(fraction, start_degrees)
                        if not re.fullmatch(identifier, start) or not re.fullmatch(re.escape(start) + r' \+ ' + turn, end): continue
                        update = re.escape(start) + r' (?:\+= ' + turn + r'|= ' + re.escape(start) + r' \+ ' + turn + r') ;'
                        if re.search(r'\b' + update, body_text): arc_ok = True; break
                    if not arc_ok: continue
                    categorical = None
                    for array_kind, array_name, categories in arrays:
                        if len(categories) != len(items): continue
                        reference = re.escape(array_name) + r' \[ ' + counter + r' \]'
                        if array_kind == 'pen' and len({_flat(item) for item in categories}) >= 2 and re.fullmatch(reference, _flat(fill_args[1])):
                            categorical = 'indexed_pen_array'; break
                        if array_kind == 'string' and 'label' in native_names and all(len(item) == 1 and item[0].kind == 'string' for item in categories):
                            if len({item[0].value for item in categories}) < 2: continue
                            for label_name, label_index in body_calls:
                                label_args = _call_arguments(body, label_index) if label_name == 'label' else []
                                if label_args and re.fullmatch(reference, _flat(label_args[0])): categorical = 'indexed_label_array'; break
                    if categorical:
                        return {'data_items': len(items), 'positive_data_items': sum(value > 0 for value in values),
                                'normalization': 'sum_of_literal_data', 'closed_arc_slices_in_data_length_loop': True,
                                'categorical_source': categorical}
    return None


def is_asymptote(code):
    """Recognize an explicit Asy import plus non-Python Asy evidence."""
    if not isinstance(code, str) or len(code) > MAX_CODE_BYTES or not _IMPORT_SIGNATURE.search(code): return False
    classification_code = code
    try:
        ast.parse(code)
    except (SyntaxError, ValueError): pass
    else:
        # Some genuine Asy programs are also valid Python ASTs (notably path
        # '--' and ordinary function-call syntax). Keep those eligible, but
        # remove Python's actual comments, docstrings and triple/f-strings so
        # an embedded Asy example cannot change the outer program's language.
        masked = list(code); offsets = [0]
        for line in code.splitlines(keepends=True): offsets.append(offsets[-1] + len(line))
        try:
            for token in tokenize.generate_tokens(io.StringIO(code).readline):
                if token.type not in {tokenize.STRING, tokenize.COMMENT}: continue
                start = offsets[token.start[0] - 1] + token.start[1]
                end = offsets[token.end[0] - 1] + token.end[1]
                for index in range(start, end):
                    if masked[index] != '\n': masked[index] = ' '
            classification_code = ''.join(masked)
        except (tokenize.TokenError, IndentationError, IndexError): return False
    tokens, text, _ = _lex(classification_code)
    # Hash comments are not Asy syntax. Their contents are never evidence for
    # changing a Python/broken-Python program into Asy.
    text = re.sub(r'(?m)#[^\n]*', lambda m: ' ' * len(m.group(0)), text)
    if not _LEADING_IMPORT.match(text): return False
    tokens, _, _ = _lex(text)
    if re.search(r'\b(?:def|class)\s+[A-Za-z_]|\blambda\b|\bfrom\s+[\w.]+\s+import\b', text): return False
    typed = bool(re.search(r'\b' + _TYPES + r'\b\s*(?:\[\s*\]\s*)*[A-Za-z_]\w*\s*(?:[=,;(]|\[)', text))
    units = bool(re.search(r'(?<![\w.])(?:\d+(?:\.\d*)?|\.\d+)(?:pi|cm|mm|bp|pt|inches)\b', text))
    names, _ = _native_names(tokens)
    path = any(t.value in {'--', '..'} for t in tokens) and 'draw' in names and 'size' in names
    native = bool(names & {'xaxis', 'yaxis', 'xaxis3', 'yaxis3', 'histogram'}) and 'size' in names
    # Semicolons are also ordinary Python syntax. Weak call-name evidence
    # requires a real native module, so np.size/np.histogram cannot switch a
    # NumPy/Matplotlib program's language. Typed declarations/units remain
    # decisive evidence for unsupported native modules, which deps reject.
    first_module = tokens[1].value if len(tokens) > 1 else None
    if first_module not in _NATIVE_MODULE_HINTS and not (typed or units): return False
    return bool(typed or units or path or native)


def visual_facts(code):
    """Positive chart evidence, deliberately excluding mere geometric draws."""
    tokens, _, error = _lex(code)
    if error: return {'chart': False, 'substantial': False, 'lexical_error': error}
    names, declarations = _native_names(tokens)
    x = bool(names & {'xaxis', 'xaxis3'})
    y = bool(names & {'yaxis', 'yaxis3'})
    full_axes = (x and y) or bool(names & {'axes3'})
    graph = 'graph' in names and 'draw' in names
    native_chart = bool(names & {'histogram', 'errorbars'})
    pie = _pie_data_evidence(tokens, names)
    chart = bool((graph and full_axes) or native_chart or pie)
    return {'chart': chart, 'substantial': chart,
            'plot_calls': sorted(names & {'graph', 'histogram', 'errorbars'}),
            'draw_call': 'draw' in names, 'xaxis': x, 'yaxis': y,
            'full_axes': full_axes, 'pie_data_evidence': pie,
            'overridden_chart_function_names': sorted(declarations & {'graph', 'histogram', 'errorbars'})}


def _task_root(task_root=None):
    return Path(task_root).resolve() if task_root is not None else Path(__file__).resolve().parent.parent


@functools.lru_cache(maxsize=4)
def _runtime(task_root):
    base = Path(task_root) / 'runtime/asymptote-2.85'
    binary = base / 'root/usr/bin/asy'
    modules = base / 'root/usr/share/asymptote'
    libs = base / 'root/usr/lib/x86_64-linux-gnu'
    config = base / 'empty_config.asy'
    if not binary.is_file() or not modules.is_dir() or not libs.is_dir() or not config.is_file():
        raise ValueError('asymptote_parser_unavailable')
    if config.read_bytes() != b'' or hashlib.sha256(binary.read_bytes()).hexdigest() != BINARY_SHA256:
        raise ValueError('asymptote_parser_integrity_mismatch')
    return base, binary, modules, libs, config


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 ** 2, 512 * 1024 ** 2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


@functools.lru_cache(maxsize=128)
def _parse(code, task_root):
    if not code.strip(): return {'issue': 'missing_code'}
    try: payload = code.encode('utf-8')
    except UnicodeError: return {'issue': 'invalid_asymptote_source_encoding'}
    if len(payload) > MAX_CODE_BYTES: return {'issue': 'asymptote_code_size_limit'}
    _, _, error = _lex(code)
    if error: return {'issue': 'invalid_asymptote_syntax', 'lexical_error': error}
    try: base, binary, modules, libs, config = _runtime(task_root)
    except (OSError, ValueError) as exc:
        return {'issue': str(exc) if isinstance(exc, ValueError) else 'asymptote_parser_unavailable'}
    env = dict(os.environ, ASYMPTOTE_CONFIG=str(config), ASYMPTOTE_DIR=str(modules),
               LD_LIBRARY_PATH=str(libs), LC_ALL='C')
    cmd = [str(binary), '-config', str(config), '-dir', str(modules), '-safe',
           '-noglobalread', '-noglobalwrite', '-parseonly', '-']
    try:
        process = subprocess.run(cmd, input=payload, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE, cwd=base, env=env, timeout=5,
                                 preexec_fn=_limits)
    except subprocess.TimeoutExpired: return {'issue': 'asymptote_parser_timeout'}
    except OSError: return {'issue': 'asymptote_parser_unavailable'}
    if process.returncode == 0: return {'issue': None, 'exit_code': 0, 'backend': RUNTIME_VERSION}
    if process.returncode in {-signal.SIGXCPU, -signal.SIGKILL, -signal.SIGSEGV, -signal.SIGABRT}:
        return {'issue': 'asymptote_parser_resource_or_process_failure', 'exit_code': process.returncode}
    # No stderr text or source excerpts leave this helper.
    stderr = process.stderr[:16384].decode('utf-8', errors='replace')
    if process.returncode in (126, 127) or 'error while loading shared libraries' in stderr:
        return {'issue': 'asymptote_parser_unavailable', 'exit_code': process.returncode}
    match = re.search(r'(?:\.asy|<stdin>|-)\s*:\s*(\d+)(?:\.\d+)?\s*:', stderr)
    return {'issue': 'invalid_asymptote_syntax', 'exit_code': process.returncode,
            'line': int(match.group(1)) if match else None}


def syntax_facts(code, task_root=None):
    """Small parser metadata only: never exposes its code-containing stderr."""
    return dict(_parse(code, str(_task_root(task_root))))


def syntax_issue(code, task_root=None):
    return syntax_facts(code, task_root).get('issue')


@functools.lru_cache(maxsize=4)
def _builtin_modules(task_root):
    _, _, modules, _, _ = _runtime(task_root)
    # All module names come from the already verified distribution payload.
    return frozenset(p.stem for p in modules.glob('*.asy') if p.is_file()) | {'settings'}


def _constant_string_values(tokens):
    """Fold literal + chains, including parenthesized literal pieces only."""
    def expression(index, depth=0):
        if depth > 12 or index >= len(tokens): return None
        token = tokens[index]
        if token.kind == 'string': result = (token.value, index + 1)
        elif token.kind == 'symbol' and token.value == '(':
            inner = expression(index + 1, depth + 1)
            if inner is None or inner[1] >= len(tokens) or tokens[inner[1]].value != ')': return None
            result = (inner[0], inner[1] + 1)
        else: return None
        value, end = result
        while end < len(tokens) and tokens[end].kind == 'symbol' and tokens[end].value == '+':
            right = expression(end + 1, depth + 1)
            if right is None: break
            value += right[0]; end = right[1]
            if len(value) > MAX_CODE_BYTES: return None
        return value, end
    values = []; index = 0
    while index < len(tokens):
        folded = expression(index)
        if folded is None: index += 1; continue
        values.append(folded[0]); index = folded[1]
    return values


def dependency_issue(code, raw_root, available_assets=None):
    """Reject unresolved custom modules, native file inputs and dynamic code."""
    tokens, _, error = _lex(code)
    if error: return 'invalid_asymptote_syntax'
    raw_root = Path(raw_root).resolve(); available_assets = available_assets or {}
    try: builtins = _builtin_modules(str(_task_root()))
    except (OSError, ValueError): return 'asymptote_parser_unavailable'

    def resource_issue(value):
        if not isinstance(value, str) or not value.strip(): return 'unresolved_asymptote_input_dependency'
        value = value.strip()
        if re.match(r'^(?:https?|ftp|file|s3|gs)://|^//', value, re.I): return 'external_asymptote_input_dependency'
        if '\\' in value or '\x00' in value: return 'unresolved_asymptote_input_dependency'
        try:
            mapped = available_assets.get(value)
            if mapped and Path(mapped).is_file(): return None
            path = (raw_root / value).resolve()
            if path.is_relative_to(raw_root) and path.is_file(): return None
        except (OSError, ValueError):
            # A malformed or overlong source reference is an unresolved input,
            # never a reason to abort the remaining rows in a full source file.
            return 'unresolved_asymptote_input_dependency'
        return 'missing_local_asymptote_input_dependency'

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.kind == 'id' and token.value == 'input' and (i + 1 == len(tokens) or tokens[i + 1].value != '('):
            return 'unresolved_asymptote_input_dependency'
        if token.kind == 'id' and token.value in {'import', 'access', 'include', 'from'}:
            start = i; end = next((j for j in range(i + 1, len(tokens)) if tokens[j].kind == 'symbol' and tokens[j].value == ';'), len(tokens))
            statement = tokens[start:end]
            if len(statement) < 2: return 'unresolved_asymptote_module_dependency'
            module = statement[1]
            if module.kind == 'string':
                if re.match(r'^(?:https?|ftp|file)://|^//', module.value, re.I): return 'external_asymptote_module_dependency'
                return 'nonstandard_asymptote_module_dependency'
            if module.kind != 'id' or module.value not in builtins: return 'nonstandard_asymptote_module_dependency'
            # A single bare distribution module is allowed; dotted names, path
            # expressions or dynamic imports are not inferred as standard files.
            if token.value in {'import', 'access', 'include'}:
                rest = statement[2:]
                if rest and not (len(rest) == 2 and rest[0].value == 'as' and rest[1].kind == 'id'):
                    return 'unresolved_asymptote_module_dependency'
            elif len(statement) < 4 or statement[2].value not in {'access', 'unravel'}:
                return 'unresolved_asymptote_module_dependency'
            elif any(part.value in {'input', 'graphic', 'read', 'readfile', 'load',
                     'system', 'eval', 'asy', 'execute', 'run', 'cd', 'chdir',
                     'readline', 'getstring', 'getint', 'getreal', 'getpair', 'gettriple', 'getc'}
                     for part in statement[3:]) and any(part.value == 'as' for part in statement[3:]):
                # The next call name would be an arbitrary alias. Do not infer
                # that it is pure just because its spelling changed.
                return 'aliased_asymptote_input_or_dynamic_dependency'
            i = end + 1; continue
        i += 1

    calls, _ = _calls(tokens)
    dynamic = {'system', 'eval', 'asy', 'execute', 'run', 'cd', 'chdir'}
    interactive = {'readline', 'getstring', 'getint', 'getreal', 'getpair', 'gettriple', 'getc'}
    for name, index in calls:
        if name in dynamic: return 'dynamic_asymptote_code_or_resource_dependency'
        if name in interactive: return 'interactive_asymptote_input_dependency'
        if name in {'input', 'graphic', 'read', 'readfile', 'load'}:
            arg = tokens[index + 2] if index + 2 < len(tokens) else None
            if arg is None or arg.kind != 'string': return 'unresolved_asymptote_input_dependency'
            after = tokens[index + 3].value if index + 3 < len(tokens) else None
            if after not in {')', ','}: return 'unresolved_asymptote_input_dependency'
            issue = resource_issue(arg.value)
            if issue: return issue

    # Inline TeX is a separate resource channel even inside an ordinary label.
    for value in _constant_string_values(tokens):
        if re.search(r'\\(?:openin|read|write18|directlua|catcode)\b', value):
            return 'unresolved_asymptote_tex_dependency'
        commands = list(re.finditer(r'\\(?:includegraphics|include|input)\b\*?\s*(?:\[[^\]]*\]\s*)?', value))
        for command in commands:
            tail = value[command.end():]
            match = re.match(r'\{([^{}]*)\}', tail)
            if not match: return 'unresolved_asymptote_tex_dependency'
            reference = match.group(1).strip()
            if re.search(r'[\\#{}]', reference): return 'unresolved_asymptote_tex_dependency'
            issue = resource_issue(reference)
            if issue: return issue
    return None
