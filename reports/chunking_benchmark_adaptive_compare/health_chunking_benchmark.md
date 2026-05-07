# Health Insurance Chunking Benchmark

- Generated: `2026-05-07T09:22:41.115764+00:00`
- Documents: `103`
- Source characters: `7442006`
- Synthetic retrieval cases: `900`
- Case mix: `{'benefit': 540, 'claim': 47, 'provider': 50, 'eligibility': 54, 'general': 136, 'waiting': 15, 'premium': 29, 'exclusion': 20, 'table': 9}`

| Rank | Method | Overall | Retrieval | Quality | Hit@1 | Hit@3 | MRR@5 | Coverage@5 | Chunks | Avg tok | Redundancy |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Adaptive Semantic Density | 50.05 | 37.10 | 95.96 | 0.238 | 0.414 | 0.334 | 0.500 | 3152 | 567.6 | 0.961 |
| 2 | Late Chunking | 49.80 | 37.63 | 92.94 | 0.221 | 0.430 | 0.332 | 0.524 | 6126 | 359.1 | 1.181 |
| 3 | LLM Chunking | 49.73 | 38.90 | 88.12 | 0.254 | 0.433 | 0.352 | 0.519 | 1838 | 975.5 | 0.963 |
| 4 | Adaptive Chunking (Paper) | 45.81 | 32.61 | 92.59 | 0.198 | 0.370 | 0.291 | 0.449 | 3582 | 541.2 | 1.041 |
| 5 | Hierarchical Parent-Child | 43.74 | 30.03 | 92.32 | 0.169 | 0.348 | 0.264 | 0.424 | 9029 | 238.6 | 1.156 |
| 6 | Recursive | 42.66 | 28.38 | 93.25 | 0.173 | 0.320 | 0.252 | 0.391 | 6126 | 312.8 | 1.029 |
| 7 | Fixed-size | 41.18 | 31.97 | 73.84 | 0.192 | 0.356 | 0.287 | 0.434 | 5350 | 396.8 | 1.141 |
| 8 | Hybrid Recursive+Semantic | 39.51 | 25.58 | 88.92 | 0.160 | 0.279 | 0.228 | 0.354 | 5401 | 335.6 | 0.973 |
| 9 | Regex | 38.46 | 24.32 | 88.58 | 0.143 | 0.268 | 0.215 | 0.346 | 4817 | 386.1 | 0.999 |
| 10 | Markdown | 37.65 | 23.36 | 88.30 | 0.128 | 0.257 | 0.203 | 0.344 | 2991 | 621.9 | 0.999 |
| 11 | Sentence | 31.25 | 14.93 | 89.11 | 0.091 | 0.168 | 0.137 | 0.182 | 14904 | 124.8 | 0.997 |
| 12 | Semantic | 27.92 | 12.00 | 84.37 | 0.087 | 0.133 | 0.112 | 0.141 | 3329 | 557.4 | 0.997 |
| 13 | Project Chunker | 18.48 | 23.70 | 0.00 | 0.139 | 0.267 | 0.209 | 0.333 | 13331 | 873.4 | 6.255 |

## Recommendation

Best overall method: **Adaptive Semantic Density** (50.05/100).

Scores weight retrieval at 78% and chunk quality at 22%. Retrieval cases are generated from the private markdown corpus without manual labeling or database writes.
