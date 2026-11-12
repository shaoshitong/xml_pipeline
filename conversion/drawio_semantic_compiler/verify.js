// Runs inside the pinned, offline draw.io editor. Reports the editor's own
// model, view and edit behaviour for one page of a document.
(request) => {
    const editor = window.__bulkUi.editor;
    const graph = editor.graph;
    const model = graph.getModel();
    const view = graph.view;
    const parse = xml => mxUtils.parseXml(xml).documentElement;
    const load = (xml, pageNumber) => {
        let root = parse(xml);
        if (root.nodeName === "mxfile") {
            const page = [...root.children].filter(child => child.nodeName === "diagram")[pageNumber - 1];
            if (!page) throw Error("Missing native draw.io page");
            root = [...page.children].find(child => child.nodeName === "mxGraphModel");
            if (root) {
                // Each page has its own ID namespace.
                root = parse(mxUtils.getXml(root));
            } else {
                const body = mxUtils.getTextContent(page).trim();
                root = parse(body.startsWith("<") ? body : Graph.decompress(body.replace(/\s+/g, "")));
            }
        }
        if (root.nodeName !== "mxGraphModel") throw Error("Invalid native draw.io model");
        editor.setGraphXml(root);
        graph.clearSelection();
        graph.container.style.overflow = "hidden";
        graph.autoTranslate = true;
        view.scaleAndTranslate(1, 0, 0);
        graph.refresh();
        view.validate();
    };
    const rect = r => r ? [r.x, r.y, r.width, r.height] : null;
    const points = state => state?.absolutePoints?.map(p => p && [p.x, p.y]) ?? null;
    const settle = async () => {
        await document.fonts.ready;
        graph.refresh();
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        view.validate();
    };
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
            JSON.stringify(observe(cells, item.watch)) === JSON.stringify(before);
        const delta = item.operation === "move" ? after.map((value, i) =>
            value && before[i] ? value.map((v, k) => v - before[i][k]) : null) : after;
        return {status: "done", changed_model: changed, restored, observed: delta};
    };
    return (async () => {
        load(request.xml, request.pageNumber ?? 1);
        if (request.operation === "snapshot") return snapshot();
        if (request.operation === "probe") {
            await settle();
            const cells = walk();
            const modelXml = mxUtils.getXml(editor.getGraphXml());
            const results = request.probes.map(item => probe(cells, item));
            return {probes: results, model_restored: mxUtils.getXml(editor.getGraphXml()) === modelXml};
        }
        throw Error("Unknown verification operation");
    })();
}
