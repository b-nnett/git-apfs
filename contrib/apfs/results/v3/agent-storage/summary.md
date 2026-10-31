# Concurrent real-repository agent loops

Timings include process launch and /usr/bin/time instrumentation. p95 is descriptive; commands share repositories. CPU/RSS cover the timed command, not the sum of persistent monitor daemons. st_blocks diagnostics are not unique physical allocation. Physical peaks are sampled lower bounds.

| Variant | Agents | Active agents wall | Workflow incl. cleanup | Cache warm | Command p50 | Command p95 | Retained extra | Cleanup extra |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| native | 1 | 1.238s | 1.477s | 0.000s | 15.14 ms | 236.17 ms | 62.97 MiB | 0.37 MiB |
| native | 8 | 3.401s | 7.971s | 0.000s | 25.65 ms | 2630.50 ms | 505.02 MiB | 3.03 MiB |
| native | 32 | 28.109s | 95.692s | 0.000s | 68.32 ms | 24328.98 ms | 2024.35 MiB | 12.05 MiB |
| apfs | 1 | 1.140s | 1.377s | 0.000s | 15.24 ms | 245.40 ms | 2.45 MiB | 0.66 MiB |
| apfs | 8 | 4.311s | 8.539s | 0.000s | 53.42 ms | 1798.01 ms | 19.29 MiB | 4.90 MiB |
| apfs | 32 | 41.524s | 92.014s | 0.000s | 127.57 ms | 37213.05 ms | 77.09 MiB | 19.00 MiB |
| native-tuned | 1 | 0.786s | 1.078s | 0.000s | 15.53 ms | 229.17 ms | 62.99 MiB | 0.37 MiB |
| native-tuned | 8 | 3.316s | 8.233s | 0.000s | 22.63 ms | 2608.80 ms | 505.23 MiB | 3.07 MiB |
| native-tuned | 32 | 52.205s | 103.659s | 0.000s | 71.14 ms | 48375.06 ms | 2024.59 MiB | 12.02 MiB |
| apfs-tuned | 1 | 0.819s | 1.044s | 0.000s | 23.83 ms | 141.51 ms | 2.46 MiB | 0.65 MiB |
| apfs-tuned | 8 | 4.587s | 9.520s | 0.000s | 35.34 ms | 2020.81 ms | 19.50 MiB | 4.89 MiB |
| apfs-tuned | 32 | 32.861s | 81.738s | 0.000s | 102.57 ms | 28803.07 ms | 77.63 MiB | 19.05 MiB |
| apfs-cache | 1 | 1.443s | 1.690s | 1.255s | 48.14 ms | 238.01 ms | 4.71 MiB | 2.87 MiB |
| apfs-cache | 8 | 4.888s | 10.048s | 1.083s | 32.28 ms | 2344.83 ms | 22.93 MiB | 8.43 MiB |
| apfs-cache | 32 | 40.075s | 77.204s | 1.168s | 107.66 ms | 36057.90 ms | 81.29 MiB | 23.24 MiB |
| apfs-cache-tuned | 1 | 1.481s | 1.722s | 1.430s | 36.26 ms | 271.67 ms | 4.62 MiB | 2.85 MiB |
| apfs-cache-tuned | 8 | 5.267s | 10.504s | 1.196s | 34.08 ms | 2381.89 ms | 22.69 MiB | 8.17 MiB |
| apfs-cache-tuned | 32 | 47.347s | 98.831s | 1.173s | 124.30 ms | 42459.71 ms | 80.84 MiB | 22.25 MiB |

## Command distributions

