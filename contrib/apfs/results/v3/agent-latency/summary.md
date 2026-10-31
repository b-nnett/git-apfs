# Concurrent real-repository agent loops

Timings include process launch and /usr/bin/time instrumentation. p95 is descriptive; commands share repositories. CPU/RSS cover the timed command, not the sum of persistent monitor daemons. st_blocks diagnostics are not unique physical allocation. Physical peaks are sampled lower bounds.

| Variant | Agents | Active agents wall | Workflow incl. cleanup | Cache warm | Command p50 | Command p95 | Retained extra | Cleanup extra |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| native | 1 | 0.982s | 1.224s | 0.000s | 14.72 ms | 286.53 ms | not measured | not measured |
| native | 8 | 1.791s | 4.602s | 0.000s | 23.99 ms | 957.84 ms | not measured | not measured |
| native | 32 | 6.917s | 20.032s | 0.000s | 38.53 ms | 4261.10 ms | not measured | not measured |
| apfs | 1 | 1.222s | 1.461s | 0.000s | 17.42 ms | 295.38 ms | not measured | not measured |
| apfs | 8 | 3.412s | 5.561s | 0.000s | 53.87 ms | 1327.62 ms | not measured | not measured |
| apfs | 32 | 12.479s | 22.079s | 0.000s | 53.35 ms | 8763.83 ms | not measured | not measured |
| native-tuned | 1 | 0.892s | 1.179s | 0.000s | 15.63 ms | 295.78 ms | not measured | not measured |
| native-tuned | 8 | 1.775s | 4.762s | 0.000s | 19.45 ms | 951.90 ms | not measured | not measured |
| native-tuned | 32 | 6.261s | 20.785s | 0.000s | 29.45 ms | 3962.92 ms | not measured | not measured |
| apfs-tuned | 1 | 1.033s | 1.265s | 0.000s | 15.01 ms | 277.37 ms | not measured | not measured |
| apfs-tuned | 8 | 3.395s | 5.558s | 0.000s | 46.32 ms | 1292.60 ms | not measured | not measured |
| apfs-tuned | 32 | 12.184s | 21.777s | 0.000s | 52.31 ms | 8666.69 ms | not measured | not measured |
| apfs-cache | 1 | 1.280s | 1.517s | 1.131s | 39.92 ms | 475.57 ms | not measured | not measured |
| apfs-cache | 8 | 4.072s | 6.214s | 1.078s | 53.90 ms | 1832.13 ms | not measured | not measured |
| apfs-cache | 32 | 15.497s | 25.203s | 1.131s | 79.61 ms | 10855.53 ms | not measured | not measured |
| apfs-cache-tuned | 1 | 1.102s | 1.339s | 1.112s | 31.14 ms | 478.34 ms | not measured | not measured |
| apfs-cache-tuned | 8 | 4.140s | 6.344s | 1.123s | 52.59 ms | 1828.42 ms | not measured | not measured |
| apfs-cache-tuned | 32 | 15.450s | 25.018s | 1.104s | 76.02 ms | 11058.32 ms | not measured | not measured |

## Command distributions

