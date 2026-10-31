# Git APFS: small-file speed and retained space

Measured 31 October 2026 on macOS 15.2 / arm64. APFS means **Agents Prioritized,
Files Shared**. This is a native Git C-source fork, with private verified clones
inside the checkout engine and no post-command compaction.

Small-file commands now run close to native Git on this machine. The interleaved
comparison is essentially tied; separate fixtures show a 2.6 ms switch penalty
and a slightly faster restore. These are modest differences, not statistically
established speedups or a guarantee for every repository.

## Small-file latency

2,000 files × 4 KiB; each agent edits 200 files. Three trial fixtures per operation,
four measured commands per variant in each fixture. Commands within a fixture
share the repository and are not independent trials. Medians include the whole
Git process. First status is measured separately and also reported as a combined
command-plus-status median.

| Workload | Native command | APFS command | Native command + status | APFS command + status |
| --- | ---: | ---: | ---: | ---: |
| Separate fixtures: switch | 65.45 ms | 68.08 ms | 77.29 ms | 81.45 ms |
| Separate fixtures: restore | 59.44 ms | 58.22 ms | 74.61 ms | 71.82 ms |
| Interleaved fixture: switch | 70.42 ms | 70.33 ms | 82.39 ms | 83.55 ms |
| Interleaved fixture: restore | 61.66 ms | 61.20 ms | 74.26 ms | 74.67 ms |

Separate fixtures use four worktrees. Interleaved fixtures keep four native and
four APFS targets live in one repository, with deterministic ordering varied by
repeat. Both arms start with CoW-shared worktrees, and setup is untimed. The fork's
default worker policy is measured; neither final comparison overrides workers.
Automatic Git GC is disabled in both fixtures to exclude background maintenance.

Large-file restore is approximately tied in the separate host-filesystem run:
native 174.11 ms, APFS 173.93 ms. Large-file switch remains sensitive to run/volume
state: native 22.03 ms versus APFS 89.90 ms on the host, but native 103.40 ms versus
APFS 14.40 ms in private-container storage trials. We do not claim a reliable
large-switch speedup. Storage-trial timing is secondary to the host latency run.

## Physical space

Median extra physical APFS allocation after the operation across three fresh
private-container trials. Four live agent worktrees, with approximately 10% of
files changed independently. Allocation is relative to the original source
checkout/object-store fixture and includes Git objects, refs, indexes, worktree
files and filesystem metadata. It is not logical `du` usage.

| Workload | Native Git | Git APFS | Less allocation |
| --- | ---: | ---: | ---: |
| Small switch | 13.82 MiB | 10.64 MiB | 23% |
| Small restore | 6.72 MiB | 3.60 MiB | 46% |
| Large switch | 96.77 MiB | 48.77 MiB | 50% |
| Large restore | 48.46 MiB | 0.45 MiB | 99% |

The large fixture has 128 files × 1 MiB; each of four agents changes 12 files.
Switch commits agent edits and returns to the shared base. Commit objects remain
allocated in both variants, explaining the remaining ~49 MiB. Restore discards
only selected working-tree edits and preserves an unrelated staged file and an
untracked note. Sharing survives without persistent caches or a compaction pass.

All 72 physical checkpoints stabilized, retaining raw samples and requiring three
equal readings after sync. Private images were detached and removed after trials.

## Implementation

- Removes redundant per-file donor HEAD/tree lookups. Requested Git blob identity,
  rather than donor HEAD/index state, determines whether source bytes are usable.
- Main-thread preflight resolves Git object type/size and replacement-object
  identity. Small-file filesystem reads and Git blob hashing run in bounded
  workers with private directory caches and independent hash contexts. Large-file
  literal byte comparisons remain on the main thread.
- Git object-store/config/index access and counters remain on the main thread.
  Batches contain at most 256 files and shrink according to the descriptor limit.
- Up to eight workers are selected for eligible batches of at least 100 entries
  only when another registered worktree is available on the same APFS volume.
  Explicit worker/threshold settings are respected; larger explicit worker counts
  use Git's existing process workers.
- Donors use no-follow opens, byte/hash verification and source metadata checks.
  Targets use fresh no-follow directory walks, a private random sibling clone,
  exclusive rename, fresh timestamps and actual stat data for Git's index.
  Unneeded chmod calls are skipped; read hints warm cloned data without writes.

Git retains dirty-file protection, staging, ref/index formats and hooks. Filters,
encoding/text conversions, symlinks, special file flags/xattrs, prefix/temp-file
checkout and files over 64 MiB use native writes. There is no persistent blob cache
or space benefit without a suitable registered donor. Native Git locks and the
usual requirement to avoid concurrent external filesystem writers still apply.

## Timer correction and provenance

The runner uses blocking `communicate()` with an independent process-group
watchdog. Python's `communicate(timeout=...)` can introduce polling-wait delays
after pipe EOF on macOS; a reproduction measured ~12 ms of extra wait. Historical
research latency reports used that older method and must not be mixed with these
final measurements. Physical-allocation measurements do not derive from timing.

These final latency and space reports all use the same two binaries, and their
hashes match the build manifest. Runner/source hashes are recorded in each raw
report. All eight patched core/build/test files exactly match the measured build
sources; there was no post-measurement code cleanup. Workspace paths in published
artifacts are replaced with `${WORKSPACE}` for portability/privacy.

The baseline is upstream Git v2.50.1, commit
`d82adb61ba2fd11d8f2587fca1b6bd7925ce4044`; the fork is `2.50.1.apfs.2`.
Both use the same make/compiler options, omitting gettext/Tcl-Tk while retaining
CLI remote helpers. This older pin matches the original experiments. This is an
experimental fork, not a current-upstream production release.

Validation: 32 local Python tests passed, including 20 native-fork regressions;
25 of those tests are packaged here (native fork, process runner and physical
measurement). 354 selected upstream Git tests plus eight new native APFS tests
passed (362 total). All 60 final benchmark comparisons passed: 24 separate latency,
12 paired small-file latency, and 24 physical-storage comparisons. Every measured
APFS checkout performed actual clones. The full upstream Git suite has not been
run locally. A macOS regression workflow is included for the packaged checks.

Coverage includes dirty and same-sized/restored-mtime donors, parallel batches,
low descriptor limits, explicit serial/disabled controls, SHA-256 repositories,
replacement objects, partial/source/staged-only restore, staged/untracked
preservation, modes/umask, symlinks and ancestor-link rejection, filters/hooks,
binary and unusual filenames, oversized-blob fallback and edit visibility.

## Artifacts and reproduction

- [Separate latency summary](results/latency/summary.md), [raw data](results/latency/results.json)
- [Paired small-file summary](results/paired/summary.md), [raw data](results/paired/results.json)
- [Physical storage summary](results/storage/summary.md), [raw data](results/storage/results.json)
- [Build manifest](results/build.json), [Git test log](results/native-tests.txt), [local Python log](results/local-python-tests.txt)
- [Build/use and implementation](native/README.md), [benchmark methodology](benchmarks/README.md)

```sh
python3 contrib/apfs/native/build.py
python3 contrib/apfs/benchmarks/checkout.py --repeats 3
python3 contrib/apfs/benchmarks/checkout.py --paired --profiles small --repeats 3
python3 contrib/apfs/benchmarks/checkout.py --mode storage --repeats 3
```
