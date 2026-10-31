# Native Git vs Git APFS checkout

Paired latency fixtures: True. Automatic Git GC is disabled in the fixture for both variants to exclude background maintenance.

Untimed settling period: 0s. Matched upstream/fork builds. Both arms begin with identically APFS-shared worktrees. Changes are ~10% of files. Timings include the whole Git process; first status is separate. No post-command compaction.

| Profile | Command | Variant | Git command median | Command + first status | Extra allocation after operation |
| --- | --- | --- | --- | --- | --- |
| small | switch | native | 65.23 ms | 76.23 ms | not measured |
| small | switch | apfs | 69.77 ms | 82.99 ms | not measured |
| small | restore | native | 58.17 ms | 70.43 ms | not measured |
| small | restore | apfs | 60.82 ms | 73.62 ms | not measured |
| large | switch | native | 105.34 ms | 128.95 ms | not measured |
| large | switch | apfs | 29.67 ms | 53.25 ms | not measured |
| large | restore | native | 175.99 ms | 190.78 ms | not measured |
| large | restore | apfs | 174.28 ms | 197.68 ms | not measured |

Passed 24/24 trials.
Physical allocation includes Git objects, refs and index metadata relative to the source fixture, not logical du sizes. Storage trials use private APFS containers; latency trials use the host filesystem. Four worktrees per variant; paired latency keeps eight worktrees live in one fixture.
Checks: bytes/types/modes, HEAD, preserved restore index entries and unrelated staged/untracked work, source isolation, restored-mtime edit detection, and actual clone counters.
