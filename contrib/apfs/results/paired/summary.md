# Native Git vs Git APFS checkout

Paired latency fixtures: True. Automatic Git GC is disabled in the fixture for both variants to exclude background maintenance.

Untimed settling period: 0s. Matched upstream/fork builds. Both arms begin with identically APFS-shared worktrees. Changes are ~10% of files. Timings include the whole Git process; first status is separate. No post-command compaction.

| Profile | Command | Variant | Git command median | Command + first status | Extra allocation after operation |
| --- | --- | --- | --- | --- | --- |
| small | switch | native | 70.42 ms | 82.39 ms | not measured |
| small | switch | apfs | 70.33 ms | 83.55 ms | not measured |
| small | restore | native | 61.66 ms | 74.26 ms | not measured |
| small | restore | apfs | 61.20 ms | 74.67 ms | not measured |

Passed 12/12 trials.
Physical allocation includes Git objects, refs and index metadata relative to the source fixture, not logical du sizes. Storage trials use private APFS containers; latency trials use the host filesystem. Four worktrees per variant; paired latency keeps eight worktrees live in one fixture.
Checks: bytes/types/modes, HEAD, preserved restore index entries and unrelated staged/untracked work, source isolation, restored-mtime edit detection, and actual clone counters.
