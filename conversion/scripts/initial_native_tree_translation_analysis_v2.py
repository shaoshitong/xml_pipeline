"""Exact primitive equations over complete observations; no quality admission.

This proves only the explicitly implemented coordinate equations and records
every remaining attribute/style difference. It refuses to certify whole-scene
equivalence without a complete clipping and inherited-CSS paint interpreter.
"""
import collections,re
from decimal import Decimal
from initial_native_render_tree_evidence_v2 import flatten,unsupported,SVG,HTML

NUMBER=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
TOKEN=re.compile(NUMBER+r'|[A-Za-z]')
ARITY={'M':2,'L':2,'H':1,'V':1,'C':6,'S':4,'Q':4,'T':2,'A':7,'Z':0}
class Unsupported(ValueError):pass
def require(value,reason):
    if not value:raise Unsupported(reason)

def path_commands(value):
    if value.startswith('path("') and value.endswith('")'):value=value[6:-2]
    tokens=TOKEN.findall(value);require(re.sub(r'[\s,]','',TOKEN.sub('',value))=='','unknown_path_token');result=[];index=0
    while index<len(tokens):
        command=tokens[index];require(command in ARITY,'unknown_or_relative_path_command:'+command);index+=1;arity=ARITY[command]
        if not arity:result.append((command,()));continue
        groups=0
        while index<len(tokens) and re.fullmatch(NUMBER,tokens[index]):
            raw=tokens[index:index+arity];require(len(raw)==arity and all(re.fullmatch(NUMBER,item) for item in raw),'incomplete_path_command');values=tuple(Decimal(item) for item in raw);require(all(item.is_finite() for item in values),'nonfinite_path_number');result.append((command,values));index+=arity;groups+=1
        require(groups,'empty_path_command')
    require(result and result[0][0]=='M','path_requires_absolute_moveto');return result

def path_translation_exact(before,after,dx,dy):
    left=path_commands(before);right=path_commands(after);require(len(left)==len(right),'path_command_count_changed');dx=Decimal(str(dx));dy=Decimal(str(dy))
    for (command,a),(other,b) in zip(left,right):
        require(command==other and len(a)==len(b),'path_command_structure_changed')
        if command=='Z':continue
        expected=[]
        if command=='H':expected=[a[0]+dx]
        elif command=='V':expected=[a[0]+dy]
        elif command=='A':
            require(a[3] in [0,1] and a[4] in [0,1] and b[3] in [0,1] and b[4] in [0,1],'unknown_arc_flags');expected=[*a[:5],a[5]+dx,a[6]+dy]
        else:expected=[number+(dx if index%2==0 else dy) for index,number in enumerate(a)]
        require(tuple(expected)==b,'path_coordinate_equation_changed')
    return True

def _numeric(value):
    require(isinstance(value,str) and re.fullmatch(NUMBER+r'(?:px)?',value),'unknown_coordinate_unit');return Decimal(value[:-2] if value.endswith('px') else value)
def _attributes(node):return {row['name']:row['value'] for row in node.get('attributes',[])}
def _style(value):
    result={}
    for token in value.split(';'):
        if not token.strip():continue
        require(':' in token,'unknown_inline_style_syntax');key,val=token.split(':',1);require(key.strip() not in result,'duplicate_inline_style_property');result[key.strip()]=val.strip()
    return result

