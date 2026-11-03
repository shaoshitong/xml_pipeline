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
