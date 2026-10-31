# Git APFS benchmarks

Run these commands from `contrib/apfs/` in the fork. Python 3.9+, macOS developer
tools and macOS disk-image utilities are required. Nothing replaces system Git
or changes global Git configuration.

```sh
python3 native/build.py --jobs 4
python3 -m unittest discover -s tests -v
python3 benchmarks/checkout.py --mode latency --paired --repeats 3
python3 benchmarks/checkout.py --mode storage --repeats 3
```

The builder installs matched native/APFS executables under `benchmark-results/`
and records source, patch, compiler options and binary hashes. The synthetic
runner measures switch/restore followed by first status, starting from equally
shared worktrees. Its raw results include byte/type/mode and isolation checks,
clone counts, dirty-file protection and timestamp-preserving edit detection.

## Real-repository agent loops

```sh
python3 benchmarks/agents.py --source /path/to/repo --ref COMMIT --agents 1,8,32 --repeats 3 --assert-clones
python3 benchmarks/agents.py --source /path/to/repo --ref COMMIT --agents 1,8,32 --mode storage --repeats 1 --assert-clones
```

The source is cloned into an isolated fixture and never edited. Each agent
creates a worktree, edits actual text files, diffs, stages, commits, restores,
switches and is removed. Committed blob identities and restored bytes are
checked independently of status. Reports retain all failures, plus per-command
p50/p95, CPU/RSS, warm-up, cleanup and disk measurements.

Six variants separate native/APFS defaults, equal FSMonitor/untracked-cache
configuration, and optional donor cache. The fork currently guards FSMonitor
when cloning or caching is enabled; tuned results do not imply an FSMonitor
speedup. Upstream controls retain their configured FSMonitor behavior. Cache
warm-up costs and post-cleanup retention are explicit.

Storage uses private APFS containers and stable allocation checkpoints. Sampled
peaks are lower bounds; sums of file `st_blocks` are diagnostic rather than
unique physical allocation. Per-command RSS excludes persistent monitor daemons
and is not aggregate agent-tree peak RAM. Latency runs use a warm host filesystem
without a global cache purge. `--profile` adds overhead and is reported separately.

See [build and methodology details](../native/README.md) and
[measured results](../results.md).
