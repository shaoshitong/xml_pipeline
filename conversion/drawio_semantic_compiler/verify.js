// Runs inside the pinned, offline draw.io editor. Reports the editor's own
// model, view and edit behaviour for one page of a document.
async ({request, editor, graph, model, view, points, settle}) => {
    const rect = r => r ? [r.x, r.y, r.width, r.height] : null;
    // Some native view states expose unavailable measurements as NaN. Keep
    // them distinct from null and finite measurements in the JSON proof.
    const measurement = (_, value) => typeof value === "number" && !Number.isFinite(value)
        ? {nonfinite: String(value)} : value;
    const json = value => JSON.stringify(value, measurement);
    const movement = (after, before) => after.map((value, axis) => value - before[axis]);
    // Cells in the editor's own child order. IDs are replaced by positions so
    // that two documents can be compared without trusting either one's names.
    const walk = () => {
        const cells = [];
        const visit = cell => {
            cells.push(cell);
            for (let i = 0; i < model.getChildCount(cell); i++) visit(model.getChildAt(cell, i));
        };
        visit(model.getRoot());
        return cells;
    };
    const describe = (cells) => {
        const index = new Map(cells.map((cell, i) => [cell, i]));
        const at = cell => cell == null ? null : index.has(cell) ? index.get(cell) : -1;
        // Resolved styles repeat heavily; send each distinct one once.
        const styles = new Map();
        const intern = text => {
            if (!styles.has(text)) styles.set(text, styles.size);
            return styles.get(text);
        };
        const records = cells.map(cell => {
            const state = view.getState(cell);
            const style = graph.getCellStyle(cell);
            const resolved = {};
            for (const key of Object.keys(style).sort()) resolved[key] = String(style[key]);
            const value = cell.value;
            const data = {};
            if (value != null && typeof value === "object" && value.attributes) {
                for (const a of value.attributes) if (a.name !== "label") data[a.name] = a.value;
            }
            const g = cell.geometry;
            // mxShape.createHandJiggle: this shape paints through the rough
            // canvas, whose seed is a hash of the cell ID.
            const shape = state?.shape;
            const seeded = !!shape && !shape.outline && shape.style != null &&
                "0" != mxUtils.getValue(shape.style, "sketch", "0") &&
                "comic" != mxUtils.getValue(shape.style, "sketchStyle", "rough");
            return {
                id: cell.id, parent: at(cell.parent),
                kind: model.isVertex(cell) ? "vertex" : model.isEdge(cell) ? "edge" : "plain",
                source: at(cell.source), target: at(cell.target),
                connectable: !!cell.isConnectable(), visible: !!cell.isVisible(), collapsed: !!cell.isCollapsed(),
                label: String(graph.convertValueToString(cell) ?? ""), data,
                // The label as painted, after placeholders such as %id%.
                painted_label: String(graph.getLabel(cell) ?? ""), id_seeds_sketch: seeded,
                style: intern(JSON.stringify(resolved)),
                geometry: g ? [g.x, g.y, g.width, g.height, !!g.relative] : null,
                shown: !!state, bbox: rect(state), paint_bbox: rect(state?.shape?.boundingBox),
                label_bbox: rect(state?.text?.boundingBox), points: points(state),
            };
        });
        return {cells: records, styles: [...styles.keys()]};
    };
    const snapshot = async () => {
        await settle();
        const bounds = mxRectangle.fromRectangle(graph.getGraphBounds());
        const image = graph.backgroundImage;
        if (image && image.width != null && image.height != null) {
            bounds.add(new mxRectangle(image.x, image.y, image.width, image.height));
        }
        return {bounds: rect(bounds), ...describe(walk())};
    };
    const observe = (cells, watch) => watch.map(([position, what]) => {
        const state = view.getState(cells[position]);
        if (!state) return null;
        if (what === "bbox") return rect(state);
        if (what === "label") return rect(state.text?.boundingBox);
        const p = points(state);
        return p ? p[what === "source" ? 0 : p.length - 1] : null;
    });
    // Each probe edits through the model, observes, and must restore exactly.
    // The edited cell is serialized per probe and the whole model once around
    // all probes, so files with large embedded assets stay affordable.
    const cellXml = cell => mxUtils.getXml(new mxCodec().encode(cell));
    const probe = (cells, item) => {
        const cell = cells[item.cell];
        const beforeXml = cellXml(cell);
        const before = observe(cells, item.watch);
        if (item.operation === "move" && !cell.geometry) return {status: "no_geometry"};
        const edits = [];
        const capture = (_, event) => edits.push(event.getProperty("edit"));
        model.addListener(mxEvent.UNDO, capture);
        let after, changed;
        try {
            model.beginUpdate();
            try {
                if (item.operation === "move") {
                    const moved = cell.geometry.clone();
                    if (moved.relative) {
                        moved.offset = moved.offset?.clone() ?? new mxPoint();
                        moved.offset.x += 23;
                        moved.offset.y += 17;
                    } else {
                        moved.x += 23;
                        moved.y += 17;
                    }
                    model.setGeometry(cell, moved);
                } else if (item.operation === "relabel") {
                    graph.cellLabelChanged(cell, "edit probe ✓", false);
                } else if (item.operation === "fold") {
                    model.setCollapsed(cell, !cell.isCollapsed());
                } else {
                    throw Error("Unknown probe operation");
                }
            } finally {
                model.endUpdate();
            }
            view.validate();
            if (item.operation === "relabel") {
                after = [String(graph.convertValueToString(cell))];
            } else {
                after = observe(cells, item.watch);
                if (item.operation === "fold") after = after.map(value => value != null);
            }
            changed = cellXml(cell) !== beforeXml;
        } finally {
            model.removeListener(capture);
            // Layouts can change other cells during the edit. Undo the whole
            // native transaction, including those recorded changes.
            for (let i = edits.length - 1; i >= 0; i--) edits[i].undo();
            view.validate();
        }
        const restored = cellXml(cell) === beforeXml &&
            json(observe(cells, item.watch)) === json(before);
        const delta = item.operation === "move" ? after.map((value, i) =>
            value && before[i] ? movement(value, before[i]) : null) : after;
        return {status: "done", changed_model: changed, restored, observed: delta};
    };
    if (request.operation === "snapshot") return JSON.parse(json(await snapshot()));
    if (request.operation === "probe") {
        await settle();
        const cells = walk();
        const modelXml = mxUtils.getXml(editor.getGraphXml());
        const results = request.probes.map(item => probe(cells, item));
        return JSON.parse(json({probes: results, model_restored: mxUtils.getXml(editor.getGraphXml()) === modelXml}));
    }
    throw Error("Unknown verification operation");
}