def analyze(before,after,translation):
    dx,dy=map(lambda value:Decimal(str(value)),translation);require(all(value==int(value) for value in [dx,dy]),'integer_translation_required');left=flatten(before);right=flatten(after);counts=collections.Counter();failures=[];context_differences=[];unhandled_styles=[]
    for path in sorted(set(left)|set(right)):
        a=left.get(path);b=right.get(path)
        try:
            require(a is not None and b is not None,'tree_shape_changed');require((a.get('nodeType'),a.get('namespace'),a.get('tag'))==(b.get('nodeType'),b.get('namespace'),b.get('tag')),'node_type_changed');require(a.get('text')==b.get('text'),'text_node_changed')
            if a['nodeType']!=1:continue
            attrs_a=_attributes(a);attrs_b=_attributes(b);require(set(attrs_a)==set(attrs_b),'attribute_set_changed');tag=a['tag'];namespace=a['namespace'];local_dx,local_dy=dx,dy
            for key in ['screenCTM']:
                one=a.get(key);two=b.get(key)
                require((one is None)==(two is None),'matrix_presence_changed')
                if one is not None:
                    require(all(one.get(name)==two.get(name)==value for name,value in [('a',1),('b',0),('c',0),('d',1)]) and one.get('is2D') is not False and two.get('is2D') is not False,'unknown_nontranslation_matrix');local_dx=dx-(Decimal(str(two['e']))-Decimal(str(one['e'])));local_dy=dy-(Decimal(str(two['f']))-Decimal(str(one['f'])))
            for key in attrs_a:
                one,two=attrs_a[key],attrs_b[key]
                if key=='d' and namespace==SVG and tag=='path':path_translation_exact(one,two,local_dx,local_dy);counts['complete_path_command_equations']+=1
                elif key in ['x','y'] and namespace==SVG and tag in ['rect','foreignObject']:
                    require(_numeric(two)-_numeric(one)==(local_dx if key=='x' else local_dy),'coordinate_equation_changed:'+key);counts['svg_coordinate_equations']+=1
                elif path=='0' and key=='data-mxgraph':counts['control_xml_attr_requires_separate_model_transform_proof']+=1
                elif path=='0' and key=='style' and one!=two:
                    sa=_style(one);sb=_style(two);changed={name:[sa.get(name),sb.get(name)] for name in set(sa)|set(sb) if sa.get(name)!=sb.get(name)};context_differences.append({'path':path,'kind':'root_inline_style','changes':changed})
                else:require(one==two,'other_attribute_changed:'+key)
            sa=a.get('computed',{});sb=b.get('computed',{});require(set(sa)==set(sb),'computed_style_schema_changed')
            for key in sa:
                one,two=sa[key],sb[key]
                if key=='d' and namespace==SVG and tag=='path':path_translation_exact(one,two,local_dx,local_dy);counts['computed_path_equations']+=1
                elif key in ['x','y'] and namespace==SVG and tag in ['rect','foreignObject']:
                    require(_numeric(two)-_numeric(one)==(local_dx if key=='x' else local_dy),'computed_coordinate_equation_changed:'+key);counts['computed_svg_coordinate_equations']+=1
                elif one!=two:
                    if path=='0':context_differences.append({'path':path,'kind':'root_computed_style','property':key,'before':one,'after':two})
                    else:unhandled_styles.append({'path':path,'property':key,'before':one,'after':two})
            require(a.get('pseudo')==b.get('pseudo'),'pseudo_paint_changed');counts['all_other_attribute_style_text_values_exact']+=1
        except (Unsupported,KeyError,TypeError) as error:failures.append({'path':path,'tag':a.get('tag') if a else None,'reason':str(error)})
    unsafe=unsupported(before)+unsupported(after);require(before.get('fontFaceRules')==after.get('fontFaceRules') and before.get('fontFaces')==after.get('fontFaces') and before.get('resources')==after.get('resources'),'font_or_resource_set_changed')
    return {'known_integer_translation':translation,'exact_implemented_equation_counts':dict(counts),'primitive_or_structure_failures':failures,'unhandled_nonroot_style_changes':unhandled_styles,'root_context_style_differences':context_differences,'observed_unsupported_features':unsafe,'all_implemented_primitive_equations_exact':not failures and not unhandled_styles and not unsafe,'all_text_font_resources_exact':True,'complete_render_tree_equivalence_certified':False,'acceptance_allowed':False,'formal_remaining_conditions':['Root viewport overflow/clipping differences must be interpreted or eliminated under a separately proven fixed-context contract.','Every inherited/computed style must have an explicit translation-covariant paint rule; string equality alone does not declare unknown properties supported.','Defs, clip, marker, gradient/pattern, mask/filter or foreignObject variants outside the reviewed observed primitive schema must fail closed.','Source provenance, strict outside0, independent native editing and all original global/local/text fidelity gates remain mandatory.']}
