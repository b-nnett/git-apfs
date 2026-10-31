# Native Git vs Git APFS checkout

Paired latency fixtures: True. Automatic Git GC is disabled in the fixture for both variants to exclude background maintenance.

Untimed settling period: 1.1s. Matched upstream/fork builds. Both arms begin with identically APFS-shared worktrees. Changes are ~10% of files. Timings include the whole Git process; first status is separate. No post-command compaction.

| Profile | Command | Variant | Git command median | Command + first status | Extra allocation after operation |
| --- | --- | --- | --- | --- | --- |
| large | switch | native | 64.01 ms | 88.43 ms | not measured |
| large | switch | apfs | 47.63 ms | 77.61 ms | not measured |
| large | restore | native | 177.04 ms | 201.02 ms | not measured |
| large | restore | apfs | 175.22 ms | 199.89 ms | not measured |

Passed 12/12 trials.
Physical allocation includes Git objects, refs and index metadata relative to the source fixture, not logical du sizes. Storage trials use private APFS containers; latency trials use the host filesystem. Four worktrees per variant; paired latency keeps eight worktrees live in one fixture.
Checks: bytes/types/modes, HEAD, preserved restore index entries and unrelated staged/untracked work, source isolation, restored-mtime edit detection, and actual clone counters.
