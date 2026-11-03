# Direct arXiv collection on HKUST1–5

The confirmed baseline is `clean/accepted_3759_v1/pairs.jsonl`, SHA256
`913624deb45c1f9b0e72bc25ba0c7b643700e7566e00ac27237f11ed7eb639f2`.
The phase target remains 500 additional valuable complex editable pairs; merely
recovered XML or completed downloads do not satisfy it.

The direct pipeline replaces failing legacy search requests with official OAI-PMH
arXivRaw metadata, filtered by first submission date (2023 onward), not OAI modified
date. Last author version is pinned. Cached official responses are reused. Failed
metadata and source requests remain pending; failed partitions are never complete.

A same-process RLock now spans telemetry generation and route correction. This
fixes a real concurrent `.tmp` rename race that stopped the single-node collector.
The old source and PDF once ledgers and cumulative 512 GiB source budget remain.

`arxiv_cluster_broker_v1.py` runs on HKUST3's campus IP, authenticated by a task
private configuration under `conversion/private_arxiv_cluster_v1/` (never Git).
Five contiguous SHA256(arxiv_id) intervals assign every paper/version to exactly
one node. Each worker uses eight direct download threads and eight native import
workers. The server grants a global fulltext request slot every .34 seconds and
shared cooldown after 403/429/503. Metadata acquisition remains serial.

A central SQLite PDF claim commits before any official invocation. Each node has
its own local SQLite, never a shared database on NFS. A committed PDF claim is
never reassigned automatically after interruption. Worker artifacts remain on the
remote data disk until an authenticated LAN upload has verified every file hash,
installed canonical relative paths, and committed the original HKUST3 ledger.
Existing source-replay QA then consumes the unchanged official-import results.

Source-body blocks reserve budget before receipt, conservatively including short
reads and interrupted transfers. These reservations are cumulative, distinct from
actual received bytes tracked in worker heartbeats. The resource guard includes
the persistent cluster reservation counter without resetting older epochs.

Runtime, pinned official draw.io WAR/JS, Chromium and fonts are distributed from
HKUST3 over the campus LAN, never through VPS or Mac bulk relay. Node-specific
greenlet wheels for Python 3.13 stay remote. Short owned /tmp symlinks point to
remote data-disk temporary directories to avoid Chromium UNIX socket path limits.
No system proxy, DNS, Mac app settings, or VPS configuration is changed.

Entry points: `prepare_arxiv_cluster_runtime_v1.py`,
`start_arxiv_cluster_broker_v1.py`, `deploy_arxiv_cluster_nodes_v1.py`,
`transition_arxiv_cluster_v1.py`, `start_arxiv_cluster_nodes_v1.py`.
The transition gracefully drains only the owned single-node collector and meters
its final counters before creating a new launch epoch. It never clears queues.

Reports on HKUST3:
- `clean/arxiv_research_figures_v1/cluster_direct_v1/progress.json`
- `clean/arxiv_research_figures_v1/goal500_progress_v1/current.json`
- `clean/arxiv_research_figures_v1/goal500_progress_v1/baseline_plus_accepted_new.jsonl`

The goal publisher deduplicates code SHA + actual dimension-prefixed RGBA pixels.
Source-replay and registered-original-PDF quality views are counted separately.
A structural policy never approves future figures: each accepted figure must be
on the explicit visually reviewed allowlist. Two inspected method/framework
figures are approved in this phase; one predates the sustained direct launch.
Dialogue/story examples remain held. Final 500-pair acceptance and a new random100
preview are outstanding.

Validation: a temporary-root integration test exercises 50 concurrent requests for
one global PDF claim, 50 retries of one byte reservation, preservation of old
budget usage, idempotent enqueue and all five non-overlapping shard deliveries.
Production validation additionally requires two measured byte/paper/result deltas
and checks for actual errors. Startup or heartbeat alone is insufficient.

Update 2026-11-03 08:00 UTC: all five nodes are deployed and have real source-byte
and paper-progress observations. HKUST4/5 completed their initial cached metadata
shards fastest. HKUST1/2/3 are slower; their source speed floor is now disabled and
a 600-second stream watchdog preserves partials instead of imposing 64 KiB/s.
Transient truncation, HTTP 408 and server 5xx remain network pending, not completed
papers. Worker handover freezes only the owned task process group and verifies no
active paper/PDF claim before restarting; partials and outboxes stay intact.

