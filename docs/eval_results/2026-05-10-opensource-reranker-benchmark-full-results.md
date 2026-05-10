# 2026-05-10 - Kết quả đầy đủ benchmark reranker open-source local

## 1. Tóm tắt nhanh

- Corpus benchmark: `data/health_insurance/health_insurance_markdowns_interpreted_cleaned`
- Collection dùng lại: `insurevn_qwen_prod_eval_20260510_full`
- Dense embedding hiện hành: `Qwen/Qwen3-Embedding-8B`
- Baseline retrieval để so sánh:
  - `hybrid`
  - `hybrid_company_filter`
- Kết luận chốt:
  - **Model rerank local phù hợp nhất hiện tại: `namdp-ptit/ViRanker`**
  - **Cách dùng khuyến nghị: `HYBRID + hard filters + ViRanker`**
  - **Không nên bật rerank trên `HYBRID` thuần nếu chưa có hard filters**, vì tất cả reranker local đều làm `source_hit@5` tệ hơn baseline không rerank.

## 2. Shortlist đã nghiên cứu

### 2.1 Candidate benchmark hoàn chỉnh

1. `BAAI/bge-reranker-v2-m3`
2. `Alibaba-NLP/gte-multilingual-reranker-base`
3. `namdp-ptit/ViRanker`
4. `Qwen/Qwen3-Reranker-0.6B` chạy ở cấu hình `4-bit + batch_size=1`

### 2.2 Candidate đã nghiên cứu nhưng không đưa vào full benchmark

1. `jinaai/jina-reranker-v2-base-multilingual`
   - Model mạnh và phổ biến, nhưng model card ghi giấy phép `CC-BY-NC-4.0` và hướng thương mại quay lại API/Jina offerings.
   - Vì mục tiêu là chốt default local reranker production, model này không phù hợp để chọn làm mặc định.
2. `Qwen/Qwen3-Reranker-4B`
   - Model card Qwen công bố điểm mạnh nhất trong dòng open-source reranker multilingual cùng series.
   - Đã thử smoke với cấu hình 4-bit trên máy `RTX 4060 8GB`, nhưng download/load kéo dài và không hoàn tất trong vòng benchmark thực dụng hiện tại.
   - Có thể benchmark bổ sung ở lượt sau nếu muốn dành một run dài riêng hoặc chuyển sang GPU VRAM lớn hơn.

## 3. Protocol benchmark

- Không re-index lại collection; dùng đúng collection đã index bằng `Qwen/Qwen3-Embedding-8B`.
- Benchmark set:
  - `health_insurance_rag_benchmark_v1.jsonl`
  - `health_insurance_rag_benchmark_v2.jsonl`
  - `health_insurance_rag_benchmark_v3_multifile.jsonl`
- Tổng case: `89`
- Top-k retrieval: `10`
- Scenarios được đánh giá cho từng reranker local:
  - `hybrid_rerank`
  - `hybrid_company_filter_rerank`
- Baseline so sánh lấy từ artifact cũ:
  - `hybrid`
  - `hybrid_company_filter`

## 4. Baseline tổng

| Baseline | source@5 | source@10 | MRR@5 | MRR@10 | quote@5 | quote@10 | phrase@5 | phrase@10 | latency avg ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `hybrid` | 0.7416 | 0.8652 | 0.5024 | 0.5180 | 0.5455 | 0.6883 | 0.4401 | 0.5208 | 658.791 |
| `hybrid_company_filter` | 0.9438 | 0.9438 | 0.8519 | 0.8519 | 0.8701 | 0.9091 | 0.5729 | 0.5924 | 366.127 |

## 5. Kết quả tổng theo model

### 5.1 `hybrid_rerank` so với baseline `hybrid`

| Model | source@5 | delta | source@10 | delta | MRR@5 | delta | MRR@10 | delta | quote@5 | delta | quote@10 | delta | rerank ms | runtime |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| baseline `hybrid` | 0.7416 | 0.0000 | 0.8652 | 0.0000 | 0.5024 | 0.0000 | 0.5180 | 0.0000 | 0.5455 | 0.0000 | 0.6883 | 0.0000 | 0.0 | - |
| `BAAI/bge-reranker-v2-m3` | 0.6854 | -0.0562 | 0.8539 | -0.0113 | 0.5285 | +0.0261 | 0.5511 | +0.0331 | 0.6494 | +0.1039 | 0.6883 | 0.0000 | 408.606 | 2:52.60 |
| `Alibaba-NLP/gte-multilingual-reranker-base` | 0.7079 | -0.0337 | 0.8652 | 0.0000 | 0.5697 | +0.0673 | 0.5911 | +0.0731 | 0.5974 | +0.0519 | 0.6883 | 0.0000 | 207.148 | 2:23.68 |
| `namdp-ptit/ViRanker` | 0.7303 | -0.0113 | 0.8427 | -0.0225 | 0.5266 | +0.0242 | 0.5415 | +0.0235 | 0.6234 | +0.0779 | 0.6753 | -0.0130 | 381.128 | 2:42.20 |
| `Qwen/Qwen3-Reranker-0.6B` 4-bit | 0.6742 | -0.0674 | 0.8539 | -0.0113 | 0.4768 | -0.0256 | 0.4997 | -0.0183 | 0.5844 | +0.0389 | 0.6883 | 0.0000 | 740.116 | 3:43.49 |

### 5.2 `hybrid_company_filter_rerank` so với baseline `hybrid_company_filter`