| Variant | Agents | Command | p50 | p95 | Median CPU | Maximum command RSS |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| native | 1 | add | 84.16 ms | 148.15 ms | 0.070s | 8.12 MiB |
| native | 1 | commit | 85.79 ms | 151.11 ms | 0.100s | 8.11 MiB |
| native | 1 | diff | 81.42 ms | 144.13 ms | 0.090s | 6.80 MiB |
| native | 1 | first status | 162.75 ms | 162.75 ms | 0.170s | 7.95 MiB |
| native | 1 | restore | 8.89 ms | 9.02 ms | 0.000s | 6.64 MiB |
| native | 1 | status | 16.08 ms | 16.44 ms | 0.030s | 7.67 MiB |
| native | 1 | switch | 14.34 ms | 14.34 ms | 0.020s | 8.55 MiB |
| native | 1 | verify committed blobs | 5.87 ms | 5.98 ms | 0.000s | 4.80 MiB |
| native | 1 | worktree add | 456.42 ms | 456.42 ms | 0.310s | 57.61 MiB |
| native | 8 | add | 27.87 ms | 93.34 ms | 0.000s | 8.73 MiB |
| native | 8 | commit | 24.45 ms | 31.63 ms | 0.020s | 8.72 MiB |
| native | 8 | diff | 25.06 ms | 84.32 ms | 0.020s | 7.31 MiB |
| native | 8 | first status | 110.73 ms | 124.04 ms | 0.085s | 8.42 MiB |
| native | 8 | restore | 16.46 ms | 24.74 ms | 0.000s | 7.36 MiB |
| native | 8 | status | 27.14 ms | 43.59 ms | 0.020s | 7.98 MiB |
| native | 8 | switch | 29.76 ms | 37.81 ms | 0.020s | 9.30 MiB |
| native | 8 | verify committed blobs | 14.06 ms | 23.45 ms | 0.000s | 4.81 MiB |
| native | 8 | worktree add | 2661.61 ms | 2693.13 ms | 0.390s | 61.95 MiB |
| native | 32 | add | 81.04 ms | 151.53 ms | 0.000s | 8.45 MiB |
| native | 32 | commit | 127.10 ms | 216.88 ms | 0.020s | 8.80 MiB |
| native | 32 | diff | 46.43 ms | 73.77 ms | 0.020s | 7.02 MiB |
| native | 32 | first status | 871.99 ms | 1339.31 ms | 0.040s | 8.08 MiB |
| native | 32 | restore | 63.85 ms | 130.43 ms | 0.000s | 7.78 MiB |
| native | 32 | status | 61.30 ms | 167.00 ms | 0.020s | 8.03 MiB |
| native | 32 | switch | 110.12 ms | 166.96 ms | 0.020s | 9.36 MiB |
| native | 32 | verify committed blobs | 15.03 ms | 55.27 ms | 0.000s | 5.16 MiB |
| native | 32 | worktree add | 24638.49 ms | 24941.48 ms | 0.500s | 63.11 MiB |
| apfs | 1 | add | 90.27 ms | 159.53 ms | 0.080s | 8.20 MiB |
| apfs | 1 | commit | 13.70 ms | 13.79 ms | 0.020s | 7.98 MiB |
| apfs | 1 | diff | 88.98 ms | 158.81 ms | 0.100s | 6.89 MiB |
| apfs | 1 | first status | 173.28 ms | 173.28 ms | 0.180s | 7.94 MiB |
| apfs | 1 | restore | 10.01 ms | 10.21 ms | 0.000s | 6.83 MiB |
| apfs | 1 | status | 17.10 ms | 17.31 ms | 0.020s | 7.64 MiB |
| apfs | 1 | switch | 16.91 ms | 16.91 ms | 0.020s | 8.42 MiB |
| apfs | 1 | verify committed blobs | 6.23 ms | 6.32 ms | 0.000s | 4.70 MiB |
| apfs | 1 | worktree add | 461.78 ms | 461.78 ms | 1.250s | 18.47 MiB |
| apfs | 8 | add | 63.78 ms | 84.76 ms | 0.040s | 8.78 MiB |
| apfs | 8 | commit | 53.56 ms | 73.88 ms | 0.035s | 9.05 MiB |
| apfs | 8 | diff | 57.54 ms | 63.46 ms | 0.050s | 7.33 MiB |
| apfs | 8 | first status | 75.42 ms | 199.12 ms | 0.060s | 8.53 MiB |
| apfs | 8 | restore | 41.87 ms | 65.50 ms | 0.020s | 8.20 MiB |
| apfs | 8 | status | 30.01 ms | 73.46 ms | 0.020s | 8.30 MiB |
| apfs | 8 | switch | 32.58 ms | 46.19 ms | 0.020s | 8.80 MiB |
| apfs | 8 | verify committed blobs | 12.17 ms | 15.73 ms | 0.000s | 4.95 MiB |
| apfs | 8 | worktree add | 3509.56 ms | 3526.25 ms | 1.120s | 19.06 MiB |
| apfs | 32 | add | 173.12 ms | 280.32 ms | 0.000s | 8.28 MiB |
| apfs | 32 | commit | 195.68 ms | 275.79 ms | 0.020s | 8.91 MiB |
| apfs | 32 | diff | 33.41 ms | 110.75 ms | 0.020s | 7.11 MiB |
| apfs | 32 | first status | 425.57 ms | 528.14 ms | 0.090s | 8.27 MiB |
| apfs | 32 | restore | 295.93 ms | 683.35 ms | 0.020s | 8.22 MiB |
| apfs | 32 | status | 95.35 ms | 169.07 ms | 0.030s | 8.08 MiB |
| apfs | 32 | switch | 141.37 ms | 361.01 ms | 0.020s | 9.03 MiB |
| apfs | 32 | verify committed blobs | 16.42 ms | 96.79 ms | 0.000s | 5.03 MiB |
| apfs | 32 | worktree add | 37275.49 ms | 37408.94 ms | 1.200s | 19.23 MiB |
| native-tuned | 1 | add | 19.61 ms | 20.38 ms | 0.000s | 6.92 MiB |
| native-tuned | 1 | commit | 23.20 ms | 23.23 ms | 0.000s | 7.84 MiB |
| native-tuned | 1 | diff | 14.24 ms | 17.17 ms | 0.000s | 6.14 MiB |
| native-tuned | 1 | first status | 178.04 ms | 178.04 ms | 0.180s | 8.22 MiB |
| native-tuned | 1 | restore | 12.79 ms | 13.49 ms | 0.000s | 6.80 MiB |
| native-tuned | 1 | status | 12.15 ms | 20.20 ms | 0.000s | 7.45 MiB |
| native-tuned | 1 | switch | 13.21 ms | 13.21 ms | 0.000s | 8.34 MiB |
| native-tuned | 1 | verify committed blobs | 6.20 ms | 6.30 ms | 0.000s | 4.66 MiB |
| native-tuned | 1 | worktree add | 382.59 ms | 382.59 ms | 0.320s | 57.23 MiB |
| native-tuned | 8 | add | 64.95 ms | 76.71 ms | 0.040s | 8.81 MiB |
| native-tuned | 8 | commit | 23.00 ms | 30.48 ms | 0.000s | 8.84 MiB |
| native-tuned | 8 | diff | 18.21 ms | 23.55 ms | 0.000s | 7.08 MiB |
| native-tuned | 8 | first status | 72.49 ms | 87.14 ms | 0.060s | 8.52 MiB |
| native-tuned | 8 | restore | 52.97 ms | 68.79 ms | 0.030s | 8.20 MiB |
| native-tuned | 8 | status | 19.49 ms | 24.54 ms | 0.000s | 7.81 MiB |
| native-tuned | 8 | switch | 23.17 ms | 30.02 ms | 0.000s | 9.12 MiB |
| native-tuned | 8 | verify committed blobs | 12.46 ms | 17.38 ms | 0.000s | 4.95 MiB |
| native-tuned | 8 | worktree add | 2671.29 ms | 2698.77 ms | 0.410s | 62.62 MiB |
| native-tuned | 32 | add | 114.29 ms | 236.27 ms | 0.000s | 8.41 MiB |
| native-tuned | 32 | commit | 129.04 ms | 226.96 ms | 0.000s | 8.75 MiB |
| native-tuned | 32 | diff | 42.71 ms | 78.90 ms | 0.000s | 7.03 MiB |
| native-tuned | 32 | first status | 837.65 ms | 2399.66 ms | 0.075s | 8.30 MiB |
| native-tuned | 32 | restore | 92.71 ms | 220.17 ms | 0.000s | 7.78 MiB |
| native-tuned | 32 | status | 37.84 ms | 73.63 ms | 0.000s | 7.88 MiB |
| native-tuned | 32 | switch | 76.27 ms | 130.05 ms | 0.000s | 9.47 MiB |
| native-tuned | 32 | verify committed blobs | 30.98 ms | 64.50 ms | 0.000s | 5.19 MiB |
| native-tuned | 32 | worktree add | 48811.50 ms | 49360.17 ms | 0.560s | 62.58 MiB |
| apfs-tuned | 1 | add | 23.59 ms | 23.76 ms | 0.020s | 7.20 MiB |
| apfs-tuned | 1 | commit | 24.33 ms | 24.62 ms | 0.040s | 8.11 MiB |
| apfs-tuned | 1 | diff | 21.52 ms | 22.12 ms | 0.030s | 6.48 MiB |
| apfs-tuned | 1 | first status | 28.82 ms | 28.82 ms | 0.040s | 7.59 MiB |
| apfs-tuned | 1 | restore | 19.17 ms | 19.39 ms | 0.000s | 7.00 MiB |
| apfs-tuned | 1 | status | 24.18 ms | 24.94 ms | 0.040s | 7.80 MiB |
| apfs-tuned | 1 | switch | 26.51 ms | 26.51 ms | 0.040s | 8.52 MiB |
| apfs-tuned | 1 | verify committed blobs | 6.09 ms | 6.27 ms | 0.000s | 4.70 MiB |
| apfs-tuned | 1 | worktree add | 479.57 ms | 479.57 ms | 1.260s | 18.45 MiB |
| apfs-tuned | 8 | add | 36.33 ms | 75.03 ms | 0.020s | 8.36 MiB |
| apfs-tuned | 8 | commit | 36.65 ms | 91.39 ms | 0.030s | 9.11 MiB |
| apfs-tuned | 8 | diff | 31.04 ms | 66.20 ms | 0.020s | 7.30 MiB |
| apfs-tuned | 8 | first status | 54.34 ms | 95.94 ms | 0.050s | 8.31 MiB |
| apfs-tuned | 8 | restore | 35.40 ms | 77.92 ms | 0.020s | 8.14 MiB |
| apfs-tuned | 8 | status | 32.79 ms | 41.19 ms | 0.040s | 8.20 MiB |
| apfs-tuned | 8 | switch | 44.73 ms | 49.98 ms | 0.040s | 9.00 MiB |
| apfs-tuned | 8 | verify committed blobs | 11.12 ms | 14.50 ms | 0.000s | 4.97 MiB |
| apfs-tuned | 8 | worktree add | 3990.10 ms | 3994.76 ms | 1.140s | 18.91 MiB |
| apfs-tuned | 32 | add | 101.80 ms | 256.41 ms | 0.000s | 8.48 MiB |
| apfs-tuned | 32 | commit | 144.34 ms | 262.73 ms | 0.020s | 8.94 MiB |
| apfs-tuned | 32 | diff | 38.86 ms | 75.92 ms | 0.020s | 7.00 MiB |
| apfs-tuned | 32 | first status | 309.22 ms | 402.74 ms | 0.030s | 8.22 MiB |
| apfs-tuned | 32 | restore | 195.84 ms | 374.97 ms | 0.020s | 8.31 MiB |
| apfs-tuned | 32 | status | 71.84 ms | 193.77 ms | 0.020s | 8.16 MiB |
| apfs-tuned | 32 | switch | 126.69 ms | 247.57 ms | 0.020s | 9.12 MiB |
| apfs-tuned | 32 | verify committed blobs | 21.28 ms | 65.03 ms | 0.000s | 5.08 MiB |
| apfs-tuned | 32 | worktree add | 29262.92 ms | 29569.72 ms | 1.180s | 19.28 MiB |
| apfs-cache | 1 | add | 67.23 ms | 67.50 ms | 0.050s | 8.16 MiB |
| apfs-cache | 1 | commit | 46.09 ms | 46.52 ms | 0.055s | 8.30 MiB |
| apfs-cache | 1 | diff | 42.23 ms | 42.25 ms | 0.050s | 6.44 MiB |
| apfs-cache | 1 | first status | 48.45 ms | 48.45 ms | 0.060s | 7.83 MiB |
| apfs-cache | 1 | restore | 59.90 ms | 60.13 ms | 0.050s | 7.50 MiB |
| apfs-cache | 1 | status | 48.05 ms | 48.21 ms | 0.050s | 7.70 MiB |
| apfs-cache | 1 | switch | 64.42 ms | 64.42 ms | 0.070s | 8.89 MiB |
| apfs-cache | 1 | verify committed blobs | 6.89 ms | 7.02 ms | 0.000s | 4.70 MiB |
| apfs-cache | 1 | worktree add | 749.45 ms | 749.45 ms | 1.650s | 19.03 MiB |
| apfs-cache | 8 | add | 49.64 ms | 213.72 ms | 0.020s | 9.09 MiB |
| apfs-cache | 8 | commit | 26.16 ms | 56.76 ms | 0.020s | 8.73 MiB |
| apfs-cache | 8 | diff | 18.19 ms | 30.18 ms | 0.020s | 7.19 MiB |
| apfs-cache | 8 | first status | 45.39 ms | 71.83 ms | 0.045s | 8.33 MiB |
| apfs-cache | 8 | restore | 52.98 ms | 75.53 ms | 0.020s | 8.22 MiB |
| apfs-cache | 8 | status | 27.68 ms | 39.58 ms | 0.020s | 7.98 MiB |
| apfs-cache | 8 | switch | 53.81 ms | 89.11 ms | 0.040s | 9.27 MiB |
| apfs-cache | 8 | verify committed blobs | 11.89 ms | 18.05 ms | 0.000s | 5.05 MiB |
| apfs-cache | 8 | worktree add | 4161.85 ms | 4325.06 ms | 1.485s | 19.42 MiB |
| apfs-cache | 32 | add | 155.81 ms | 351.59 ms | 0.020s | 9.36 MiB |
| apfs-cache | 32 | commit | 169.72 ms | 232.95 ms | 0.020s | 8.81 MiB |
| apfs-cache | 32 | diff | 45.49 ms | 91.54 ms | 0.020s | 6.98 MiB |
| apfs-cache | 32 | first status | 140.06 ms | 251.52 ms | 0.030s | 7.98 MiB |
| apfs-cache | 32 | restore | 289.16 ms | 472.30 ms | 0.030s | 8.66 MiB |
| apfs-cache | 32 | status | 78.37 ms | 108.65 ms | 0.030s | 8.05 MiB |
| apfs-cache | 32 | switch | 182.25 ms | 270.12 ms | 0.050s | 9.55 MiB |
| apfs-cache | 32 | verify committed blobs | 35.25 ms | 67.68 ms | 0.000s | 5.11 MiB |
| apfs-cache | 32 | worktree add | 36149.96 ms | 36288.15 ms | 1.710s | 19.61 MiB |
| apfs-cache-tuned | 1 | add | 67.84 ms | 96.85 ms | 0.050s | 8.58 MiB |
| apfs-cache-tuned | 1 | commit | 45.29 ms | 73.44 ms | 0.055s | 8.19 MiB |
| apfs-cache-tuned | 1 | diff | 42.49 ms | 70.30 ms | 0.055s | 6.72 MiB |
| apfs-cache-tuned | 1 | first status | 79.50 ms | 79.50 ms | 0.090s | 7.73 MiB |
| apfs-cache-tuned | 1 | restore | 61.57 ms | 89.67 ms | 0.050s | 7.64 MiB |
| apfs-cache-tuned | 1 | status | 13.27 ms | 70.49 ms | 0.020s | 7.72 MiB |
| apfs-cache-tuned | 1 | switch | 36.92 ms | 36.92 ms | 0.040s | 8.92 MiB |
| apfs-cache-tuned | 1 | verify committed blobs | 6.34 ms | 6.50 ms | 0.000s | 4.75 MiB |
| apfs-cache-tuned | 1 | worktree add | 786.45 ms | 786.45 ms | 1.650s | 19.31 MiB |
| apfs-cache-tuned | 8 | add | 74.52 ms | 233.41 ms | 0.040s | 9.12 MiB |
| apfs-cache-tuned | 8 | commit | 28.76 ms | 75.64 ms | 0.020s | 8.70 MiB |
| apfs-cache-tuned | 8 | diff | 21.19 ms | 68.17 ms | 0.020s | 7.22 MiB |
| apfs-cache-tuned | 8 | first status | 64.57 ms | 88.77 ms | 0.060s | 8.36 MiB |
| apfs-cache-tuned | 8 | restore | 52.46 ms | 106.59 ms | 0.020s | 8.41 MiB |
| apfs-cache-tuned | 8 | status | 21.24 ms | 28.43 ms | 0.020s | 7.89 MiB |
| apfs-cache-tuned | 8 | switch | 61.72 ms | 111.63 ms | 0.040s | 9.27 MiB |
| apfs-cache-tuned | 8 | verify committed blobs | 10.46 ms | 14.30 ms | 0.000s | 4.95 MiB |
| apfs-cache-tuned | 8 | worktree add | 4529.75 ms | 4653.33 ms | 1.495s | 19.59 MiB |
| apfs-cache-tuned | 32 | add | 179.01 ms | 418.35 ms | 0.020s | 9.39 MiB |
| apfs-cache-tuned | 32 | commit | 193.45 ms | 307.55 ms | 0.020s | 8.86 MiB |
| apfs-cache-tuned | 32 | diff | 28.86 ms | 88.88 ms | 0.020s | 6.98 MiB |
| apfs-cache-tuned | 32 | first status | 223.70 ms | 330.77 ms | 0.030s | 8.11 MiB |
| apfs-cache-tuned | 32 | restore | 353.74 ms | 797.20 ms | 0.030s | 8.69 MiB |
| apfs-cache-tuned | 32 | status | 68.55 ms | 120.92 ms | 0.020s | 7.92 MiB |
| apfs-cache-tuned | 32 | switch | 181.03 ms | 316.79 ms | 0.040s | 9.50 MiB |
| apfs-cache-tuned | 32 | verify committed blobs | 22.21 ms | 64.46 ms | 0.000s | 5.09 MiB |
| apfs-cache-tuned | 32 | worktree add | 42594.26 ms | 42727.55 ms | 1.750s | 19.75 MiB |

Passed 18/18 trials.