| Variant | Agents | Command | p50 | p95 | Median CPU | Maximum command RSS |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| native | 1 | add | 14.16 ms | 158.40 ms | 0.000s | 8.16 MiB |
| native | 1 | commit | 14.17 ms | 125.03 ms | 0.020s | 8.11 MiB |
| native | 1 | diff | 12.29 ms | 154.91 ms | 0.020s | 6.84 MiB |
| native | 1 | first status | 162.37 ms | 163.88 ms | 0.170s | 7.91 MiB |
| native | 1 | restore | 9.19 ms | 9.62 ms | 0.000s | 6.73 MiB |
| native | 1 | status | 16.47 ms | 19.56 ms | 0.030s | 7.64 MiB |
| native | 1 | switch | 15.05 ms | 15.84 ms | 0.020s | 8.55 MiB |
| native | 1 | verify committed blobs | 6.47 ms | 7.12 ms | 0.000s | 4.66 MiB |
| native | 1 | worktree add | 359.82 ms | 367.40 ms | 0.320s | 58.56 MiB |
| native | 8 | add | 23.02 ms | 47.52 ms | 0.000s | 8.73 MiB |
| native | 8 | commit | 24.58 ms | 54.11 ms | 0.020s | 8.98 MiB |
| native | 8 | diff | 22.12 ms | 45.62 ms | 0.020s | 7.09 MiB |
| native | 8 | first status | 268.96 ms | 612.26 ms | 0.230s | 8.66 MiB |
| native | 8 | restore | 16.90 ms | 34.04 ms | 0.000s | 8.06 MiB |
| native | 8 | status | 26.65 ms | 44.13 ms | 0.030s | 8.20 MiB |
| native | 8 | switch | 26.13 ms | 37.23 ms | 0.020s | 9.31 MiB |
| native | 8 | verify committed blobs | 10.27 ms | 17.11 ms | 0.000s | 4.94 MiB |
| native | 8 | worktree add | 986.58 ms | 1026.62 ms | 0.555s | 66.84 MiB |
| native | 32 | add | 44.70 ms | 106.86 ms | 0.000s | 8.69 MiB |
| native | 32 | commit | 39.58 ms | 97.07 ms | 0.020s | 9.02 MiB |
| native | 32 | diff | 42.22 ms | 112.76 ms | 0.020s | 7.59 MiB |
| native | 32 | first status | 114.93 ms | 207.58 ms | 0.050s | 8.39 MiB |
| native | 32 | restore | 25.46 ms | 78.49 ms | 0.000s | 8.11 MiB |
| native | 32 | status | 36.52 ms | 83.60 ms | 0.030s | 8.19 MiB |
| native | 32 | switch | 35.41 ms | 62.75 ms | 0.020s | 9.31 MiB |
| native | 32 | verify committed blobs | 23.60 ms | 59.96 ms | 0.000s | 5.02 MiB |
| native | 32 | worktree add | 4738.80 ms | 5625.89 ms | 0.610s | 67.19 MiB |
| apfs | 1 | add | 14.06 ms | 171.87 ms | 0.000s | 8.19 MiB |
| apfs | 1 | commit | 16.18 ms | 176.32 ms | 0.030s | 8.27 MiB |
| apfs | 1 | diff | 14.16 ms | 171.11 ms | 0.030s | 6.81 MiB |
| apfs | 1 | first status | 189.40 ms | 189.71 ms | 0.210s | 7.95 MiB |
| apfs | 1 | restore | 10.71 ms | 11.40 ms | 0.000s | 6.86 MiB |
| apfs | 1 | status | 18.92 ms | 20.14 ms | 0.030s | 7.70 MiB |
| apfs | 1 | switch | 19.10 ms | 19.65 ms | 0.030s | 8.39 MiB |
| apfs | 1 | verify committed blobs | 7.03 ms | 7.22 ms | 0.000s | 4.70 MiB |
| apfs | 1 | worktree add | 357.90 ms | 364.23 ms | 1.340s | 18.39 MiB |
| apfs | 8 | add | 70.44 ms | 225.82 ms | 0.040s | 9.25 MiB |
| apfs | 8 | commit | 67.24 ms | 104.57 ms | 0.060s | 9.02 MiB |
| apfs | 8 | diff | 72.43 ms | 269.37 ms | 0.060s | 7.55 MiB |
| apfs | 8 | first status | 111.54 ms | 328.55 ms | 0.080s | 8.59 MiB |
| apfs | 8 | restore | 33.65 ms | 95.21 ms | 0.010s | 8.44 MiB |
| apfs | 8 | status | 35.78 ms | 85.64 ms | 0.040s | 8.36 MiB |
| apfs | 8 | switch | 31.14 ms | 60.63 ms | 0.030s | 8.92 MiB |
| apfs | 8 | verify committed blobs | 12.58 ms | 22.86 ms | 0.000s | 5.05 MiB |
| apfs | 8 | worktree add | 2522.58 ms | 2640.66 ms | 1.230s | 19.19 MiB |
| apfs | 32 | add | 45.55 ms | 148.27 ms | 0.000s | 8.66 MiB |
| apfs | 32 | commit | 53.51 ms | 153.97 ms | 0.030s | 8.92 MiB |
| apfs | 32 | diff | 47.94 ms | 125.21 ms | 0.030s | 7.23 MiB |
| apfs | 32 | first status | 90.57 ms | 209.45 ms | 0.050s | 8.58 MiB |
| apfs | 32 | restore | 58.06 ms | 159.68 ms | 0.020s | 8.31 MiB |
| apfs | 32 | status | 50.76 ms | 105.74 ms | 0.040s | 8.08 MiB |
| apfs | 32 | switch | 46.99 ms | 139.08 ms | 0.040s | 9.08 MiB |
| apfs | 32 | verify committed blobs | 29.09 ms | 113.56 ms | 0.000s | 5.06 MiB |
| apfs | 32 | worktree add | 9501.82 ms | 10539.17 ms | 1.260s | 19.31 MiB |
| native-tuned | 1 | add | 20.12 ms | 165.20 ms | 0.000s | 8.30 MiB |
| native-tuned | 1 | commit | 22.60 ms | 24.24 ms | 0.000s | 7.97 MiB |
| native-tuned | 1 | diff | 13.76 ms | 20.53 ms | 0.000s | 6.14 MiB |
| native-tuned | 1 | first status | 178.05 ms | 180.84 ms | 0.180s | 8.16 MiB |
| native-tuned | 1 | restore | 15.35 ms | 122.38 ms | 0.000s | 7.45 MiB |
| native-tuned | 1 | status | 11.97 ms | 22.83 ms | 0.000s | 7.42 MiB |
| native-tuned | 1 | switch | 13.31 ms | 14.13 ms | 0.000s | 8.34 MiB |
| native-tuned | 1 | verify committed blobs | 6.42 ms | 7.25 ms | 0.000s | 4.66 MiB |
| native-tuned | 1 | worktree add | 364.37 ms | 372.42 ms | 0.320s | 59.75 MiB |
| native-tuned | 8 | add | 41.76 ms | 174.61 ms | 0.020s | 9.28 MiB |
| native-tuned | 8 | commit | 19.34 ms | 33.00 ms | 0.000s | 8.73 MiB |
| native-tuned | 8 | diff | 17.78 ms | 28.61 ms | 0.000s | 6.88 MiB |
| native-tuned | 8 | first status | 199.20 ms | 355.93 ms | 0.120s | 8.77 MiB |
| native-tuned | 8 | restore | 25.30 ms | 68.60 ms | 0.000s | 8.11 MiB |
| native-tuned | 8 | status | 17.63 ms | 25.76 ms | 0.000s | 7.94 MiB |
| native-tuned | 8 | switch | 17.36 ms | 23.67 ms | 0.000s | 9.62 MiB |
| native-tuned | 8 | verify committed blobs | 11.87 ms | 18.82 ms | 0.000s | 4.89 MiB |
| native-tuned | 8 | worktree add | 995.83 ms | 1031.21 ms | 0.540s | 67.22 MiB |
| native-tuned | 32 | add | 41.44 ms | 99.71 ms | 0.000s | 8.92 MiB |
| native-tuned | 32 | commit | 29.91 ms | 78.86 ms | 0.000s | 8.86 MiB |
| native-tuned | 32 | diff | 31.44 ms | 80.69 ms | 0.000s | 7.09 MiB |
| native-tuned | 32 | first status | 133.44 ms | 266.83 ms | 0.060s | 8.56 MiB |
| native-tuned | 32 | restore | 24.23 ms | 72.95 ms | 0.000s | 8.12 MiB |
| native-tuned | 32 | status | 21.62 ms | 50.23 ms | 0.000s | 7.89 MiB |
| native-tuned | 32 | switch | 24.35 ms | 56.43 ms | 0.000s | 9.16 MiB |
| native-tuned | 32 | verify committed blobs | 21.11 ms | 56.08 ms | 0.000s | 5.02 MiB |
| native-tuned | 32 | worktree add | 4321.91 ms | 4634.92 ms | 0.580s | 67.67 MiB |
| apfs-tuned | 1 | add | 14.80 ms | 163.82 ms | 0.000s | 8.25 MiB |
| apfs-tuned | 1 | commit | 15.87 ms | 119.47 ms | 0.030s | 8.28 MiB |
| apfs-tuned | 1 | diff | 14.06 ms | 164.10 ms | 0.030s | 6.81 MiB |
| apfs-tuned | 1 | first status | 188.99 ms | 192.30 ms | 0.200s | 7.86 MiB |
| apfs-tuned | 1 | restore | 10.64 ms | 111.02 ms | 0.000s | 7.39 MiB |
| apfs-tuned | 1 | status | 14.98 ms | 15.80 ms | 0.030s | 7.62 MiB |
| apfs-tuned | 1 | switch | 19.27 ms | 19.75 ms | 0.030s | 8.39 MiB |
| apfs-tuned | 1 | verify committed blobs | 6.96 ms | 7.24 ms | 0.000s | 4.72 MiB |
| apfs-tuned | 1 | worktree add | 326.92 ms | 378.43 ms | 1.370s | 18.48 MiB |
| apfs-tuned | 8 | add | 49.79 ms | 161.78 ms | 0.020s | 8.72 MiB |
| apfs-tuned | 8 | commit | 48.94 ms | 70.33 ms | 0.040s | 9.17 MiB |
| apfs-tuned | 8 | diff | 50.17 ms | 141.91 ms | 0.040s | 7.39 MiB |
| apfs-tuned | 8 | first status | 88.79 ms | 220.54 ms | 0.070s | 8.66 MiB |
| apfs-tuned | 8 | restore | 43.67 ms | 62.99 ms | 0.020s | 8.42 MiB |
| apfs-tuned | 8 | status | 41.97 ms | 60.28 ms | 0.040s | 8.28 MiB |
| apfs-tuned | 8 | switch | 45.00 ms | 64.71 ms | 0.050s | 9.08 MiB |
| apfs-tuned | 8 | verify committed blobs | 14.88 ms | 28.13 ms | 0.000s | 5.12 MiB |
| apfs-tuned | 8 | worktree add | 2511.88 ms | 2633.04 ms | 1.250s | 18.98 MiB |
| apfs-tuned | 32 | add | 50.74 ms | 137.66 ms | 0.000s | 8.59 MiB |
| apfs-tuned | 32 | commit | 56.05 ms | 136.84 ms | 0.030s | 8.95 MiB |
| apfs-tuned | 32 | diff | 49.03 ms | 129.86 ms | 0.030s | 7.22 MiB |
| apfs-tuned | 32 | first status | 88.39 ms | 198.41 ms | 0.050s | 8.48 MiB |
| apfs-tuned | 32 | restore | 60.53 ms | 144.30 ms | 0.020s | 8.53 MiB |
| apfs-tuned | 32 | status | 41.08 ms | 104.77 ms | 0.030s | 8.12 MiB |
| apfs-tuned | 32 | switch | 48.70 ms | 149.48 ms | 0.030s | 9.17 MiB |
| apfs-tuned | 32 | verify committed blobs | 27.13 ms | 83.26 ms | 0.000s | 5.06 MiB |
| apfs-tuned | 32 | worktree add | 9589.43 ms | 10454.77 ms | 1.260s | 19.45 MiB |
| apfs-cache | 1 | add | 62.48 ms | 76.32 ms | 0.045s | 8.33 MiB |
| apfs-cache | 1 | commit | 32.27 ms | 46.07 ms | 0.050s | 8.28 MiB |
| apfs-cache | 1 | diff | 28.51 ms | 43.93 ms | 0.050s | 6.55 MiB |
| apfs-cache | 1 | first status | 34.67 ms | 48.02 ms | 0.050s | 7.78 MiB |
| apfs-cache | 1 | restore | 56.61 ms | 65.77 ms | 0.040s | 7.41 MiB |
| apfs-cache | 1 | status | 34.21 ms | 47.15 ms | 0.050s | 7.78 MiB |
| apfs-cache | 1 | switch | 51.27 ms | 64.91 ms | 0.060s | 9.14 MiB |
| apfs-cache | 1 | verify committed blobs | 6.28 ms | 7.23 ms | 0.000s | 4.70 MiB |
| apfs-cache | 1 | worktree add | 697.81 ms | 700.15 ms | 1.810s | 19.19 MiB |
| apfs-cache | 8 | add | 95.27 ms | 159.24 ms | 0.045s | 9.06 MiB |
| apfs-cache | 8 | commit | 44.68 ms | 83.37 ms | 0.030s | 8.97 MiB |
| apfs-cache | 8 | diff | 38.71 ms | 73.49 ms | 0.030s | 7.14 MiB |
| apfs-cache | 8 | first status | 58.14 ms | 172.15 ms | 0.040s | 8.47 MiB |
| apfs-cache | 8 | restore | 72.05 ms | 160.51 ms | 0.040s | 8.30 MiB |
| apfs-cache | 8 | status | 43.32 ms | 62.85 ms | 0.040s | 8.05 MiB |
| apfs-cache | 8 | switch | 80.12 ms | 138.96 ms | 0.065s | 9.36 MiB |
| apfs-cache | 8 | verify committed blobs | 15.54 ms | 26.75 ms | 0.000s | 5.09 MiB |
| apfs-cache | 8 | worktree add | 3086.55 ms | 3270.93 ms | 1.635s | 19.41 MiB |
| apfs-cache | 32 | add | 161.23 ms | 528.00 ms | 0.040s | 9.53 MiB |
| apfs-cache | 32 | commit | 58.34 ms | 139.06 ms | 0.030s | 8.80 MiB |
| apfs-cache | 32 | diff | 49.97 ms | 132.30 ms | 0.030s | 6.95 MiB |
| apfs-cache | 32 | first status | 67.36 ms | 109.51 ms | 0.040s | 7.83 MiB |
| apfs-cache | 32 | restore | 187.70 ms | 596.39 ms | 0.050s | 8.78 MiB |
| apfs-cache | 32 | status | 60.01 ms | 130.20 ms | 0.040s | 8.16 MiB |
| apfs-cache | 32 | switch | 131.03 ms | 478.18 ms | 0.070s | 9.69 MiB |
| apfs-cache | 32 | verify committed blobs | 31.72 ms | 145.04 ms | 0.000s | 5.11 MiB |
| apfs-cache | 32 | worktree add | 11756.13 ms | 12808.19 ms | 1.710s | 19.69 MiB |
| apfs-cache-tuned | 1 | add | 48.13 ms | 93.17 ms | 0.030s | 8.16 MiB |
| apfs-cache-tuned | 1 | commit | 16.39 ms | 59.89 ms | 0.030s | 8.38 MiB |
| apfs-cache-tuned | 1 | diff | 14.08 ms | 55.87 ms | 0.030s | 6.61 MiB |
| apfs-cache-tuned | 1 | first status | 21.35 ms | 56.86 ms | 0.040s | 7.72 MiB |
| apfs-cache-tuned | 1 | restore | 43.82 ms | 72.71 ms | 0.030s | 7.64 MiB |
| apfs-cache-tuned | 1 | status | 15.73 ms | 41.65 ms | 0.030s | 7.69 MiB |
| apfs-cache-tuned | 1 | switch | 50.01 ms | 53.14 ms | 0.060s | 9.09 MiB |
| apfs-cache-tuned | 1 | verify committed blobs | 7.10 ms | 7.27 ms | 0.000s | 4.70 MiB |
| apfs-cache-tuned | 1 | worktree add | 691.59 ms | 716.44 ms | 1.820s | 19.17 MiB |
| apfs-cache-tuned | 8 | add | 88.81 ms | 151.63 ms | 0.040s | 9.05 MiB |
| apfs-cache-tuned | 8 | commit | 45.18 ms | 78.92 ms | 0.030s | 8.92 MiB |
| apfs-cache-tuned | 8 | diff | 37.58 ms | 70.21 ms | 0.030s | 7.06 MiB |
| apfs-cache-tuned | 8 | first status | 72.72 ms | 119.26 ms | 0.050s | 8.41 MiB |
| apfs-cache-tuned | 8 | restore | 84.77 ms | 135.31 ms | 0.040s | 8.55 MiB |
| apfs-cache-tuned | 8 | status | 34.98 ms | 59.83 ms | 0.030s | 8.06 MiB |
| apfs-cache-tuned | 8 | switch | 89.76 ms | 157.31 ms | 0.070s | 9.41 MiB |
| apfs-cache-tuned | 8 | verify committed blobs | 17.34 ms | 25.23 ms | 0.000s | 5.06 MiB |
| apfs-cache-tuned | 8 | worktree add | 3055.03 ms | 3279.04 ms | 1.650s | 19.45 MiB |
| apfs-cache-tuned | 32 | add | 145.93 ms | 493.75 ms | 0.030s | 9.34 MiB |
| apfs-cache-tuned | 32 | commit | 58.62 ms | 150.77 ms | 0.030s | 8.97 MiB |
| apfs-cache-tuned | 32 | diff | 47.08 ms | 133.66 ms | 0.030s | 7.00 MiB |
| apfs-cache-tuned | 32 | first status | 62.52 ms | 115.58 ms | 0.040s | 8.45 MiB |
| apfs-cache-tuned | 32 | restore | 172.18 ms | 630.47 ms | 0.050s | 8.75 MiB |
| apfs-cache-tuned | 32 | status | 48.59 ms | 126.21 ms | 0.030s | 7.92 MiB |
| apfs-cache-tuned | 32 | switch | 122.81 ms | 375.02 ms | 0.060s | 9.62 MiB |
| apfs-cache-tuned | 32 | verify committed blobs | 33.73 ms | 149.23 ms | 0.000s | 5.11 MiB |
| apfs-cache-tuned | 32 | worktree add | 11725.59 ms | 13131.67 ms | 1.720s | 19.69 MiB |

Passed 53/54 trials.
