"""Failure-only equivalence of actual frozen TikZ branches; never accepts data."""
import ast,copy,hashlib,importlib,inspect,json,re
from pathlib import Path

OLD_POLICY='source_execution_glyph_lineage_native_render_and_local_fidelity_v3:210bf4dbced804c5'
ABSENT=('html_text_layout_v5','html_actual_text_alignment')
UNKNOWN=object()
sha=lambda b:hashlib.sha256(b).hexdigest()


def family_assumptions(record):
    if record.get('source_format')!='tikz' or any(record.get(key) for key in ABSENT):
        raise ValueError('failure_equivalence_requires_plain_TikZ_without_changed_family_lineage')
    if not record.get('original_reference') or not record.get('original_source_code'):
        raise ValueError('failure_equivalence_requires_persisted_original_payloads')


def static(node):
    if isinstance(node,ast.Constant):return node.value
    if isinstance(node,(ast.Tuple,ast.List,ast.Set)):
        values=[static(x) for x in node.elts]
        return tuple(values) if all(x is not UNKNOWN for x in values) else UNKNOWN
    if isinstance(node,ast.Name):return {'fmt':'tikz','glyph_profile':False}.get(node.id,UNKNOWN)
    if isinstance(node,ast.Subscript) and isinstance(node.value,ast.Name) and node.value.id in ('r','record') and static(node.slice)=='source_format':return 'tikz'
    if isinstance(node,ast.Call):
        if isinstance(node.func,ast.Name) and node.func.id=='bool' and len(node.args)==1:
            value=static(node.args[0]);return bool(value) if value is not UNKNOWN else UNKNOWN
        if isinstance(node.func,ast.Attribute) and node.func.attr=='get' and isinstance(node.func.value,ast.Name) and node.func.value.id in ('r','record','before') and node.args:
            key=static(node.args[0])
            if key in ABSENT:return None
            if key in ('original_reference','original_source_code'):return 'present_original_payload'
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.Not):
        value=static(node.operand);return not value if value is not UNKNOWN else UNKNOWN
    if isinstance(node,ast.BoolOp):
        values=[static(x) for x in node.values]
        if isinstance(node.op,ast.And):
            if any(v is not UNKNOWN and not v for v in values):return False
            return True if all(v is not UNKNOWN for v in values) else UNKNOWN
        if any(v is not UNKNOWN and v for v in values):return True
        return False if all(v is not UNKNOWN for v in values) else UNKNOWN
    if isinstance(node,ast.Compare) and len(node.ops)==1:
        left,right=static(node.left),static(node.comparators[0])
        if left is UNKNOWN or right is UNKNOWN:return UNKNOWN
        operation=node.ops[0]
        if isinstance(operation,ast.Eq):return left==right
        if isinstance(operation,ast.NotEq):return left!=right
        if isinstance(operation,ast.In):return left in right
        if isinstance(operation,ast.NotIn):return left not in right
    return UNKNOWN


class TikZ(ast.NodeTransformer):
    def statements(self,nodes):
        result=[]
        for node in nodes:
            value=self.visit(node)
            result.extend(value if isinstance(value,list) else [value] if value is not None else [])
        return result
    def visit_If(self,node):
        value=static(node.test)
        if value is not UNKNOWN:return self.statements(node.body if value else node.orelse)
        return self.generic_visit(node)
    def visit_IfExp(self,node):
        value=static(node.test)
        return self.visit(node.body if value else node.orelse) if value is not UNKNOWN else self.generic_visit(node)
    def visit_Assign(self,node):
        if any(isinstance(target,ast.Name) and target.id=='renderer' for target in node.targets):return None
        return self.generic_visit(node)
    def expression(self,node):
        value=static(node)
        return ast.copy_location(ast.Constant(value=value),node) if value is not UNKNOWN and isinstance(value,(str,int,float,bool,type(None))) else self.generic_visit(node)
    visit_Compare=expression
    visit_BoolOp=expression
    visit_Call=expression
    visit_Subscript=expression
    def visit_Name(self,node):
        return self.expression(node) if isinstance(node.ctx,ast.Load) else node


def function_node(source,name):
    matches=[n for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
    if len(matches)!=1:raise ValueError('exactly_one_function_required: '+name)
    return matches[0]


def normalized(source,name,prefix=False):
    node=copy.deepcopy(function_node(source,name))
    if prefix:
        tries=[n for n in node.body if isinstance(n,ast.Try)]
        if len(tries)!=1:raise ValueError('unsupported_verify_control_flow')
        body=[];found=False
        for statement in tries[0].body:
            body.append(statement)
            if isinstance(statement,ast.If) and any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='require_coverage' for n in ast.walk(statement)):
                found=True;break
        if not found:raise ValueError('source_reject_boundary_not_found')
        node.body=body
    node=TikZ().visit(node);ast.fix_missing_locations(node)
    return ast.dump(node,include_attributes=False)