| Model | source@5 | delta | source@10 | delta | MRR@5 | delta | MRR@10 | delta | quote@5 | delta | quote@10 | delta | rerank ms | runtime |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| baseline `hybrid_company_filter` | 0.9438 | 0.0000 | 0.9438 | 0.0000 | 0.8519 | 0.0000 | 0.8519 | 0.0000 | 0.8701 | 0.0000 | 0.9091 | 0.0000 | 0.0 | - |
| `BAAI/bge-reranker-v2-m3` | 0.9326 | -0.0112 | 0.9438 | 0.0000 | 0.8674 | +0.0155 | 0.8687 | +0.0168 | 0.8961 | +0.0260 | 0.9091 | 0.0000 | 298.071 | 2:52.60 |
| `Alibaba-NLP/gte-multilingual-reranker-base` | 0.9326 | -0.0112 | 0.9438 | 0.0000 | 0.8552 | +0.0033 | 0.8571 | +0.0052 | 0.8182 | -0.0519 | 0.9091 | 0.0000 | 117.560 | 2:23.68 |
| `namdp-ptit/ViRanker` | 0.9438 | 0.0000 | 0.9438 | 0.0000 | 0.8781 | +0.0262 | 0.8781 | +0.0262 | 0.8831 | +0.0130 | 0.9091 | 0.0000 | 289.529 | 2:42.20 |
| `Qwen/Qwen3-Reranker-0.6B` 4-bit | 0.9213 | -0.0225 | 0.9438 | 0.0000 | 0.8219 | -0.0300 | 0.8249 | -0.0270 | 0.8312 | -0.0389 | 0.9091 | 0.0000 | 645.117 | 3:43.49 |

## 6. Xếp hạng thực dụng

### 6.1 Nếu tiêu chí là pipeline production khuyến nghị `HYBRID + company filter + rerank`

1. `namdp-ptit/ViRanker`
   - Giữ nguyên `source_hit_rate_at_5 = 0.9438`
   - Giữ nguyên `source_hit_rate_at_10 = 0.9438`
   - Tăng `MRR@5/@10` mạnh nhất lên `0.8781 / 0.8781`
   - Tăng `quote_hit_rate_at_5` lên `0.8831`
2. `BAAI/bge-reranker-v2-m3`
   - `quote_hit_rate_at_5` cao nhất `0.8961`
   - Nhưng làm giảm `source_hit_rate_at_5` từ `0.9438` xuống `0.9326`
3. `Alibaba-NLP/gte-multilingual-reranker-base`
   - Nhanh nhất
   - Uplift chất lượng yếu
   - `quote_hit_rate_at_5` còn giảm
4. `Qwen/Qwen3-Reranker-0.6B` 4-bit
   - Chạy được nhưng chậm nhất và metric tổng thể kém

### 6.2 Nếu tiêu chí là `HYBRID` thuần không hard filters

- Không model nào vượt baseline `hybrid` ở metric quan trọng nhất là `source_hit_rate_at_5`.
- `ViRanker` là model ít gây hại nhất ở `source@5` (`-0.0113`), nhưng vẫn không đủ để khuyến nghị bật rerank global cho mọi query.

## 7. Breakdown theo provider cho model thắng `ViRanker`

### 7.1 So với baseline `hybrid_company_filter`

| Provider | baseline source@5 | ViRanker source@5 | baseline MRR@5 | ViRanker MRR@5 | baseline quote@5 | ViRanker quote@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `aia.com.vn` | 0.3333 | 0.3333 | 0.1250 | 0.2500 | 0.6000 | 0.6000 |
| `baominh.com.vn` | 1.0000 | 1.0000 | 0.5067 | 0.6400 | 1.0000 | 1.0000 |
| `bic.vn` | 1.0000 | 1.0000 | 0.6722 | 0.7417 | 0.3333 | 0.3333 |
| `libertyinsurance.com.vn` | 0.8000 | 0.8000 | 0.8000 | 0.7000 | 0.8000 | 0.6000 |
| `pacific_cross_all_pdfs` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| `pti.com.vn` | 1.0000 | 1.0000 | 0.9621 | 0.9773 | 0.9464 | 0.9821 |

### 7.2 Diễn giải

- `AIA` vẫn là provider khó nhất; rerank không giải quyết được miss nguồn gốc ở đây.
- `BaoMinh`, `BIC`, `PTI` là các provider hưởng lợi rõ nhất về ranking quality.
- `Liberty` là trường hợp cần theo dõi nếu bật rerank, vì `quote@5` và `MRR@5` giảm.

## 8. Hiện vật đầu ra

### 8.1 Aggregate

- Summary CSV: `data/eval_runs/20260510_opensource_reranker_benchmark_summary.csv`

### 8.2 Per-model benchmark run

- `data/eval_runs/20260510_opensource_reranker_benchmark_bge_m3`
- `data/eval_runs/20260510_opensource_reranker_benchmark_gte_multilingual`
- `data/eval_runs/20260510_opensource_reranker_benchmark_viranker`
- `data/eval_runs/20260510_opensource_reranker_benchmark_qwen3_0_6b_4bit`

## 9. Nguồn tham khảo đã dùng

- `BAAI/bge-reranker-v2-m3`: https://huggingface.co/BAAI/bge-reranker-v2-m3
- `Alibaba-NLP/gte-multilingual-reranker-base`: https://huggingface.co/Alibaba-NLP/gte-multilingual-reranker-base
- `Qwen/Qwen3-Reranker-0.6B`: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- `Qwen/Qwen3-Reranker-4B`: https://huggingface.co/Qwen/Qwen3-Reranker-4B
- `namdp-ptit/ViRanker`: https://huggingface.co/namdp-ptit/ViRanker
- `jinaai/jina-reranker-v2-base-multilingual`: https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual
