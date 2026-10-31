# Git APFS v3: agent workflows, speed and physical space

Measured on macOS 15.2 arm64 on 31 October 2026. Matched Git **2.56.0** and **2.56.0.apfs.3**, pinned to upstream `a018953688f1b10bddf91bff8747068f5f4746a4`; both use the same C build options. [Build manifest](results/v3/build.json) records patch and binary hashes. [v2 measurements](results-v2.md) are historical and use a different upstream base.

The fork adds LF-safe text eligibility, streamed verification for all eligible sizes, donor search hints, adaptive large-file batches, a shared auxiliary-worker budget, JSON diagnostics and a bounded optional donor cache. It also fixes worktree registration publication order. **APFS cloning currently bypasses FSMonitor for normal stat validation**, following missed-edit failures in concurrent stress tests. The final matrix also reproduced missed restores in the equally tuned upstream control at 32 agents, so the symptom is not isolated to our clone/cache code. Untracked-cache tuning remains available. This is a correctness guard, not a completed FSMonitor speed optimization.

## Whole agent workflows

The source is the real Git v2.56.0 repository. Each agent creates a worktree, performs two edit/diff/add/commit/restore cycles on 16 actual text files, switches back and is removed. Committed blob identities and restored bytes are checked independently of status. Median wall time includes cleanup but excludes separately listed cache warm-up and allocation checkpoint waits. Three trials attempted per variant/cohort. Failed trials are excluded from timing medians and shown in the valid-trial column.

| Variant | Agents | Valid trials | Workflow wall | Cache warm-up | Summed command CPU | Max command RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| native | 1 | 3/3 | 1.224s | 0.000s | 1.19s | 58.6 MiB |
| native | 8 | 3/3 | 4.602s | 0.000s | 9.47s | 66.8 MiB |
| native | 32 | 3/3 | 20.032s | 0.000s | 36.26s | 67.2 MiB |
| apfs | 1 | 3/3 | 1.461s | 0.000s | 2.49s | 18.4 MiB |
| apfs | 8 | 3/3 | 5.561s | 0.000s | 16.91s | 19.2 MiB |
| apfs | 32 | 3/3 | 22.079s | 0.000s | 59.19s | 19.3 MiB |
| native-tuned | 1 | 3/3 | 1.179s | 0.000s | 0.86s | 59.8 MiB |
| native-tuned | 8 | 3/3 | 4.762s | 0.000s | 8.08s | 67.2 MiB |
| native-tuned | 32 | 2/3 | 20.785s | 0.000s | 28.67s | 67.7 MiB |
| apfs-tuned | 1 | 3/3 | 1.265s | 0.000s | 2.32s | 18.5 MiB |
| apfs-tuned | 8 | 3/3 | 5.558s | 0.000s | 16.36s | 19.0 MiB |
| apfs-tuned | 32 | 3/3 | 21.777s | 0.000s | 58.24s | 19.5 MiB |
| apfs-cache | 1 | 3/3 | 1.517s | 1.131s | 3.58s | 19.2 MiB |
| apfs-cache | 8 | 3/3 | 6.214s | 1.078s | 20.70s | 19.4 MiB |
| apfs-cache | 32 | 3/3 | 25.203s | 1.131s | 79.50s | 19.7 MiB |
| apfs-cache-tuned | 1 | 3/3 | 1.339s | 1.112s | 3.38s | 19.2 MiB |
| apfs-cache-tuned | 8 | 3/3 | 6.344s | 1.123s | 21.02s | 19.5 MiB |
| apfs-cache-tuned | 32 | 3/3 | 25.018s | 1.104s | 78.98s | 19.7 MiB |

Native/APFS defaults have no FSMonitor tuning. `*-tuned` sets the same FSMonitor/untracked-cache configuration in both builds; the fork reports its FSMonitor stat guard and therefore does not receive that acceleration. Cache variants use a 64 MiB charge limit. Cache warm-up and maintenance command CPU are included in summed CPU; CPU/RSS exclude persistent monitor daemons and are not aggregate peak RAM. Per-command p50/p95 and individual distributions are in the [full latency report](results/v3/agent-latency/summary.md).

## Real-workflow physical allocation

Separate private APFS-container trials, one trial per cell. Extra allocation is relative to the source fixture and includes cache warm-up, Git objects/index/refs and worktree metadata. Peak is a sampled lower bound. Cleanup removes worktrees and stops managed monitor daemons; agent branches and committed objects remain, as do configured cache entries. It does not run garbage collection. These are physical container measurements, not sums of file block counts.

| Variant | Agents | Sampled peak extra | Retained extra | After cleanup extra |
| --- | ---: | ---: | ---: | ---: |
| native | 1 | 62.97 MiB | 62.97 MiB | 0.37 MiB |
| native | 8 | 505.02 MiB | 505.02 MiB | 3.03 MiB |
| native | 32 | 2024.35 MiB | 2024.35 MiB | 12.05 MiB |
| apfs | 1 | 2.45 MiB | 2.45 MiB | 0.66 MiB |
| apfs | 8 | 19.62 MiB | 19.29 MiB | 4.90 MiB |
| apfs | 32 | 80.59 MiB | 77.09 MiB | 19.00 MiB |
| native-tuned | 1 | 62.99 MiB | 62.99 MiB | 0.37 MiB |
| native-tuned | 8 | 505.23 MiB | 505.23 MiB | 3.07 MiB |
| native-tuned | 32 | 2024.59 MiB | 2024.59 MiB | 12.02 MiB |
| apfs-tuned | 1 | 2.46 MiB | 2.46 MiB | 0.65 MiB |
| apfs-tuned | 8 | 19.92 MiB | 19.50 MiB | 4.89 MiB |
| apfs-tuned | 32 | 79.60 MiB | 77.63 MiB | 19.05 MiB |
| apfs-cache | 1 | 4.71 MiB | 4.71 MiB | 2.87 MiB |
| apfs-cache | 8 | 22.93 MiB | 22.93 MiB | 8.43 MiB |
| apfs-cache | 32 | 83.51 MiB | 81.29 MiB | 23.24 MiB |
| apfs-cache-tuned | 1 | 4.62 MiB | 4.62 MiB | 2.85 MiB |
| apfs-cache-tuned | 8 | 23.11 MiB | 22.69 MiB | 8.17 MiB |
| apfs-cache-tuned | 32 | 83.43 MiB | 80.84 MiB | 22.25 MiB |