def compare_sources(old_source,new_source):
    result={}
    for name,prefix in (('source_baseline',False),('profile',False),('require_coverage',False),('verify',True)):
        old,new=normalized(old_source,name,prefix),normalized(new_source,name,prefix)
        if old!=new:raise ValueError('TikZ_failure_branch_not_equivalent: '+name)
        result[name]={'normalized_ast_sha256':sha(old.encode()),'scope':'early source rejection' if prefix else 'TikZ-only specialization'}
    return result


def registration_delegation(new_function,old_function):
    steps=[];seen=set()
    while new_function is not old_function:
        if id(new_function) in seen:raise ValueError('cyclic_registration_delegation')
        seen.add(id(new_function));node=TikZ().visit(copy.deepcopy(function_node(inspect.getsource(new_function),'registration_record')))
        body=node.body
        if len(body)!=1 or not isinstance(body[0],ast.Return) or not isinstance(body[0].value,ast.Call) or not isinstance(body[0].value.func,ast.Name):raise ValueError('registration_not_plain_TikZ_delegation')
        call=body[0].value
        if [getattr(a,'id',None) for a in call.args]!=['record','reference','xml'] or call.keywords:raise ValueError('registration_delegation_arguments_changed')
        target=new_function.__globals__.get(call.func.id)
        if not callable(target):raise ValueError('registration_delegate_not_found')
        path=Path(inspect.getsourcefile(new_function));steps.append({'module':new_function.__module__,'file':str(path),'sha256':sha(path.read_bytes()),'delegate':target.__module__+'.'+target.__name__});new_function=target
    return steps


def prove_modules(old,new,active_policy,expected_historical_policy=None):
    if expected_historical_policy is not None and old.POLICY!=expected_historical_policy:raise ValueError('historical_policy_pin_no_longer_reproduces')
    if new.POLICY!=active_policy:raise ValueError('active_policy_does_not_match_imported_implementation')
    mismatched=[name for name,digest in old.IMPLEMENTATION.items() if new.IMPLEMENTATION.get(name)!=digest]
    if mismatched:raise ValueError('shared_historical_implementation_changed: '+','.join(mismatched))
    for name in ('checked','structure_checks','resource_checks'):
        if getattr(old,name) is not getattr(new,name):raise ValueError('early_shared_gate_function_changed: '+name)
    if old.RENDERER!=new.RENDERER:raise ValueError('TikZ_native_renderer_changed')
    branches={}
    for name,prefix in (('source_baseline',False),('profile',False),('require_coverage',False),('verify',True)):
        prior=normalized(inspect.getsource(getattr(old,name)),name,prefix);current=normalized(inspect.getsource(getattr(new,name)),name,prefix)
        if prior!=current:raise ValueError('TikZ_failure_branch_not_equivalent: '+name)
        branches[name]={'normalized_ast_sha256':sha(prior.encode()),'scope':'early source rejection' if prefix else 'TikZ-only specialization'}
    delegation=registration_delegation(new.registration_record,old.registration_record)
    return {'version':1,'kind':'failure_only_early_literal_TikZ_equivalence','historical_policy':old.POLICY,'active_policy':new.POLICY,'branch_checks':branches,'registration_delegation':delegation,'all_historical_dependencies_still_pinned':dict(old.IMPLEMENTATION),'renderer':str(old.RENDERER),'does_not_certify_success_or_reuse_rendered_acceptance':True,'assumptions':list(ABSENT),'fresh_literal_rejection_and_source_payload_hashes_still_required':True}


def active_module(work):
    work=Path(work);owner_path=work/'auto_quality_owner.json';owner=json.loads(owner_path.read_text());cmd=Path('/proc')/str(owner['pid'])/'cmdline'
    args=cmd.read_bytes().split(b'\0') if cmd.exists() else []
    names=[Path(x.decode()).name for x in args if x and re.fullmatch(rb'auto_quality_batch_v4[a-z]*\.py',Path(x.decode()).name.encode())]
    if len(names)!=1:raise ValueError('active_QA4_family_coordinator_not_live_or_ambiguous')
    module=importlib.import_module(Path(names[0]).stem)
    return module,owner,sha(owner_path.read_bytes())