OAI returns HTTP503 for the current October token and fresh November partitions.
The feeder now prioritizes untouched partitions over repeatedly failing ones.
The failures remain pending; no metadata-exhausted or 500-pair completion is claimed.

A generic official-renderer issue affected 518 preserved author-XML recoveries:
math was disabled in the old Editor initialization. A versioned math renderer
loads only the official offline bundle from the same pinned WAR. The official
MathJax SVG font cache is disabled to avoid changing per-export glyph IDs; all
existing exact model, topology, SVG and actual PNG/RGBA restoration gates remain.
A fresh synthetic formula passed those unchanged strict gates.

`arxiv_math_source_repair_v1.py` selects 2023+ structurally valuable unprocessed
source-replay cases from that preserved XML. It never invokes a PDF importer and
never alters old failures or accepted payloads. The new once ledger uses queued
and committed attempt states; saved child results are recovered without repeating
conversion after controller handover. It has two cold source-replay workers.

The first measured recovery batch produced 34 fully verified source replays.
Many other recovered XML files fail the existing exact model/pixel restore gates
and remain pending; enabling math does not make them acceptable automatically.
A snapshot-restore v2 prototype failed its fresh source probe and is not deployed
as the production recipe. Final scientific-value review is still required for
each newly accepted goal500 pair. The goal remains active and below +500.

Update 2026-11-03 08:12 UTC: partial OAI recovery is now demonstrated by actual
new direct XML page receipts. The CV partition enqueued 1047 then 1253 distinct
jobs; cached/prefetched repeat enqueue attempts add zero. Another HTTP200 page
hit the old 240-second body deadline before completion. The serial metadata
transfer deadline is now 600 seconds, with a 100 B/s for 30 s stall guard and the
same 16 MiB cap. Incomplete XML still never advances the cursor. The feeder now
closes its unused converter pool; only the five workers supply the 40+40 pools.

Forty-five complete source-replay figures were actually inspected in contact
sheets `review_20261103T080117Z`. Thirty-one were individually accepted; fourteen
small, simple, near-variant or unreadable figures were held. Together with the
prior two figures, the fixed-baseline-relative accepted count is 33 and the
unified index contains 3792 rows (not +500 complete). The exact source/PNG hashes,
sheet hashes and per-figure rationale are in the individual review JSON. New
future candidates remain unapproved until a later actual review.

The math recovery ledger measured 34 verified source replays earlier, then 44
verified and 190 pending. A pending result failing exact model/PNG restore is not
counted. All these recoveries add zero PDF-import calls and zero model calls.

Update 2026-11-03 08:59 UTC: a second individually inspected batch accepted 7 of
10 figures. Three near-variant mammography architectures remain held in favor of
the complete, detailed registration architecture. Accepted new count is 40.

A static audit of an old failed formula figure established unchanged source-cell
geometry but differing serialized viewport dx/dy, 1-pixel label widths and SVG
edge-routing coordinates. A fresh synthetic wide/negative-coordinate math figure
reproduced failure of the unchanged validator; applying a uniform identity view
(scale 1, translate 0, scroll 0) before all validation stages made every original
exact model/topology/SVG/PNG/RGBA restore gate pass. A previously unvalidated real
source then passed under the same adapter with zero PDF-import/model calls.

`arxiv_math_viewport_validation_v1.py` continues only prior source-validation
failures with identical original/restored source-cell inventories, pinned physical
fonts and closed resources. It uses a new per-protocol once ledger and preserves
the prior PDF conversion, author XML, failed proof, failure record and baseline
payloads. Old source/proof hashes are checked before and after. Source recipes are
pinned and checked in each bounded worker. No original-PDF fidelity is inferred.
The first real observation verified 19 additional source replays, with other
failures still held; these are not counted as accepted scientific figures until
individual visual review. The new manifest is included in the goal publisher.

Evidence paths:
- `clean/arxiv_research_figures_v1/math_viewport_protocol_selftest_v1/results.json`
- `clean/arxiv_research_figures_v1/math_uniform_viewport_probe_v1/`
- `clean/arxiv_research_figures_v1/math_viewport_source_replay_v1/{policy,summary}.json`


