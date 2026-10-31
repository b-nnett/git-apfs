# Native Git APFS builds and benchmarks

Git APFS is compiled from Git v2.56.0 with an APFS checkout patch. The `git`
executable uses Git's own built-ins; no command wrapper or post-command
compaction is involved. The earlier Go allocator is a separate experiment.

```sh
python3 native/build.py --jobs 4
benchmark-results/git-apfs/bin/git --version
benchmark-results/git-apfs/bin/git -C /path/to/repo apfs doctor
python3 -m unittest discover -s tests -v
```

`upstream.json` pins the upstream object, branding, compiler options and patch
SHA-256. The builder exports clean source archives into private directories and
installs matched native/APFS binaries under `benchmark-results/`. Both use
`NO_RUST=YesPlease NO_GETTEXT=YesPlease NO_TCLTK=YesPlease`, including Git's C
fallback without Cargo and normal CLI remote helpers. Python 3.9+, macOS developer
tools and make are required. Build manifests record executable hashes and logs.
System Git and global configuration are untouched.

## Controls and eligibility

The checkout hook accepts regular files up to 64 MiB whose conversion attributes
preserve their bytes, including LF text. It resolves replacement objects, checks
blob type/size and streams the canonical SHA-1/SHA-256 identity. Donors are
opened without following symlinks and checked for identity/metadata changes.
Private `fclonefileat` output is published exclusively, given fresh timestamps
and fed back into normal Git index updates. Unsupported attributes/metadata and
unavailable or changed donors use native writes. Post-publication errors fail.
Donor search hints only affect order; every selected snapshot is verified.

Batch capacity is capped at 256 and adapts to the file-descriptor limit. Object
lookup/index/config work remains on the main thread. Filesystem/hash workers
use independent contexts. Automatic worker leases share a per-repository budget
of eight **auxiliary threads**; caller threads are additional. Set
`apfs.workerBudget` to 0..64. Explicit `checkout.workers` overrides that budget.
Large batches (at least two files and 8 MiB) can run below the default count
threshold; explicit `checkout.thresholdForParallelism` wins.

`git apfs doctor`/`status` prints read-only JSON. `GIT_APFS_TRACE_JSON=1` adds
per-process diagnostics to stderr, including donor rejection events (which can
count several probes per file), cloned bytes and worker lease events.
`GIT_APFS_PROFILE=1` adds phase durations; summed parallel work exceeds wall time.
`GIT_APFS_CLONE_CHECKOUT=0` disables cloning and cache population.

`git apfs tune` explicitly configures native FSMonitor and untracked cache.
Always compare against upstream with the same settings. With APFS cloning or a positive
`apfs.cacheLimit`, FSMonitor is bypassed for safe normal stat validation: stress
tests exposed missed external edits with concurrent APFS checkout workloads. The
FSEvents interaction remains unresolved; `cache.fsmonitor_stat_guard` reports the
guard. Configuration remains intact and untracked cache still works.

## Optional cache

`apfs.cacheLimit` defaults to zero. Set a positive byte limit (k/m/g suffixes
accepted) to retain snapshots under the private common Git directory's
`apfs-cache/v1`. `git apfs cache warm` seeds matching tracked files; checkout and
add also populate it. Reads reverify content. A nonblocking writer lock avoids
competing mutation; FIFO eviction charges max(allocated file blocks, 4096) per
entry, plus separate directory/lock metadata. Shared extents are conservatively
charged more than once. A later writer enforces a reduced quota; `cache prune`
removes owned entries immediately if it obtains the lock. Unknown files and
links are preserved. Cache initialization, warm-up and post-cleanup retention
are costs, not free savings.

## Benchmark methodology

```sh
python3 benchmarks/checkout.py --mode latency --paired --repeats 3
python3 benchmarks/checkout.py --mode storage --repeats 3
python3 benchmarks/checkout.py --profiles large --mode latency --paired --profile --settle-seconds 1.1
python3 benchmarks/agents.py --source /path/to/repo --ref COMMIT --agents 1,8,32 --repeats 3
python3 benchmarks/agents.py --source /path/to/repo --ref COMMIT --agents 1,8,32 --mode storage --repeats 1
```

The synthetic runner isolates switch/restore and follows each with status. Four
worktrees per variant start CoW-shared, isolating command allocation. Paired
latency runs interleave variants in one fixture. Settled/profile runs are separate
from normal latency measurements. The real-repository runner clones a pinned
source into an isolated fixture, then concurrently creates, edits, diffs, stages,
commits, dirties/restores, switches and cleans up worktrees. It checks contents,
source isolation, final cleanliness and worker lease balance.

Six agent variants separate native/APFS, equal FSMonitor/untracked-cache tuning,
and optional cache (whose tuned variant reports the FSMonitor guard). Warm-up
cost is explicit. Command distributions are descriptive: commands share the
same fixture and are not independent samples. `/usr/bin/time -l` records CPU and
peak RSS of each timed command, excluding persistent monitor daemons. This is
not aggregate process-tree peak RAM. First status includes daemon startup.

Storage runs use disposable private APFS sparse-image containers and wait for
stable allocation readings. Source, warmed cache, retained worktrees and cleanup
are measured; cache storage remains included after worktree removal. A 100 ms
allocation sampler provides a peak **lower bound**, not an exact transient peak.
`st_blocks` diagnostics are not unique physical allocation. Latency runs use the
host filesystem with warm caches; no global cache purge is attempted. Raw JSON
records source revisions, parameters, diagnostics, hashes and failures. Failed
trials are retained in reports and excluded from timing summaries.

Git APFS remains experimental; targeted tests do not replace the full upstream
suite. See the published results for measured tradeoffs and validation counts.
