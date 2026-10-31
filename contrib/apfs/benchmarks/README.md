# Git APFS benchmarks

For the native replacement Git fork, start with the “Native Git APFS switch and
restore” section below. The original allocation/command experiments remain
available for comparisons and historical results.

## Earlier worktree workflow benchmark

Run from the project root with Python 3. No Python dependencies are needed.
Reference binaries must be built or supplied explicitly. The build helper uses
installed Go/Rust toolchains, downloads their declared dependencies as needed,
and skips unavailable compilers without installing them:

```sh
python3 benchmarks/build-tools.py
python3 benchmarks/bench.py
```

Each run writes `benchmark-results/run-*/results.json` and `summary.md`.
Results include commands, stdout/stderr, per-phase wall times, failures,
executable paths and hashes, reference revision manifest, and host information.
Missing or unlaunchable executables are skipped with reasons. A tool rejecting a
scenario is recorded as `rejected`, distinct from passing it. Exit status is 1
for correctness failures or harness errors, 2 when nothing ran, and 0 otherwise;
**0 does not mean every tool supports every scenario**. Inspect coverage.

## Workflows

| Case | What it exercises |
| --- | --- |
| same | Fresh tool cache and a subsequent allocation from the same repository |
| divergent | Requested target changes 10% of synthetic source files, deletes one, and adds a file |
| dirty | Local modifications and an untracked source file must not become destination changes |
| collision | Existing destination sentinel must survive a rejected allocation; registrations must not leak |
| hook | Post-checkout runs exactly once with the destination as cwd |
| warm-build | Ignored dependency tree and deterministic incremental build outputs; fake `.env` must not be copied |
| parallel | Multiple branches/paths allocated concurrently against the same tool cache |

Successful allocations are checked against a native Git checkout for tracked
bytes, executable bits and symlink targets, as well as HEAD and initial status.
Every successful allocation also gets a same-length edit with restored mtime to
challenge change detection, a source-isolation check, and timed native Git
removal. Failing the edit-detection policy is visible even if a tool deliberately
relaxes Git's stat checks. Mutation and removal checks happen **after** first
status/build timings.

Collision tests record branch changes as diagnostics, not failures: native
`git worktree add -b` itself can create the branch before rejecting an occupied
destination. Requested branch leaks and stale registrations on other failed
allocations are failures. Retained partial destinations are reported as failures
with recovery evidence; that does not imply deleting them would be safer.

The built-in build is a hermetic content-addressed stand-in: one output digest
per package, rebuilt only when its sources change. Rebuilt-package counts show
whether warmed outputs were reused. It is **not a compiler benchmark**.

## Representative fixture sizes

Small smoke run:

```sh
python3 benchmarks/bench.py --tools git --files 100 --repeats 1
```

Many-small-file monorepo, including larger dependency warmup:

```sh
python3 benchmarks/bench.py --files 20000 --file-bytes 4096 --dependency-files 5000 --repeats 5
```

Large tracked asset workload:

```sh
python3 benchmarks/bench.py --files 128 --file-bytes 1048576 --cases same,divergent,parallel --repeats 5
```

Override binaries and select tools/cases:

```sh
python3 benchmarks/bench.py --tools git,cowtree --tool cowtree=/absolute/path/to/cowtree --cases same,divergent,hook
```

## Actual repositories and builds

Use a local repository as the committed source. The harness makes an independent
clone with no hardlinks; it does not edit the supplied repository or copy its
uncommitted/ignored files. Use an argv array for builds; no shell is involved:

```sh
python3 benchmarks/bench.py --repo /absolute/path/to/project --tools git,cowtree --cases same,divergent,parallel --build-command '["npm","run","build"]' --timeout 600 --repeats 3
```

Commands must work in a fresh committed checkout; for dependency setup, supply a
project-owned script as argv (for example `["./scripts/benchmark-build"]`).
The first and second executions are timed separately. Setup is included if the
script does it. Builds execute project code and may access the network; the
harness is filesystem isolation, **not a security sandbox**.

