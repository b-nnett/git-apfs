# Native Git APFS checkout benchmarks

Build matched upstream/fork executables from the pinned Git v2.50.1 source:

```sh
python3 contrib/apfs/native/build.py
python3 contrib/apfs/benchmarks/checkout.py --repeats 3
python3 contrib/apfs/benchmarks/checkout.py --paired --profiles small --repeats 3
python3 contrib/apfs/benchmarks/checkout.py --mode storage --repeats 3
```

All paths are relative to the repository root. Python 3.9+, macOS developer
tools, make, diskutil and hdiutil are required. Builds and raw reports stay in
ignored `contrib/apfs/benchmark-results/`. The full executable is `bin/git`.
`bench.py` and `storage.py` provide shared fixture/measurement helpers; the
native switch/restore benchmark entry point is `checkout.py`.

## Workloads

- Small: 2,000 files of 4 KiB each; each worktree changes 200 files.
- Large: 128 files of 1 MiB each; each worktree changes 12 files.
- Each fixture uses deterministic incompressible bytes and special filename,
  symlink and executable fixtures. Four agent worktrees are measured per variant.
- Both variants initially use identical CoW-shared files. Worktree creation is
  outside the measured operation, isolating switch/restore from allocation gains.
- Switch commits agent edits, then returns to the shared base. New commit objects
  remain allocated. Restore discards selected working-tree changes while keeping
  an unrelated staged file and untracked note.
- Automatic GC is disabled in both fixtures to exclude background maintenance.
  User configuration and hooks are isolated. Normal Git/APFS checkout defaults
  are measured unless an explicit control is requested.

Separate latency fixtures use the host filesystem. `--paired` interleaves four
native and four APFS targets in the same repository, with deterministic ordering
changed per repeat; eight worktrees remain live. Report these profiles separately.
`--settle-seconds 1.1` adds an untimed idle interval before commands; it does not
flush OS caches. `--candidate-workers N` overrides the candidate only and records
the setting. `--variants native,apfs,disabled` adds a feature-disabled fork control.

Whole-process timing uses a blocking process wait with an independent watchdog
that kills the process group on timeout. This avoids timeout-polling delays from
Python's `communicate(timeout=...)` on macOS. Runner/source hashes and executable
versions/hashes are recorded. Earlier research timings used the older wait method
and should not be mixed with these latency results.

Physical trials use fresh private sparse APFS containers. Allocation is container
capacity minus free capacity after sync, requiring three equal samples. Fixture,
before-command and after-command checkpoints retain all raw readings. Only stable
checkpoints support precise space claims. The extra allocation includes objects,
refs, indexes, worktree files and filesystem metadata relative to the original
source checkout/object-store fixture. Logical `du` sizes cannot show shared extent
savings. There is no compaction pass.

Every trial checks bytes/types/modes, HEAD/index behavior, staged/untracked
preservation, donor isolation, restored-mtime edit visibility, and actual clone
counts. Read [results and limitations](../results.md) before interpreting speedups.
