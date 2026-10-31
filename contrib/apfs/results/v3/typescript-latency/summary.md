# Concurrent real-repository agent loops

Timings include process launch and /usr/bin/time instrumentation. p95 is descriptive; commands share repositories. CPU/RSS cover the timed command, not the sum of persistent monitor daemons. st_blocks diagnostics are not unique physical allocation. Physical peaks are sampled lower bounds.

| Variant | Agents | Active agents wall | Workflow incl. cleanup | Cache warm | Command p50 | Command p95 | Retained extra | Cleanup extra |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| native | 1 | 5.438s | 9.048s | 0.000s | 94.76 ms | 1165.47 ms | not measured | not measured |
| apfs | 1 | 7.046s | 11.097s | 0.000s | 116.07 ms | 1560.75 ms | not measured | not measured |
| native-tuned | 1 | 5.019s | 8.755s | 0.000s | 37.61 ms | 1290.65 ms | not measured | not measured |
| apfs-tuned | 1 | 6.988s | 11.115s | 0.000s | 100.21 ms | 1693.70 ms | not measured | not measured |
| apfs-cache | 1 | 25.460s | 29.688s | 17.220s | 139.93 ms | 6082.21 ms | not measured | not measured |
| apfs-cache-tuned | 1 | 25.445s | 29.836s | 16.638s | 115.90 ms | 6096.15 ms | not measured | not measured |

## Command distributions