In real-repo mode, the divergent target adds a benchmark file; only repositories
matching the synthetic `packages/*/src/*.txt` layout also receive the synthetic
10% edits/deletion. The warm-build case always adds the artificial dependency
and digest workload, so use actual build timings for performance conclusions.
Submodules and Git LFS hydration are not automatically initialized. Repository
hooks and user/global Git settings are not imported. A future profile can
explicitly provision those dependencies and checkout conversions.

## Measurement and isolation

- Tools run in seeded randomized order, with separate private repositories per
  tool/case/repetition. Fresh/reused means **tool-cache state**, not cold RAM or
  cold disk: OS caches are not flushed. A warm allocation follows removal of
  the previous worktree while the tool's baseline/template cache remains.
- Parallel results include total workflow batch wall time (validation, edits,
  builds and removal included) and individual allocation times. This tests different destinations/branches; same-path contention and
  interrupted-creation fault injection remain future cases.
- Aggregate medians include only allocations that passed all checks; rejected
  or incorrect allocations do not contribute speed results. Raw JSON separates
  cache states and contains second-status/build timings and rebuild counts.
  Do not rank tools using a combined fresh/reused median alone.
- Free-space deltas are volume-wide, noisy diagnostics. They are **not** measured
  exclusive CoW allocation. No `du`-based savings claim is made. Choose a quiet
  scratch APFS volume with `--work-dir /Volumes/Bench/results`; diskutil output is
  recorded. The suite can also run on other filesystems to exercise fallbacks,
  but does not claim that the tool actually used CoW based on speed alone.
- Configuration is isolated through child-process Git configuration variables,
  per-fixture cache paths, and a private git-cow template. User HOME is unchanged.
  Child commands get timeouts and process-group termination. Tools that detach
  into independent sessions cannot be reliably reaped by this mechanism.
- Scratch repositories are removed after each case. Use `--keep` to inspect
  partial worktrees and caches; the entire retained run directory is disposable.
  Avoid running unrelated processes inside scratch repositories.
- The recorded revision manifest reflects our pinned reference clones. An
  overridden executable's path/hash is authoritative for what actually ran;
  the manifest does not attest that the binary was built from those revisions.

## Harness validation

```sh
python3 -m unittest discover -s tests -v
```

Tests require native Git. They run every built-in workflow against native Git,
then verify that intentionally broken test adapters are caught for wrong
checkout contents and destination deletion. The test adapters operate only on
temporary fixtures.

Next coverage priorities: conversion/filter cache invalidation, SHA-256 and
index-format profiles, interruption/fault injection, same-destination contention,
real dependency-cache reuse, and controlled APFS physical-storage measurement.

## Controlled physical-storage comparison

```sh
python3 benchmarks/storage.py --cowtree benchmark-results/tools/cowtree --repeats 3 --worktrees 4
```

This macOS-only runner creates a fresh private 4 GiB sparse APFS disk image for
each tool/profile/repetition. Only the benchmark uses its container. It records
`CapacityCeiling - CapacityFree` via `diskutil apfs list -plist`, synchronizes,
and waits for three identical readings (with a bounded retry and raw samples).
No user volumes are reformatted or changed. Images are detached and deleted
when each trial finishes; a failed detach retains the image for recovery.

Profiles use 2,000 × 4 KiB files and 128 × 1 MiB files with deterministic
pseudorandom payloads. Source checkout and Git object storage are measured before
adding worktrees. All worktrees remain present together, with checkpoints after
each allocation. The runner then rewrites approximately 10% of files independently in every
worktree and measures growth, verifies source isolation, removes worktrees,
and records remaining allocation. Initial tracked bytes/modes/links and status
must match the source. This isolates marginal container block allocation,
including metadata, rather than summing clone files' misleading `du` sizes.