2026-11-03 09:32 UTC update: 125 individually inspected figures produced 88 explicit accepts and 37 holds; authoritative accepted-new index now has 128 rows, unified total 3887. This is source-replay acceptance; original-PDF fidelity remains a separate overlapping view. New random100 preview and +500 final acceptance remain outstanding.

HKUST4 and HKUST5 stopped at 09:02 / 09:13 UTC on UnicodeEncodeError during performance JSON writes: archive member names contained surrogateescaped non-UTF8 bytes. Worker-local atomic JSON writer now uses JSON Unicode escapes (lossless Python string roundtrip) and unique temporary files. Existing PDF/paper ledgers and partial archives remain; completed PDF imports are skipped on recovery. Both stopped processes were relaunched from preserved state; other nodes use the existing verified idle-only handover, never interrupting an active paper/PDF import.


2026-11-03 09:44 UTC: added 20 accepts from 25 individually reviewed figures. Cross-figure overview caught two near variants previously accepted in the 125-figure batch; these were explicitly revoked with a correction batch (artifacts retained). Accepted-new index is now146, unified3905. Replay of an already-applied review batch is now a no-op, tested against the old 88-accept batch: later corrections and total146 preserved.

Uniform random100 milestone: frozen population146, index SHA b3777fb1714f65c00be77a4778b8a6d1b2c22c80eab4498625bbb40934b8af34, seed20261103100, no visual replacement. Archive clean/review_samples/random100_new146_seed20261103100_v1.zip, SHA391a11e26db07b8aed2bf0a19bee747c4832a514c9ae5a6d8a4177b0ab306abe. All307 packaged files and PNG/code/pixel/proof hashes checked remotely. Fonts remain declared runtime dependencies. This preview does not certify original PDF fidelity or finish the +500 goal. The earlier128-population sample is superseded and retained remotely for audit only.


2026-11-03 10:01 UTC: HKUST4 public TCP egress stopped working around09:45: both arXiv151.101.131.42 /151.101.195.42 timed out on4 while5 connected to both in~55ms; an independent public destination also failed on4. Default gateway/interface remained present. This is not evidence of an arXiv HTTP rate rejection; upstream root cause beyond the host has not been identified. No system route/DNS/proxy was changed.

Task-local fallback now serves HKUST4 source GETs through authenticated HKUST3 LAN port60572. Only exact https://arxiv.org/{abs,src}/versioned-id is allowed; upstream uses the existing HKUST3 direct exit. Raw bytes, compression and Range headers are preserved. Worker4 retains8download+8native threads, original global rate/cooldown/budget and unchanged PDF once claims/import/QA. Other nodes still use direct GET. Source transport selector is an HKUST4-only field in the private mode0600 config; no credentials are in Git. Launcher+idle helper updated only on4; other workers retain their previous launcher revision, same current core worker.

Loopback fixture verified raw compressed bytes,206Range, authorization, URL restrictions, and existing budget stop with zero external requests. Idle handover verified0active papers/0active PDF imports; partial files and outboxes preserved. First real observation10:01UTC: worker4 new launch processed16papers and received12,335,286 source bytes; broker total1245 ingested. Relay requests showed200source responses. Old TCP failures remain pending rather than completed.


Second recovery observation10:02UTC: HKUST4 new launch28papers /24,440,953source bytes, gains+12papers/+12,105,667bytes over the first observation. Broker1257 ingested. The sole relay BrokenPipe was traced to2610.20512v1: official/src returned PDF content type; the unchanged worker intentionally rejected it before reading body (typed_skip_source_attempt), not a transport retry. All five actual worker identities/core helper hashes and39 canonical source files verified.


2026-11-03 10:16 UTC: three additional figures individually accepted; approvals149. Diagnosed33 of40 viewport-protocol pending cases: model/geometry/pixels/PNG restore exact, SVG differs solely in official random drawio-svg-<GUID>-gradient namespaces. New renderer gives the official Editor.guid a deterministic source-hash/ordinal allocator only during synchronous getSvg, restores it in finally, and leaves source XML/model and the exact original acceptance comparator unchanged.

Fresh gradient+math synthetic A/B: random exporter fails only strict SVG; deterministic exporter passes model/SVG/RGBA/PNG gates with equal geometry inventory. New stable_export_source_replay_v1 controller selects only proven namespace-only old failures, pins old proof/record/SVG/PNG files and source recipes before/after, claims a new versioned source-validation once record, and never calls PDF import or models. Seven failures in other gates remain untouched. Main five collection workers and old ledgers are preserved. No new-source automatic acceptance: successful rows enter the unchanged individual visual policy.


