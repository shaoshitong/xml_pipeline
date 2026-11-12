// Runs inside the pinned, offline draw.io editor.
(request, observe) => {
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
                // Each page has its own ID namespace, even when pages reuse 0 and 1.
                root = parse(mxUtils.getXml(root));
            } else {
                const body = mxUtils.getTextContent(page).trim();
                root = parse(body.startsWith("<") ? body : Graph.decompress(body.replace(/\s+/g, "")));
            }
        }
        if (root.nodeName !== "mxGraphModel") throw Error("Invalid native draw.io model");
        editor.setGraphXml(root);
        graph.clearSelection();
        // The interactive UI adds page padding when the editor has scrollbars.
        // Disable only that viewport behavior so page coordinates stay stable.
        graph.container.style.overflow = "hidden";
        graph.autoTranslate = true;
        view.scaleAndTranslate(1, 0, 0);
        graph.refresh();
        view.validate();
    };
    const rect = r => r && [r.x, r.y, r.width, r.height];
    const points = state => state?.absolutePoints?.map(p => p && [p.x, p.y]) ?? null;
    const cells = () => {
        const result = [];
        const visit = (cell, hidden) => {
            const vertex = model.isVertex(cell);
            const edge = model.isEdge(cell);
            const visible = !hidden && graph.isCellVisible(cell);
            const state = visible ? view.getState(cell) : null;
            const style = graph.getCellStyle(cell);
            const label = graph.convertValueToString(cell);
            const kind = vertex ? "vertex" : edge ? "edge" : cell.parent ? "layer" : "root";
            const selectedStyle = {};
            for (const key of [
                "shape", "rounded", "direction", "rotation", "fillColor", "strokeColor",
                "strokeWidth", "dashed", "dashPattern", "opacity", "fillOpacity", "strokeOpacity",
                "fontColor", "fontFamily", "fontSize", "fontStyle", "align", "verticalAlign",
                "startArrow", "endArrow", "startFill", "endFill", "startSize", "endSize",
                "edgeStyle", "curved", "container", "childLayout", "html", "whiteSpace",
            ]) {
                if (style[key] != null) selectedStyle[key] = String(style[key]);
            }
            result.push({
                id: cell.id, parent: cell.parent?.id ?? null, kind,
                source: cell.source?.id ?? null, target: cell.target?.id ?? null,
                visible: !!state && (vertex || edge),
                collapsed: graph.isCellCollapsed(cell),
                relative: !!cell.geometry?.relative, label: String(label ?? ""),
                style: selectedStyle, raw_style: cell.style ?? "",
                bbox: state && vertex ? rect(state) : null,
                paint_bbox: state && (vertex || edge) ? rect(state.shape?.boundingBox) ?? null : null,
                label_bbox: state?.text?.boundingBox ? rect(state.text.boundingBox) : null,
                points: edge ? points(state) : null,
            });
            for (let i = 0; i < model.getChildCount(cell); i++) {
                visit(model.getChildAt(cell, i), !visible || graph.isCellCollapsed(cell));
            }
        };
        visit(model.getRoot(), false);
        return result;
    };
    const settle = async () => {
        await document.fonts.ready;
        graph.refresh();
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        view.validate();
    };
    const snapshot = async () => {
        await settle();
        const bounds = mxRectangle.fromRectangle(graph.getGraphBounds());
        const image = graph.backgroundImage;
        if (image && image.width != null && image.height != null) {
            bounds.add(new mxRectangle(image.x, image.y, image.width, image.height));
        }
        return {bounds: rect(bounds), cells: cells(),
            editor_xml: mxUtils.getXml(editor.getGraphXml())};
    };
    const render = async (frame) => {
        await settle();
        // getSvg's fixed-page path paints the complete graph into these bounds.
        // Its native translate is floor(-bounds * scale) at border zero.
        const originalBounds = view.getBackgroundPageBounds;
        view.getBackgroundPageBounds = () => new mxRectangle(...frame.bounds);
        try {
            const background = graph.background || "#ffffff";
            const svg = graph.getSvg(background, frame.scale, 0, false, true, true,
                true, null, null, false, false, null, "page", null, false, true);
            const [x, y] = frame.bounds;
            return {svg: mxUtils.getXml(svg), transform: {
                scale: frame.scale,
                offset: [Math.floor(mxUtils.unscale(-x * frame.scale, 1)),
                    Math.floor(mxUtils.unscale(-y * frame.scale, 1))],
                pixel_ratio: window.devicePixelRatio,
                view_scale: view.scale,
                view_translate: [view.translate.x, view.translate.y],
            }};
        } finally {
            view.getBackgroundPageBounds = originalBounds;
        }
    };
    const probe = ({edge, label, node, end}) => {
        const e = model.getCell(edge ?? label);
        const n = model.getCell(node);
        const point = () => {
            if (label != null) {
                const box = e && view.getState(e)?.text?.boundingBox;
                return box ? [box.getCenterX(), box.getCenterY()] : null;
            }
            const p = points(e && view.getState(e));
            return p?.[end === "source" ? 0 : p.length - 1] ?? null;
        };
        const original = n?.geometry;
        const before = point();
        const nodeBefore = rect(n && view.getState(n));
        if (!e || !original || !before || !nodeBefore) return {status: "unknown"};
        const beforeXml = mxUtils.getXml(editor.getGraphXml());
        const moved = original.clone();
        const [dx, dy] = [23, 17];
        if (moved.relative) {
            moved.offset = moved.offset?.clone() ?? new mxPoint();
            moved.offset.x += dx;
            moved.offset.y += dy;
        } else {
            moved.x += dx;
            moved.y += dy;
        }
        let after, nodeAfter;
        try {
            model.setGeometry(n, moved);
            view.validate();
            after = point();
            nodeAfter = rect(view.getState(n));
        } finally {
            model.setGeometry(n, original);
            view.validate();
        }
        const restored = point();
        const restoredXml = mxUtils.getXml(editor.getGraphXml()) === beforeXml;
        const restoredExact = restoredXml && JSON.stringify(before) === JSON.stringify(restored);
        const nodeMoved = nodeAfter && Math.hypot(nodeAfter[0] - nodeBefore[0],
            nodeAfter[1] - nodeBefore[1]) > 1;
        if (!after || !nodeMoved || !restoredExact) {
            return {status: "unknown", before, after, restored, restored_exact: restoredExact};
        }
        const delta = [after[0] - before[0], after[1] - before[1]];
        return {
            status: Math.hypot(...delta) > 1 ? "moved" : "stationary",
            delta, before, after, restored, restored_exact: restoredExact,
            node_delta: [nodeAfter[0] - nodeBefore[0], nodeAfter[1] - nodeBefore[1]],
        };
    };
    return (async () => {
        load(request.xml, request.pageNumber ?? 1);
        if (observe) return observe({request, editor, graph, model, view, points, settle});
        switch (request.operation) {
            case "snapshot":
                return snapshot();
            case "render":
                return render(request.frame);
            case "repair": {
                // Attribute changes introduced by the codec are excluded from
                // rule evidence by capturing the same codec before and after.
                const before = mxUtils.getXml(editor.getGraphXml());
                const rules = graph.normalizeModel();
                return {before, rules, after: mxUtils.getXml(editor.getGraphXml())};
            }
            case "probe":
                return request.probes.map(probe);
            default:
                throw Error("Unknown drawio-compare operation");
        }
    })();
}
