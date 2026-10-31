# Concurrent real-repository agent loops

Timings include process launch and /usr/bin/time instrumentation. p95 is descriptive; commands share repositories. CPU/RSS cover the timed command, not the sum of persistent monitor daemons. st_blocks diagnostics are not unique physical allocation. Physical peaks are sampled lower bounds.

| Variant | Agents | Active agents wall | Workflow incl. cleanup | Cache warm | Command p50 | Command p95 | Retained extra | Cleanup extra |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| native | 8 | 41.726s | 123.130s | 0.000s | 2241.16 ms | 19150.60 ms | not measured | not measured |
| apfs | 8 | 66.498s | 126.682s | 0.000s | 420.59 ms | 28684.54 ms | not measured | not measured |

## Command distributions

| Variant | Agents | Command | p50 | p95 | Median CPU | Maximum command RSS |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| native | 8 | add | 138.68 ms | 254.75 ms | 0.050s | 27.61 MiB |
| native | 8 | commit | 2265.03 ms | 2503.18 ms | 2.100s | 28.38 MiB |
| native | 8 | diff | 2312.36 ms | 2561.97 ms | 2.155s | 27.14 MiB |
| native | 8 | first status | 2236.00 ms | 2595.37 ms | 1.540s | 26.94 MiB |
| native | 8 | restore | 122.01 ms | 180.80 ms | 0.040s | 27.50 MiB |
| native | 8 | status | 2590.03 ms | 2672.66 ms | 2.240s | 27.05 MiB |
| native | 8 | switch | 2245.14 ms | 2263.53 ms | 2.040s | 36.11 MiB |
| native | 8 | verify committed blobs | 54.73 ms | 64.20 ms | 0.000s | 5.19 MiB |
| native | 8 | worktree add | 19251.51 ms | 19401.24 ms | 6.875s | 122.06 MiB |
| apfs | 8 | add | 89.27 ms | 107.23 ms | 0.040s | 27.56 MiB |
| apfs | 8 | commit | 1888.88 ms | 2007.99 ms | 2.105s | 28.36 MiB |
| apfs | 8 | diff | 1883.24 ms | 2005.05 ms | 1.510s | 27.20 MiB |
| apfs | 8 | first status | 1774.84 ms | 1787.45 ms | 1.380s | 27.06 MiB |
| apfs | 8 | restore | 60.53 ms | 98.34 ms | 0.040s | 27.62 MiB |
| apfs | 8 | status | 1970.78 ms | 2152.62 ms | 2.490s | 27.11 MiB |
| apfs | 8 | switch | 1819.84 ms | 1829.63 ms | 2.355s | 35.97 MiB |
| apfs | 8 | verify committed blobs | 17.85 ms | 21.67 ms | 0.000s | 5.12 MiB |
| apfs | 8 | worktree add | 48602.49 ms | 48611.97 ms | 20.035s | 78.11 MiB |

Passed 2/2 trials.