[Storage method and full measurements](results/v3/agent-storage/summary.md). Cache accounting charges at least 4 KiB per snapshot or allocated file blocks, plus directory/lock metadata. Its quota is conservative rather than a unique physical-byte count. It can retain more space after cleanup than the cache-free mode.

## Switch and restore

Paired latency measurements interleave four worktrees of each variant; physical storage uses separate containers with four worktrees each. Each begins with identically shared files and changes approximately 10% of them. Three trials per cell; command medians are across 12 operations.

| Shape / command | Native | APFS | APFS / native time | Native retained extra | APFS retained extra |
| --- | ---: | ---: | ---: | ---: | ---: |
| small / switch | 65.23 ms | 69.77 ms | 1.07× | 13.77 MiB | 10.68 MiB |
| small / restore | 58.17 ms | 60.82 ms | 1.05× | 6.73 MiB | 3.59 MiB |
| large / switch | 105.34 ms | 29.67 ms | 0.28× | 96.78 MiB | 48.77 MiB |
| large / restore | 175.99 ms | 174.28 ms | 0.99× | 48.46 MiB | 0.45 MiB |

[Latency details](results/v3/checkout-latency/summary.md), [physical allocation](results/v3/checkout-storage/summary.md), and [separate settled large-file profiles](results/v3/large-profile/summary.md). The profiled run adds phase timing and Git Trace2 overhead and is not pooled with normal latency. Phase work sums can exceed wall time because workers run concurrently. In the settled profiled APFS restore run, median clone-batch wall time was about 4.1 ms while Trace2 attributed about 164.8 ms of the 175.2 ms command to index writing. The remaining large-restore bottleneck lies outside clone publication; the current fixture exercises conservative Git index validation. The optimization does not remove that cost. Large-switch timings are profile-sensitive: the default paired host run favored APFS by 3.55×, the separately instrumented settled host run by about 1.34×, while storage-mode timings on private disk images favored native Git (34.6 vs 71.2 ms). Storage-mode timings are not normal host-latency measurements, but this variation rules out claiming a universal large-switch speedup.

## Second real repository

[microsoft/TypeScript](https://github.com/microsoft/TypeScript) is pinned to `6161772c1370bdd4a82f808e6823bd755eb1870d`. One trial per cell: six variants with one agent, and native/APFS defaults with eight agents. This is a coverage check, not a statistically strong comparison. [One-agent report](results/v3/typescript-latency/summary.md), [eight-agent report](results/v3/typescript-concurrent/summary.md).

| TypeScript agents | Native workflow | APFS workflow |
| ---: | ---: | ---: |
| 1 | 9.048s | 11.097s |
| 8 | 123.130s | 126.682s |

The cache-enabled TypeScript trial took 29.69s plus 17.22s cache warm-up. With registered donors already available, cache admission/verification adds substantial overhead to this corpus; this is another reason it remains opt-in.

## Validation and remaining limits

- 45 local Python tests and 38 packaged tests pass.
- 742 targeted Git checks pass; three skip for missing prerequisites. This is not the full upstream suite.
- Six 32-agent guarded stress trials passed before the frozen performance matrix. Earlier registration and missed-edit failures remain archived separately; they are not silently retried into success.
- No global cache purge; latency measures a warm host filesystem. Command instrumentation and correctness verification add overhead to workflow wall time. CPU values have `/usr/bin/time` reporting precision.
- Private-container readings must stabilize. Peak sampling waits at least 100 ms between polls and can miss transients. No claim of aggregate daemon/agent peak RAM is made.
- Donor bytes are always verified. Explicit checkout workers override the shared default budget; caller threads are additional to auxiliary leases.
- The cache is off by default. Its warm-up, retention, FIFO policy and FSMonitor guard are material costs.

| Final report | Passed / attempted |
| --- | ---: |
| [agent-latency](results/v3/agent-latency/summary.md) | 53 / 54 |
| [checkout-latency](results/v3/checkout-latency/summary.md) | 24 / 24 |
| [large-profile](results/v3/large-profile/summary.md) | 12 / 12 |
| [agent-storage](results/v3/agent-storage/summary.md) | 18 / 18 |
| [checkout-storage](results/v3/checkout-storage/summary.md) | 24 / 24 |
| [typescript-latency](results/v3/typescript-latency/summary.md) | 6 / 6 |
| [typescript-concurrent](results/v3/typescript-concurrent/summary.md) | 2 / 2 |

Each report directory includes a compressed raw `results.json.gz`, executable and runner hashes, invocation parameters and a run log. [Run index](results/v3/run-index.json), [local tests](results/v3/local-python-tests.txt), [packaged tests](results/v3/packaged-python-tests.txt), [Git tests](results/v3/native-tests.txt). Absolute workspace/home paths are replaced with placeholders. Exact runner snapshots are archived alongside results.
