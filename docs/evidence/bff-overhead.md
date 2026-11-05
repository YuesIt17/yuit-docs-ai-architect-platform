# BFF Overhead

Raw output behind the numbers in [ADR-010](../../architecture/adr/ADR-010-bff-auth.md). Docker Desktop on Windows, 3.8 GiB VM, MOCK LLM, `STORE_BACKEND=live`, one replica each of the BFF and the API, 2026-11-05.

## How to reproduce

Deploy with `KP_AUTH=oidc`, get a session id by logging in, and run [`bff_overhead.py`](../../app/scripts/k8s/bff_overhead.py) in a pod in the `kp` namespace built from `kp-api:dev`. It needs a Restricted security context. It decrypts the session with the demo key to get the token for the direct calls.

## Limits of this measurement

- The client is Python and shares the VM with everything it measures, so the figures with several clients are noisy and partly measure the client.
- Run 1's direct `mean` and both runs' chat `p99` are dominated by a few outliers on the direct side.
- Direct and proxied blocks alternate only in the sequential scenario. In the others, one side runs after the other.

## Run 1

```text
GET /v1/me, sequential  (n=1500 per side, ms)
              direct   via BFF     added
p50             8.19     10.04      1.85
p95            20.82     23.12      2.30
p99            36.34     36.36      0.03
mean           24.25     11.83    -12.41

GET /v1/me, 8 clients  (n=800 per side, ms)
              direct   via BFF     added
p50            48.74     61.66     12.92
p95            92.26    127.85     35.59
p99           257.58    172.73    -84.85
mean           54.99     69.54     14.55
throughput  direct 141 req/s, via BFF 113 req/s

GET /v1/me, 16 clients  (n=1600 per side, ms)
              direct   via BFF     added
p50            93.91    119.88     25.98
p95           176.56    262.19     85.63
p99           291.66    344.35     52.70
mean          105.43    136.44     31.01
throughput  direct 149 req/s, via BFF 114 req/s

POST /v1/chat stream, time to first bytes  (n=60 per side, ms)
              direct   via BFF     added
p50           435.72    452.65     16.93
p95           860.62    744.59   -116.03
p99          6043.51    983.19  -5060.33
mean          589.65    483.15   -106.49

POST /v1/chat stream, total  (n=60 per side, ms)
              direct   via BFF     added
p50           437.21    453.98     16.77
p95           862.17    745.99   -116.18
p99          6045.43    984.75  -5060.69
mean          591.47    485.46   -106.01
```

## Run 2

```text
GET /v1/me, sequential  (n=1500 per side, ms)
              direct   via BFF     added
p50             4.37      5.86      1.50
p95            13.12     12.06     -1.07
p99            22.60     24.13      1.52
mean            9.14      7.04     -2.10

GET /v1/me, 8 clients  (n=800 per side, ms)
              direct   via BFF     added
p50            76.11     70.10     -6.01
p95           145.82    135.71    -10.11
p99           251.82    403.66    151.84
mean           84.69     79.20     -5.49
throughput  direct 92 req/s, via BFF 98 req/s

GET /v1/me, 16 clients  (n=1600 per side, ms)
              direct   via BFF     added
p50           104.77    127.30     22.53
p95           171.61    225.80     54.20
p99           346.81    367.92     21.11
mean          113.38    138.30     24.92
throughput  direct 138 req/s, via BFF 114 req/s

POST /v1/chat stream, time to first bytes  (n=60 per side, ms)
              direct   via BFF     added
p50           383.71    403.62     19.91
p95           628.79    673.96     45.17
p99          3437.33    766.22  -2671.11
mean          458.77    428.28    -30.49

POST /v1/chat stream, total  (n=60 per side, ms)
              direct   via BFF     added
p50           384.92    405.63     20.70
p95           630.28    675.25     44.98
p99          3438.78    767.29  -2671.49
mean          460.07    430.04    -30.03
```

## Memory

`docker stats` for the containers and `free -m` inside the VM.

| State | BFF | Keycloak | `free -m` available | Swap used |
| ----- | --- | -------- | ------------------- | --------- |
| After the first benchmark run | 13 MiB | 573 MiB | 1,336 MB | 831 of 1,024 MB |
| With the full observability stack (other, unrelated containers were also running) | 12 MiB | 586 MiB | 1,126 MB | 1,024 of 1,024 MB |
| Observability stack stopped, after all runs | 16 MiB | 593 MiB | 1,473 MB | 976 of 1,024 MB |

Before the upgrade, in demo mode, the containers together used about 1.1 GiB. Keycloak started in 176 s on its first start, including the realm import.

## Live refresh

Real Keycloak with a 300 s access token. Two waves of 30 concurrent requests, each near token expiry:

```text
logged in; before: {}
codes: {200: 30}
after first wave: {'success': 1.0}
second wave codes (rotated token redeemed): {200: 30}
after second wave: {'success': 2.0}
```
