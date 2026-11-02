function resolveSourceGeometry(el, tag, attrs, css) {
  if (!['rect', 'circle', 'ellipse'].includes(tag)) return {applied: false};
  const names = ['x', 'y', 'width', 'height', 'rx', 'ry', 'cx', 'cy', 'r'];
  const attributes = Object.fromEntries(names.map(k => [k, el.getAttribute(k)]));
  const computed = Object.fromEntries(names.map(k => [k, css[k] ?? null]));
  const b = el.getBBox();
  const box = {x: b.x, y: b.y, w: b.width, h: b.height};
  if (!Object.values(box).every(Number.isFinite) || b.width < 0 || b.height < 0)
    throw Error('source_nonfinite_resolved_geometry');
  const resolved = {};
  if (tag === 'rect') {
    Object.assign(resolved, {x: b.x, y: b.y, width: b.width, height: b.height});
    const radius = key => {
      const value = (computed[key] ?? 'auto').trim();
      if (value === 'auto') return null;
      if (!/^[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:px)?$/.test(value))
        throw Error('source_resolved_rect_radius_requires_absolute_length:' + key + ':' + value);
      const n = Number.parseFloat(value);
      if (!Number.isFinite(n) || n < 0) throw Error('source_invalid_resolved_rect_radius');
      return n;
    };
    let rx = radius('rx'), ry = radius('ry');
    if (rx === null && ry === null) rx = ry = 0;
    else if (rx === null) rx = ry;
    else if (ry === null) ry = rx;
    Object.assign(resolved, {rx: Math.min(rx, b.width / 2), ry: Math.min(ry, b.height / 2)});
  } else {
    Object.assign(resolved, {cx: b.x + b.width / 2, cy: b.y + b.height / 2});
    if (tag === 'circle') {
      if (Math.abs(b.width - b.height) > 0.00001) throw Error('source_circle_local_geometry_not_circular');
      resolved.r = b.width / 2;
    } else Object.assign(resolved, {rx: b.width / 2, ry: b.height / 2});
  }
  if (names.some(k => el.getAttribute(k) !== attributes[k])) throw Error('source_geometry_observation_mutated_attributes');
  return {applied: true, tag, raw_attributes: attributes, animated_base_values: {...attrs},
    computed_css: computed, actual_local_bbox: box, resolved,
    method: 'actual_SVG_geometry_bbox_and_computed_absolute_corner_radii_v1',
    source_attributes_unchanged: true, candidate_or_reference_pixels_used: false};
}
