"""Materialize the exact source Text backend before querying physical fonts.

DOM.describeNode may return a child nodeId of zero when that child has not
been sent to the frontend. It still supplies a backendNodeId. No parent font
aggregation, text rewriting, browser retries, or source mutation is allowed.
"""


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _positive_int(value):
    return type(value) is int and value > 0


def _child(session, parent, index, text):
    description = session.send('DOM.describeNode', {'nodeId': parent, 'depth': 1})['node']
    children = description.get('children', [])
    _require(type(index) is int and 0 <= index < len(children),
             'native_source_text_child_index_changed')
    child = children[index]
    _require(child.get('nodeType') == 3 and child.get('nodeValue') == text,
             'native_source_text_backend_node_binding_changed')
    _require(_positive_int(child.get('backendNodeId')),
             'native_source_text_backend_identity_missing')
    return child


def physical_fonts(session, parent_node_id, child_index, expected_text):
    """Return fonts for one exact Text node; refuse detached or changed text.

    The backend identity, text and original parent/child position are checked
    around the platform-font query. Protocol errors propagate to the caller.
    """
    _require(_positive_int(parent_node_id), 'native_source_text_parent_missing')
    _require(isinstance(expected_text, str) and bool(expected_text),
             'native_source_text_expected_content_missing')
    child = _child(session, parent_node_id, child_index, expected_text)
    backend = child['backendNodeId']
    pushed = session.send('DOM.pushNodesByBackendIdsToFrontend',
                          {'backendNodeIds': [backend]}).get('nodeIds')
    _require(isinstance(pushed, list) and len(pushed) == 1 and _positive_int(pushed[0]),
             'native_source_text_backend_not_materialized')
    frontend = pushed[0]
    actual = session.send('DOM.describeNode', {'nodeId': frontend, 'depth': 0})['node']
    _require(actual.get('backendNodeId') == backend and actual.get('nodeType') == 3
             and actual.get('nodeValue') == expected_text,
             'native_source_text_materialized_identity_changed')
    fonts = session.send('CSS.getPlatformFontsForNode', {'nodeId': frontend})['fonts']
    _require(isinstance(fonts, list) and all(isinstance(font, dict) for font in fonts),
             'native_source_text_physical_font_response_invalid')
    _require(_child(session, parent_node_id, child_index, expected_text)['backendNodeId'] == backend,
             'native_source_text_parent_membership_changed')
    return fonts
