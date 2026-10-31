# Native Git vs Git APFS checkout

Paired latency fixtures: False. Automatic Git GC is disabled in the fixture for both variants to exclude background maintenance.

Untimed settling period: 0s. Matched upstream/fork builds. Both arms begin with identically APFS-shared worktrees. Changes are ~10% of files. Timings include the whole Git process; first status is separate. No post-command compaction.

| Profile | Command | Variant | Git command median | Command + first status | Extra allocation after operation |
| --- | --- | --- | --- | --- | --- |
| small | switch | native | 64.00 ms | 74.28 ms | 13.82 MiB |
| small | switch | apfs | 63.09 ms | 75.42 ms | 10.64 MiB |
| small | restore | native | 57.69 ms | 68.16 ms | 6.72 MiB |
| small | restore | apfs | 56.80 ms | 68.05 ms | 3.60 MiB |
| large | switch | native | 103.40 ms | 126.21 ms | 96.77 MiB |
| large | switch | apfs | 14.40 ms | 36.95 ms | 48.77 MiB |
| large | restore | native | 175.03 ms | 197.69 ms | 48.46 MiB |
| large | restore | apfs | 172.46 ms | 195.06 ms | 0.45 MiB |

Passed 24/24 trials.
Physical allocation includes Git objects, refs and index metadata relative to the source fixture, not logical du sizes. Storage trials use private APFS containers; latency trials use the host filesystem. Four worktrees per variant; paired latency keeps eight worktrees live in one fixture.
Checks: bytes/types/modes, HEAD, preserved restore index entries and unrelated staged/untracked work, source isolation, restored-mtime edit detection, and actual clone counters.
