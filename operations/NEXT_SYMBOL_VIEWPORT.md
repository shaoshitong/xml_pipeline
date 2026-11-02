# Current measured symbol integration

The immutable frontend v13 and generation guard v9 now reconstruct native symbol viewports in isolated scratch pages, sharing the exact native builder between legacy and enriched extraction. The original source page stays unchanged, and physical UA-shadow vector attributes, styles and layout quads bind each accepted instance. The source preflight on `6c1c25a2...` proved all 12 symbols and 190 objects in **8.34 s**.

The one actual development normal on this new source core (`79dc0b649fb4f508b9b41bb06ede66afc9d22f4dcc0d37d03631bf926af8b57b`) completed conversion and initial independent QA in **54.62 s**. Its initial QA rejected two opacity guards; the actual XML already had the correct `opacity=80`. No normal repeat is permitted. The failed result is preserved.

QA adapter v11/independent QA ro15 add a proof for single fill-only rect/circle/ellipse leaf opacity, requiring opaque ancestors, no use/marker contexts or effects, and exact native opacity. Group alpha and compound paint stay pending. Three genuinely mutated XML/PNG controls (text, geometry and opacity) were correctly rejected in **25.0–25.5 s**, and two existing positives passed full eight stages in **54.88 s and 66.47 s** while running concurrently.

The new symbol development candidate remains **pending** because the fresh native DOM order check found `v174`/`v178` painting after `v179`. All symbol geometry, source glyph/font and primitive-pixel gates passed; this is a separate retained paint-order failure, not a qualification. Strict main remains 886.

The planned next round reuses the frozen complete source audit and complex selection, takes fresh independent reservations, and runs twelve workers through the unchanged validation-to-mass gates. Do not redo the 26,754-source audit or the development normal.

---

# Next generic source repair

Current completed round: `svg_complex_actual_shadow_unseen100_20261102_v6`, 100 B / 100 C, C=6 qualified / 94 pending, zero infrastructure failures. No mass release because the unchanged 20% / five-increment / zero-regression gate did not pass. Five qualified architectures were value-screened and published; strict main is 886. Taxonomy `3ebc4b82...` remains held for layout quality. Arxiv acquisition/replay/reference and catalogue watcher remain independent.

Current generation core remains `compiler_svg_general_guard_v8` / frontend v12 / backend v10 / quality ro13, source core key `a55037567b7746db66cdb914ccbe3db71b0de337a5513d275ee760ab89287733`. Do not rerun source/core normals; the completed C ledger adds 100 consumed normals. Manual history catalog remains `release/compiler_iterations/source_core_attempts/manual_catalog_svg_actual_shadow_layout_20261102_v6.json`.

## Verified source-only prototype

`conversion/scripts/probe_symbol_viewport_layout_v4.py` is deployed and committed. Remote proof: `conversion/symbol_viewport_layout_probe_v4/380d7d97f1f4458682bfdc800bc26b13/summary.json`.

Development source: `6c1c25a290c58f50b7affe778c2f52dba94ffae8f91ac0172547cdbc186d74bb`; original SVG SHA256 `1523b11523e19a42fa4fbf14a48c5204c368256b8e296ee9bb273fce4299917f`.

All 12 vector symbol instances exactly reproduce actual Chromium UA-shadow path attributes, computed paint and physical CDP layout quads. All paint fits each source viewport; original page pixels remain exact. Real shifted-viewport, changed-fill and out-of-viewport mutations were rejected. These are source reconstruction controls, not conversion or full QA qualification.

Important observed causes:

- Cloning source IDs into the original document invalidates `<use>` references and can make captured UA node handles stale. Stripping the cloned root ID removed the real layout discrepancy. Descendant IDs/internal references currently require explicit remapping or typed deferral; do not silently drop them.
- `SVGSymbolElement.getScreenCTM()` from an actual UA shadow omits the symbol viewport mapping, while CDP layout quads reflect physical paint. Normalize the source linear transform algebraically from the source host matrix and native resolved `viewBox`/`preserveAspectRatio` dimensions; retain exact physical-quad checks.
- `getComputedStyle(svg).width` may be `auto`; use the resolved native SVG length as in the prototype, not a guessed dimension.
- A symbol must retain a real native nested `<svg>` viewport. A scaled `<g>` alone loses alignment/default sizing/clipping semantics.
- Perform reconstruction in a separate scratch page loaded from the same source DOM snapshot. Do not append cloned IDs or toggle display in the original source observer page. The prototype preserves original pixels exactly this way.

## Next concrete integration

Create immutable successors; do not modify current/frozen files. Likely free version slots: frontend v13, backend v11, guard v9, quality ro14, adapter v10, endpoint bridge v3, legacy DOM v9 and source-scene DOM v4 (verify existence first).

Extract the prototype's native source viewport builder/UA-shadow verification into a shared runtime module. Inject that exact builder into both legacy and enriched scene capture so source object IDs stay aligned. Feed fresh source-only symbol facts (resolved native viewport dimensions, source child markup, exact paint/layout proof, full-paint containment) to use expansion. Suppress an unproved-viewport issue only when the fresh complete containment proof actually succeeds. Leave cropped, nested/unproved, CSS-changing or unsupported cases pending.

Isolate source observations into scratch pages. Keep the original text-range/font observer on its unchanged source page; verify legacy/general object identities and original source pixels. Extend ownership proof only from fresh actual UA evidence, and preserve all independent source, marker geometry/editing, font, raster and strict-page gates.

Run one normal on a consumed development source under the genuinely new source core; freeze before calling, create an exclusive once claim, preserve its result even if rejected, then register the event in a successor manual history catalog. Follow actual terminal/full-eight results. Do not count source-only prototype success as conversion success.

After two real positive and two XML/PNG negative controls plus actual once-safe runtime dispatch controls, reuse full audit/seal metadata and reserve fresh unseen complex targets. Source-only preselection has 5,672 complex/dense sources, 2,365 applicable pending sources in the last pool, and a complete 26,754-SVG / 131,904-all-format provenance seal. `derive_complex_source_pool_v2.py` avoids repeating the full audit and pins a compact frozen target snapshot instead of rehashing the 160 MB source index every dispatch. Preserve the unchanged validation/release gates and 12-worker fixed program.

## Source content/value evidence

`svg_source_text_occlusion_review_v1.py` passed four real browser controls. Its read-only grapheme hit-stack audit flags 3 of the earlier 14 full-eight pairs, including both directly observed label occlusions. Review output: `clean/source_content_review_v1/ec79a8fdb3564e64aeadbecbec6f1380/summary.json`. The later six complex pairs had zero source-label occlusion flags; five were published after source rules and actual PNG spot inspection, while the taxonomy was held for overlapping boxes/routing. Do not equate full converter QA with scientific-value/content approval, or silently relabel earlier qualifications.