Read `storage-*/summary.md` alongside workflow timings. JSON includes raw
checkpoint samples, source/setup allocation, mutation growth, removal residuals,
commands/timings, volume identity and executable hash. Image-backed timing can
differ from native-volume timing. Container allocation is not flash-device write
amplification or sparse-image host allocation. Fresh images have no user
snapshots; filesystem bookkeeping still contributes to measurements.

## Experimental allocator

`apfs-worktree` is now an available adapter. The build helper compiles the local
Go implementation as well as reference tools. Its verified fallback uses
`benchmark-results/tools/cowtree` when present, or the explicitly configured
`APFS_WORKTREE_COWTREE`. Output records the actual fast/fallback mode.

The edit-detection probe modifies an existing tracked file directly, rather than
committing a fresh probe first. This catches old-mtime races that the earlier
probe could miss. Results from prototypes that fail the stronger probe are not
accepted as performance wins.

Use `storage.py --candidate benchmark-results/tools/apfs-worktree` to include
its baseline cache in physical storage accounting. The cache is retained during
the four-worktree trial, including when it was first initialized; its cost is
not excluded from the reported marginal footprint.

## Other Git commands and concurrent agents

```sh
python3 benchmarks/commands.py --files 2000 --agents 4 --untracked 1000 --repeats 5
python3 benchmarks/commands.py --files 100 --agents 64 --untracked 100 --repeats 3
python3 benchmarks/commands.py --repo /absolute/path/to/project --agents 4 --repeats 3
python3 benchmarks/commands.py --files 2000 --edits 100 --untracked 0 --repeats 3
```

This compares the same installed Git executable in native and APFS-allocated
workspaces. It benchmarks `worktree list`, clean/repeated/dirty status, tracked-only
status, `ls-files`, `ls-tree`, branch listing, diff/check/stat/patch, selected-path
staging, staged diff, commit, log/show, restore, branch switches and removal.
Workspace allocation and its actual reported mode are recorded separately.
Both arms receive an untimed warmup allocation/removal before measured allocation.

Each agent gets a separate branch/index/worktree sharing the Git object database.
A scoped commit must include exactly the selected paths and bytes, with the right
parent; another tracked edit is deliberately left unstaged and must survive.
Switching away/back must restore the correct commit and bytes. Concurrent agents
edit the same logical path on their own branches; every resulting commit is
validated independently. The original checkout must remain unchanged. Git object
connectivity and listed workspace membership are checked as well.

Parallel workloads cap concurrency at 16 workers. Reports state both worktree count
and worker count. Schema 2 times edits/add/commit and excludes subsequent commit
validation; schema 1's batch wall time also included validation commands. Individual
command timings are captured separately in both versions. Allocation, setup and
correctness validation are outside individual command timings. Failures preserve
partial command logs and are excluded from performance summaries.

Generated reports live in `commands-*/`. They include executable fingerprints,
source tree identity, raw commands/output, selected paths, errors and timing data.
`--keep` retains disposable fixture repositories. A supplied real repository is
cloned; its working checkout is not changed. The workload tests Git operations,
not whether the edited application compiles. Signing, user hooks, global settings,
network fetch/push and remote server behavior are not imported or benchmarked.
OS caches are not flushed; differences near process-startup latency are exploratory.

Physical lifecycle costs can be measured independently:

```sh
python3 benchmarks/storage.py --candidate benchmark-results/tools/apfs-worktree --tools git,apfs-worktree --git-lifecycle --repeats 1
```

This extends isolated-container storage trials with commits, switching all
worktrees back to the original commit, and switching them back to their agent
branches. It records cumulative physical allocation after each phase, including
Git object storage and the baseline cache, with content/parent/source-isolation
checks. New blobs and changed filesystem extents both contribute; the resulting
deltas are not attributed to individual Git internals or treated as latency data.

An optional re-sharing experiment measures verified compaction after returning
to the shared base (all donor/target worktrees are idle inside the private image):

```sh
python3 benchmarks/storage.py --candidate benchmark-results/tools/apfs-worktree --tools apfs-worktree --profiles large --git-lifecycle --compact-after-switch --repeats 1
```

