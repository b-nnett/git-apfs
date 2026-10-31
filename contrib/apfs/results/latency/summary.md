# Native Git vs Git APFS checkout

Paired latency fixtures: False. Automatic Git GC is disabled in the fixture for both variants to exclude background maintenance.

Untimed settling period: 0s. Matched upstream/fork builds. Both arms begin with identically APFS-shared worktrees. Changes are ~10% of files. Timings include the whole Git process; first status is separate. No post-command compaction.

| Profile | Command | Variant | Git command median | Command + first status | Extra allocation after operation |
| --- | --- | --- | --- | --- | --- |
| small | switch | native | 65.45 ms | 77.29 ms | not measured |
| small | switch | apfs | 68.08 ms | 81.45 ms | not measured |
| small | restore | native | 59.44 ms | 74.61 ms | not measured |
| small | restore | apfs | 58.22 ms | 71.82 ms | not measured |
| large | switch | native | 22.03 ms | 44.89 ms | not measured |
| large | switch | apfs | 89.90 ms | 112.85 ms | not measured |
| large | restore | native | 174.11 ms | 196.06 ms | not measured |
| large | restore | apfs | 173.93 ms | 196.90 ms | not measured |

Passed 24/24 trials.
Physical allocation includes Git objects, refs and index metadata relative to the source fixture, not logical du sizes. Storage trials use private APFS containers; latency trials use the host filesystem. Four worktrees per variant; paired latency keeps eight worktrees live in one fixture.
Checks: bytes/types/modes, HEAD, preserved restore index entries and unrelated staged/untracked work, source isolation, restored-mtime edit detection, and actual clone counters.