| Variant | Agents | Command | p50 | p95 | Median CPU | Maximum command RSS |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| native | 1 | add | 68.44 ms | 96.61 ms | 0.060s | 27.22 MiB |
| native | 1 | commit | 110.65 ms | 139.48 ms | 0.470s | 27.91 MiB |
| native | 1 | diff | 90.53 ms | 120.16 ms | 0.405s | 26.75 MiB |
| native | 1 | first status | 196.60 ms | 196.60 ms | 0.490s | 26.66 MiB |
| native | 1 | restore | 60.42 ms | 86.84 ms | 0.050s | 27.22 MiB |
| native | 1 | status | 131.90 ms | 133.99 ms | 0.490s | 26.66 MiB |
| native | 1 | switch | 89.17 ms | 89.17 ms | 0.430s | 35.66 MiB |
| native | 1 | verify committed blobs | 7.16 ms | 7.33 ms | 0.000s | 4.84 MiB |
| native | 1 | worktree add | 4072.06 ms | 4072.06 ms | 3.900s | 104.97 MiB |
| apfs | 1 | add | 59.89 ms | 80.03 ms | 0.050s | 27.20 MiB |
| apfs | 1 | commit | 137.01 ms | 162.28 ms | 0.515s | 27.98 MiB |
| apfs | 1 | diff | 112.96 ms | 136.69 ms | 0.490s | 26.88 MiB |
| apfs | 1 | first status | 270.68 ms | 270.68 ms | 0.850s | 26.75 MiB |
| apfs | 1 | restore | 53.20 ms | 72.34 ms | 0.045s | 27.27 MiB |
| apfs | 1 | status | 158.95 ms | 159.34 ms | 0.540s | 26.70 MiB |
| apfs | 1 | switch | 123.22 ms | 123.22 ms | 0.500s | 35.66 MiB |
| apfs | 1 | verify committed blobs | 7.30 ms | 7.50 ms | 0.000s | 4.81 MiB |
| apfs | 1 | worktree add | 5430.96 ms | 5430.96 ms | 22.770s | 80.05 MiB |
| native-tuned | 1 | add | 40.72 ms | 41.72 ms | 0.025s | 27.39 MiB |
| native-tuned | 1 | commit | 58.02 ms | 78.54 ms | 0.225s | 28.05 MiB |
| native-tuned | 1 | diff | 45.88 ms | 66.78 ms | 0.200s | 26.95 MiB |
| native-tuned | 1 | first status | 353.26 ms | 353.26 ms | 0.620s | 26.70 MiB |
| native-tuned | 1 | restore | 34.88 ms | 35.55 ms | 0.020s | 27.48 MiB |
| native-tuned | 1 | status | 34.51 ms | 44.44 ms | 0.020s | 26.91 MiB |
| native-tuned | 1 | switch | 57.21 ms | 57.21 ms | 0.030s | 35.58 MiB |
| native-tuned | 1 | verify committed blobs | 6.61 ms | 6.71 ms | 0.000s | 4.77 MiB |
| native-tuned | 1 | worktree add | 4102.82 ms | 4102.82 ms | 3.940s | 114.45 MiB |
| apfs-tuned | 1 | add | 37.72 ms | 37.79 ms | 0.030s | 27.36 MiB |
| apfs-tuned | 1 | commit | 113.36 ms | 114.25 ms | 0.510s | 28.14 MiB |
| apfs-tuned | 1 | diff | 93.64 ms | 94.22 ms | 0.475s | 26.91 MiB |
| apfs-tuned | 1 | first status | 415.79 ms | 415.79 ms | 1.000s | 26.72 MiB |
| apfs-tuned | 1 | restore | 31.97 ms | 32.18 ms | 0.020s | 27.42 MiB |
| apfs-tuned | 1 | status | 111.68 ms | 112.37 ms | 0.530s | 26.86 MiB |
| apfs-tuned | 1 | switch | 126.26 ms | 126.26 ms | 0.510s | 35.84 MiB |
| apfs-tuned | 1 | verify committed blobs | 7.35 ms | 7.51 ms | 0.000s | 4.81 MiB |
| apfs-tuned | 1 | worktree add | 5527.43 ms | 5527.43 ms | 22.870s | 79.81 MiB |
| apfs-cache | 1 | add | 143.35 ms | 145.89 ms | 0.135s | 27.20 MiB |
| apfs-cache | 1 | commit | 110.98 ms | 111.19 ms | 0.495s | 27.92 MiB |
| apfs-cache | 1 | diff | 87.08 ms | 90.52 ms | 0.465s | 26.77 MiB |
| apfs-cache | 1 | first status | 151.00 ms | 151.00 ms | 0.540s | 26.70 MiB |
| apfs-cache | 1 | restore | 140.92 ms | 144.16 ms | 0.135s | 27.27 MiB |
| apfs-cache | 1 | status | 159.86 ms | 163.41 ms | 0.540s | 26.70 MiB |
| apfs-cache | 1 | switch | 240.38 ms | 240.38 ms | 0.630s | 37.38 MiB |
| apfs-cache | 1 | verify committed blobs | 6.87 ms | 6.94 ms | 0.000s | 4.81 MiB |
| apfs-cache | 1 | worktree add | 23607.69 ms | 23607.69 ms | 39.730s | 84.61 MiB |
| apfs-cache-tuned | 1 | add | 147.06 ms | 151.76 ms | 0.140s | 27.41 MiB |
| apfs-cache-tuned | 1 | commit | 115.33 ms | 115.62 ms | 0.475s | 28.06 MiB |
| apfs-cache-tuned | 1 | diff | 92.86 ms | 97.45 ms | 0.470s | 26.91 MiB |
| apfs-cache-tuned | 1 | first status | 166.94 ms | 166.94 ms | 0.570s | 26.72 MiB |
| apfs-cache-tuned | 1 | restore | 148.11 ms | 153.55 ms | 0.130s | 27.42 MiB |
| apfs-cache-tuned | 1 | status | 105.85 ms | 115.11 ms | 0.500s | 26.86 MiB |
| apfs-cache-tuned | 1 | switch | 234.68 ms | 234.68 ms | 0.610s | 37.81 MiB |
| apfs-cache-tuned | 1 | verify committed blobs | 7.39 ms | 7.60 ms | 0.000s | 4.81 MiB |
| apfs-cache-tuned | 1 | worktree add | 23680.57 ms | 23680.57 ms | 39.800s | 86.73 MiB |

Passed 6/6 trials.
