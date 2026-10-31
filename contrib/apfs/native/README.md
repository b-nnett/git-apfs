# Git APFS: a native Git fork

This is a patched Git executable. `switch` and `restore` execute Git's built-in
commands and use APFS cloning inside the checkout writer. They do not invoke a
second Git executable or perform a post-command compaction pass.

## Build and use

```sh
python3 native/build.py
benchmark-results/git-apfs/bin/git --version
benchmark-results/git-apfs/bin/git -C /path/to/repository switch branch-name
benchmark-results/git-apfs/bin/git -C /path/to/repository restore -- path/to/file
```

The build produces two local installations: `benchmark-results/git-baseline/`
and `benchmark-results/git-apfs/`. Both use the pinned upstream commit and the
same compiler options; only the APFS patch and version branding differ. Nothing
changes `/usr/bin/git`, global Git configuration or the user's PATH. To use the
fork as the `git` command in a shell, put its `bin` directory first in that
shell's PATH. Git's helper programs are installed with it.

Python 3.9+, macOS developer tools and `make` are required. The matched builds
omit gettext translations and Tcl/Tk GUI programs; CLI features including remote
helpers remain enabled. Sources are exported from the pinned upstream object,
patched in a private build directory and compiled. Build logs and executable
hashes are recorded in a build manifest. `upstream.json` pins Git v2.50.1, chosen
to match the installed Git version used in the initial experiments; this is an
experimental fork, not a current-upstream production release.

## What changed

The patch adds an APFS checkout helper to Git's serial `write_entry` path and
parallel-checkout writer. The existing Git code still decides which paths to
replace, protects dirty files, selects the branch/source/index, handles deletions,
updates index stat information and runs hooks. This also makes the optimization
available to other callers of this checkout engine, such as `worktree add`.

For an eligible regular file, the helper:

1. Finds the same path in another registered worktree. Donor HEAD/index lookups
   are unnecessary because the bytes are checked against the exact requested blob.
2. Opens donor ancestors and the donor file without following symlinks.
3. Rejects special file flags/xattrs, unreadable owner modes and large files.
4. Checks the Git blob's size before materializing its expected bytes; the current
   fast path is bounded to 64 MiB per file.
5. Verifies small donor files (up to 64 KiB) using Git's canonical blob hash,
   including the blob header, repository hash algorithm and replacement-object
   resolution. Larger files are compared byte-for-byte with the Git blob.
   Donor identity/timestamps are checked before and after cloning.
6. Clones the pinned donor descriptor to a random sibling name using
   `fclonefileat`, normalizes mode for Git's umask semantics, and publishes with
   exclusive rename. It sets fresh checkout timestamps and supplies the actual
   output stat information back to Git's normal index update code.
7. Issues a best-effort asynchronous read hint for cloned files.

If no verified donor is available, the normal Git write path runs. Filters,
encoding, ident expansion, CRLF/text transformations, symlinks, temporary checkout
files and `checkout-index --prefix` remain on that path. A clone failure before
publication also falls back. A failure after publication is reported as a normal
checkout error instead of attempting to rewrite an exposed path.

The helper changes no Git index formats, trust flags, ref formats or object-store
formats. Unrelated staged/unstaged/untracked paths remain governed by Git. In
particular, `restore --staged` does not materialize files and invokes no APFS
checkout helper. Commits and worktree listing remain real Git built-ins.

## Controls and observability

```sh
# Disable the checkout optimization for one command.
GIT_APFS_CLONE_CHECKOUT=0 benchmark-results/git-apfs/bin/git restore -- file

# Or configure this repository explicitly (default in the fork is enabled).
benchmark-results/git-apfs/bin/git config apfs.cloneCheckout false

# Emit per-process actual clone counts/logical bytes to stderr.
GIT_APFS_TRACE=1 benchmark-results/git-apfs/bin/git switch branch-name
```

Trace byte counts describe cloned logical contents, not measured physical savings.
The benchmark measures physical APFS container allocation independently.

## Validation and benchmarking

```sh
python3 -m unittest discover -s tests -p test_git_core.py -v
python3 benchmarks/checkout.py --mode latency --repeats 3
python3 benchmarks/checkout.py --mode storage --repeats 3
# Separate settled-timestamp workload; the default above runs immediately.
python3 benchmarks/checkout.py --mode latency --repeats 3 --settle-seconds 1.1
```

The tests compare native/fork behavior for dirty protection, carried changes,
staging, path-limited and staged-only restore, other source commits, subdirectory
pathspecs, filters/hooks, symlinks, executable modes/umask, binary data, Unicode and
newline names, restored timestamps, parallel checkout and disabling the feature.
Validation passes 20 targeted native-fork tests, 354 selected upstream tests, and
eight new tests in Git's APFS test script. See
[results and tradeoffs](../results.md).

The checkout benchmarks use the full executables directly. Both arms begin with
identical APFS-shared worktrees, so command-specific savings are not confused with
worktree-creation savings. Latency runs use the host filesystem; storage runs use
fresh private APFS containers. Every run records executable hashes and actual
clone counters and checks bytes, modes, HEAD, index semantics and source isolation.

## Current limits

A donor must be an accessible registered worktree with the exact requested bytes
at the same path on a clone-compatible volume. Its HEAD/index can differ. There is no persistent blob cache or
single-checkout deduplication when no donor exists. Conversion-heavy repositories and
files over 64 MiB use native writes. Donors are mutable, so content verification
and metadata checks are retained. Native Git index/ref locks and the
usual requirement to avoid concurrent external writers still apply.

The fork defaults to up to eight checkout workers for batches of at
least 100 eligible entries when another registered worktree exists on the same
APFS volume. Explicit `checkout.workers` and `checkout.thresholdForParallelism`
settings take precedence. With clones disabled, on other filesystems, or without
a donor worktree, native serial defaults remain. Small batches remain serial.
For eligible batches, Git resolves object metadata and replacement identities on
the main thread. Filesystem reads, private descriptor caches and independent
small-file hash contexts run in bounded workers, alongside cloning. Larger-file
byte comparisons remain on the main thread. Git object/config/index access and
counters remain on the main thread. Batch size is capped at 256 files and reduced
according to the file-descriptor limit.
Native fallback and collision recovery use the existing checkout machinery.
Command and first-status timings must be reported alongside physical space.
This does not claim every Git command is faster or that the full upstream test
suite has been run.

`git-apfs.patch` and the Git fork are distributed under Git's GPL version 2;
`COPYING` contains the upstream license. The pinned upstream URL and exact patch
digest are in `upstream.json`.

## Keeping the matched build current

CI verifies the patched build against every tracked source file in this checkout,
excluding the fork README, GitHub workflows and this `contrib/apfs` harness. It
fails if core changes are missing from the reproducible patch. After staging new
source files, regenerate from the pinned base, then refresh the digest:

```sh
base=d82adb61ba2fd11d8f2587fca1b6bd7925ce4044
git diff --binary "$base" -- . ':!README.md' ':!README.upstream.md' ':!.github' ':!contrib/apfs' > contrib/apfs/native/git-apfs.patch
python3 - <<'PYCODE'
import hashlib,json
from pathlib import Path
root=Path('contrib/apfs/native')
p=root/'upstream.json'
meta=json.loads(p.read_text())
meta['patch_sha256']=hashlib.sha256((root/'git-apfs.patch').read_bytes()).hexdigest()
p.write_text(json.dumps(meta,indent=2)+'\n')
PYCODE
```
