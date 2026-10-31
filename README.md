# Git APFS

**Agents Prioritized, Files Shared.**

A real Git fork for agent workspaces on macOS APFS. Verified copy-on-write
checkout lives inside Git's C checkout engine, so `switch`, `restore` and
`worktree add` can share file extents with another registered worktree.
The executable is `git`: there is no command wrapper or compaction pass.

This is an experimental fork based on Git v2.50.1, not a current-upstream
production release. Other commands remain Git's built-ins; they are not all
optimized by this patch. Git's GPL v2 license, attribution and history are retained.

## Build

Requires macOS developer tools and make. Install into your own prefix:

```sh
make -j4 NO_GETTEXT=YesPlease NO_TCLTK=YesPlease prefix="$HOME/.local/git-apfs" install
export PATH="$HOME/.local/git-apfs/bin:$PATH"
git --version
git switch branch-name
git restore -- path/to/file
```

Choose a prefix separate from system Git. Omitting gettext and Tcl/Tk matches
the benchmark build; CLI remote helpers remain included. On other operating
systems the APFS helper falls back to native Git behavior.

## How it works

- Finds the same path in another registered worktree and verifies its Git blob
  identity. Small files use Git's canonical blob hash with SHA-1/SHA-256 and
  replacement-object support; larger files use a literal byte comparison.
  Donor HEAD/index metadata is not trusted.
- Uses no-follow directory opens and pinned file descriptors, checks source
  metadata around verification/cloning, and publishes a private clone with an
  exclusive rename. Git retains dirty-file protection, index/ref updates and hooks.
- Overlaps main-thread object lookup with bounded filesystem/hash workers.
  Object-store access, configuration, index updates and trace counters stay on
  the main thread. Each worker owns its directory cache and hash context. The donor-directory handle can be reused; target ancestors are walked
  afresh. Batch capacity adapts to the descriptor limit and is capped at 256 files.
- Defaults to up to eight workers for eligible batches of at least 100 entries
  when a registered donor exists on the same APFS volume. Explicit
  `checkout.workers` and `checkout.thresholdForParallelism` settings win.
- Uses ordinary Git writes for filters, text/encoding conversions, symlinks,
  special metadata, files over 64 MiB, unavailable donors and clone failures
  before publication. Errors after publication are reported without retrying.

No index formats, object formats, trust flags or global settings are changed.
There is no persistent donor cache, and no space benefit without an eligible
registered donor. Normal Git locks and the usual requirement to avoid concurrent
external filesystem writers still apply.

```sh
GIT_APFS_TRACE=1 git restore -- file  # actual clone counts, logical byte counts
GIT_APFS_CLONE_CHECKOUT=0 git restore -- file  # native-write control
# Repository configuration also works:
git config apfs.cloneCheckout false
```

Trace byte counts are logical contents, not physical savings. Physical space
must be measured independently on an isolated APFS container.

## Benchmarks and tests

[Measured results and limitations](contrib/apfs/results.md) report both latency
and retained physical allocation, including first status and Git metadata.
[Implementation details](contrib/apfs/native/README.md) describe the bounded fast
path and controls. Benchmark scripts and targeted differential tests are in
`contrib/apfs/`.

For reproducible matched upstream/fork builds and comparisons:

```sh
python3 contrib/apfs/native/build.py
python3 contrib/apfs/benchmarks/checkout.py --mode latency --repeats 3
python3 contrib/apfs/benchmarks/checkout.py --mode storage --repeats 3
python3 -m unittest discover -s contrib/apfs/tests -v
```

Storage trials require macOS disk-image tools and use disposable private APFS
containers. Both variants begin with CoW-shared worktrees to isolate command
savings from initial worktree creation. Raw timing and allocation samples are
recorded locally. These are synthetic agent workflows, not a guarantee for every
repository or workload.

Git's native APFS regressions are in `t/t2090-apfs-checkout.sh`. The full upstream
suite has not yet been run. See [upstream Git's README](README.upstream.md) for
Git's general documentation and contribution information.
