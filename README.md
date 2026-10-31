# Git APFS

**Agents Prioritized, Files Shared.**

An experimental Git fork for agent workspaces on macOS APFS, based on Git
v2.56.0. Verified copy-on-write checkout lives inside Git's C checkout engine:
`switch`, `restore` and `worktree add` can share file extents. The executable is
`git`, with Git's normal built-ins, object/index formats and GPL v2 license.

## Build

Requires macOS developer tools and make. Install into a separate prefix:

```sh
make -j4 NO_RUST=YesPlease NO_GETTEXT=YesPlease NO_TCLTK=YesPlease prefix="$HOME/.local/git-apfs" install
export PATH="$HOME/.local/git-apfs/bin:$PATH"
git --version
git apfs doctor
git switch branch-name
git restore -- path/to/file
```

These options use Git's C implementation without Cargo, translations or Tcl/Tk
GUI programs. CLI remote helpers remain included. Other platforms use native
checkout behavior; the APFS optimization requires macOS and a suitable volume.

## Checkout and agent controls

- Streams SHA-1/SHA-256 verification against the exact resolved Git blob before
  cloning. Donor HEAD/index metadata is never sufficient proof. Files up to
  64 MiB are eligible, including byte-preserving LF text attributes.
- Uses pinned no-follow donor descriptors, private clone publication, fresh
  checkout timestamps and Git's normal dirty-file protection and index updates.
  Filters, CRLF conversions, encoding/ident conversion, special metadata,
  symlinks, unavailable donors and pre-publication failures use native writes.
- Reuses donor directory handles and successful donor search hints, without
  skipping verification. Bounded batches overlap main-thread object lookup with
  filesystem/hash workers. Large batches can start below the usual file-count
  threshold; explicit checkout worker/threshold settings retain precedence.
- Shares a default budget of eight auxiliary threads across processes in one
  repository. Caller threads are additional. OS file-lock leases release on
  process death. Set `apfs.workerBudget` to 0..64; explicit `checkout.workers`
  overrides the automatic budget.
- Initializes worktree common-directory metadata before publishing its linking
  files, closing a concurrent discovery race during worktree creation.

```sh
git apfs doctor                 # read-only JSON diagnostics
git apfs tune                   # enable native FSMonitor/untracked-cache config
GIT_APFS_TRACE_JSON=1 git restore -- file
GIT_APFS_PROFILE=1 git switch branch-name  # extra phase/worker timings
GIT_APFS_CLONE_CHECKOUT=0 git restore -- file  # native-write control
```

`tune` changes repository configuration, so compare with equally tuned upstream
Git. No global settings are changed. Diagnostics report clone coverage, fallback
reasons, worker activity and cache accounting. Clone byte counts are logical
contents; physical savings require an independent allocation measurement.

**APFS + FSMonitor guard:** concurrent stress tests exposed missed external
edits during APFS checkout workloads, including in equally tuned upstream Git.
With APFS cloning or a positive `apfs.cacheLimit`, Git therefore bypasses FSMonitor and uses normal stat checks. Configuration is
preserved and diagnostics report `cache.fsmonitor_stat_guard`. Untracked cache
remains available. The FSEvents interaction is unresolved; the guard is deliberate.

## Optional donor cache

The cache is **off by default**. It retains verified snapshots even after donor
worktrees disappear. Checkout and `add` populate it when enabled:

```sh
git config apfs.cacheLimit 64m
git apfs cache warm
git apfs cache status
git apfs cache prune
```

The private common-directory cache uses verified blob identities, opportunistic
writer locking and FIFO eviction. Its quota charges at least 4 KiB per entry or
allocated file blocks, whichever is greater; directory/lock metadata is extra.
This conservatively charges shared extents more than once. Cache warm-up costs
and retained cache storage must be included when assessing benefit.

## Measurements and validation

[Results and limitations](contrib/apfs/results.md) cover speed and physical disk
usage. [Build and benchmark instructions](contrib/apfs/native/README.md) include
matched upstream/fork builds and controls. The real-repository agent runner
measures concurrent creation, status, diff, add, commit, restore, switch and
cleanup, with per-command p50/p95, CPU/RSS and isolated-container disk accounting.

```sh
python3 contrib/apfs/native/build.py
python3 -m unittest discover -s contrib/apfs/tests -v
python3 contrib/apfs/benchmarks/checkout.py --mode latency --paired
python3 contrib/apfs/benchmarks/checkout.py --mode storage
python3 contrib/apfs/benchmarks/agents.py --source /path/to/repo --agents 1,8,32
```

This remains an experimental fork. Other Git commands retain upstream behavior;
not every workload becomes faster. The full upstream suite has not been run.
See [upstream Git's README](README.upstream.md) for general Git documentation.