2026-11-03 10:25 UTC: stable exporter verified16cases then33cases. Independent audit:33/33 old PNGs byte-identical;33/33 initial geometry inventories unchanged;33/33 prior proof/record/SVG/PNG hashes unchanged;33/33 original strict replay gates pass. Visual review batch35:28accepted/7held, including same-paper comparison references. Combined approval count177 (3759+177=3936 once publisher updates).

Read-only direct-author-XML inventory found125 .drawio files,13 meeting the unchanged value structure policy. Three are exact/decoded duplicates of already processed graphs;10 are unseen source graphs. Inventory performs0source replays/0PDF imports/0model calls and none are counted. Further processing requires archive provenance, resource closure and the exact source replay gates; do not treat native XML presence as a product.


2026-11-03 10:42 UTC: added a direct author-XML branch for native .drawio members previously omitted by the PDF-only source scanner. Uses preserved remote archives only, never downloads/imports PDFs or calls models. Requires an original terminal source-completed paper record, original2023+ AI publication metadata, frozen source archive/receipt hashes, exact unique safe TAR-member bytes for XML and every relative asset, unchanged raw XML, unchanged complex-value policy, font byte pins and the same strict official stable-export edit/restore gates. Graph SHA once claims prevent duplicate validations. Failures stay pending, never accepted automatically.

Archive fixture passes exact membership and rejects tampered/duplicate/escaping/wrong-member payloads without external requests. Source branch writes its own ledger/manifest under direct_author_XML_source_replay_v1; old PDF/source ledgers untouched. Original-PDF correspondence and actual paper-figure usage are explicitly uncertified for these standalone author sources. Publisher reads this sixth source only through the existing review allowlist. Random sampler handles absent original-PDF references and percent-encodes source filenames while preserving file bytes.


2026-11-03 10:51 UTC observation: direct-author branch8verified/2pending. Eight paired code files independently passed resource closure without a PDF context. Two pending causes: external CTAN fontSource in2302.14696v3, Text-backend node-binding change in2407.19922v1. Neither was retried or counted. Visual batch20 accepted13/held7, including three of the native author-source figures; draft canvases, large gaps, near variants and overlap were excluded. Publisher approval set190; wait for authoritative current index before reporting190.


2026-11-03 marker inventory: bounded first scan read8715PNG/89SVG headers and found141 native XML markers in55seconds; directory walk incomplete. No pixels decoded, no downloads/import/replay/model calls. Markers are not parsed/qualified products. New v2 scanner persists a frozen filename cohort in its own SQLite queue and commits500-file checkpoints, so continuation does not rescan the same prefix forever. Existing v1 partial inventory is retained. Next step is official embedded XML extraction, graph duplicate detection and unchanged strict source QA plus individual review; none of these141 markers is counted yet.


2026-11-03 v2 actual progress: frozen cohort246,034source SVG/PNG filenames. At11:03:33UTC3500checked/37markers; at11:05:51UTC105,000checked/1712markers,141,034stillqueued. Same live PID1843921 verified by birth ticks1149548885. These remain unparsed marker candidates, not products. The scan performs no pixel decoding, network download, PDF import, source replay or model call.


## Latest user-directed embedded XML compiler workflow (2026-11-03)

User authorizes one DeepSeek Harness command-line coding session, using the already installed HKUST3 runtime, to implement deterministic SVG/PNG extraction, graph deduplication and automatic edit/render/restore gates. No virtual mouse, per-image LLM calls or further agents. This supersedes manual per-image visual review for this new branch; deterministic quality diagnostics and all existing strict replay/source/resource/font gates remain. Existing190 accepted pairs stay immutable until separately reviewed integration. Frozen inventory has completed246034 file checks with3946 metadata markers; those are not accepted pairs. The isolated remote workspace is `/backup/shaoshitong/img2code_20261029/conversion/dpsk_svg_png_compiler_20261103`; CLI launch/inspection/brief source is on branch `codex/dpsk-svg-png-compiler`. Inspect `launcher_status.json`, actual tool events, generated source and `embedded_XML_compiler_dpsk_v1/status.json`; a launched or thinking process is not sufficient evidence.
