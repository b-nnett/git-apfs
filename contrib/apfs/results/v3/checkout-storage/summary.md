# Native Git vs Git APFS checkout

Paired latency fixtures: False. Automatic Git GC is disabled in the fixture for both variants to exclude background maintenance.

Untimed settling period: 0s. Matched upstream/fork builds. Both arms begin with identically APFS-shared worktrees. Changes are ~10% of files. Timings include the whole Git process; first status is separate. No post-command compaction.

| Profile | Command | Variant | Git command median | Command + first status | Extra allocation after operation |
| --- | --- | --- | --- | --- | --- |
| small | switch | native | 62.27 ms | 72.92 ms | 13.77 MiB |
| small | switch | apfs | 66.82 ms | 80.33 ms | 10.68 MiB |
| small | restore | native | 56.40 ms | 67.47 ms | 6.73 MiB |
| small | restore | apfs | 59.72 ms | 72.07 ms | 3.59 MiB |
| large | switch | native | 34.60 ms | 58.54 ms | 96.78 MiB |
| large | switch | apfs | 71.19 ms | 95.28 ms | 48.77 MiB |
| large | restore | native | 178.25 ms | 201.95 ms | 48.46 MiB |
| large | restore | apfs | 174.20 ms | 197.45 ms | 0.45 MiB |

Passed 24/24 trials.
Physical allocation includes Git objects, refs and index metadata relative to the source fixture, not logical du sizes. Storage trials use private APFS containers; latency trials use the host filesystem. Four worktrees per variant; paired latency keeps eight worktrees live in one fixture.
Checks: bytes/types/modes, HEAD, preserved restore index entries and unrelated staged/untracked work, source isolation, restored-mtime edit detection, and actual clone counters.