`--profiles small,large` selects storage fixtures. The compaction experiment uses
the configured cowtree binary, verifies bytes and HEAD afterwards, records its
wall time, and measures allocation again before switching back to agent branches.
It is a separate, opt-in benchmark pass, not an integrated checkout optimization.

## Native Git APFS switch and restore

The replacement Git implementation now lives in Git's C checkout engine. Build
matched upstream/fork binaries and benchmark them directly:

```sh
python3 native/build.py
python3 benchmarks/checkout.py --mode latency --repeats 3
python3 benchmarks/checkout.py --mode storage --repeats 3
```

`checkout.py` compares `git-baseline/bin/git` and `git-apfs/bin/git`, not the Go
allocator or a command wrapper. Both arms start with worktrees created by the
fork so their initial files are identically APFS-shared. The experiment then
changes ~10% of files in each of four worktrees. Switch trials commit the changes
and return to the shared base. Restore trials discard only selected working-tree
changes while preserving an unrelated staged file and untracked note.

Latency runs use the host filesystem and report whole-command time plus first
status. Physical storage runs use fresh private sparse APFS containers and report
allocation relative to the source checkout/object store, before and after the
operation. Git objects, refs, index and worktree metadata are included. There is
no post-command compaction. The source checkout remains unchanged.

Options include `--profiles small,large,smoke`, `--operations switch,restore`,
`--worktrees`, `--repeats`, `--paired`, and `--variants native,apfs,disabled`.
`--paired` interleaves four native and four APFS command targets in one shared
fixture, with deterministic ordering changed per repeat. It is a separate
latency profile; separate storage fixtures still use four live worktrees.
The checkout fixtures disable automatic Git GC in both variants so background
maintenance cannot contaminate checkout timings. The disabled
variant runs the fork with `GIT_APFS_CLONE_CHECKOUT=0` as an additional control.
`--settle-seconds 1.1` adds an untimed idle interval after preparation to compare
settled timestamp state with the default immediate-agent workload. It does not
flush OS caches; report these profiles separately.
All reports record binary versions/hashes, exact commands and actual native clone
counts. Passing trials require correct bytes/types/modes, HEAD/index behavior,
source isolation, staged/untracked preservation and timestamp-restored edit
visibility. Storage checkpoints retain their raw stabilization readings.

The native fork's scope, build options, source revision and limits are documented
in [native/README.md](../native/README.md). Older worktree allocation and command
benchmarks above describe earlier research stages, not the replacement Git binary.

Native checkout timings now use blocking process waits with an independent
process-group watchdog, avoiding Python timeout-polling delays on macOS. Earlier
checkout latency results used the old runner and should not be mixed with the
current [speed/space report](../review/git-apfs-small-file-results.md).

## Concurrent real-repository agent loops

`agents.py` takes an existing repository and a pinned ref, clones an isolated
fixture and runs concurrent worktree creation, status, diff, add, commit,
restore, switch and cleanup. It verifies committed blob identities and restored
bytes independently of status. Use `--agents 1,8,32 --repeats 3` for latency and
`--mode storage --repeats 1` for isolated APFS allocation trials. The source
checkout is never edited. See `native/README.md` for controls, quota accounting,
FSMonitor guard, CPU/RSS limitations and physical peak sampling methodology.

```sh
python3 benchmarks/agents.py --source references/git-core --ref v2.56.0 --assert-clones
python3 benchmarks/agents.py --source references/git-core --ref v2.56.0 --mode storage --repeats 1 --assert-clones
```

The six variants compare native/APFS defaults, equal native tuning settings,
and optional donor cache. FSMonitor is guarded in the fork while cloning/cache
is enabled; do not interpret its tuned result as an FSMonitor speedup. Native
controls retain their configured FSMonitor behavior. `--profile` adds overhead
and is reported separately. All failures remain in raw JSON. Command p50/p95
and RSS are per-command, not aggregate agent-tree resource measurements.
