# 2026-05-10 - Kết quả đầy đủ benchmark tất cả embedding methods

## 1. Tóm tắt điều hành

Đây là báo cáo canonical cho toàn bộ embedding methods đã được benchmark trên
baseline chunking hiện tại của InsureVN. Báo cáo này thay thế các report
embedding kết quả trước đó để tránh trùng lặp.

Kết luận ngắn:

- Nếu ưu tiên **chất lượng retrieval dense tốt nhất**, `Qwen/Qwen3-Embedding-8B`
  đang đứng đầu trong các full-corpus run hoàn tất.
- Nếu ưu tiên **tradeoff chất lượng, tốc độ, độ đơn giản triển khai và vận hành
  local**, `BAAI/bge-m3` vẫn là lựa chọn production pragmatically tốt nhất.
- `intfloat/multilingual-e5-large` là lựa chọn multilingual mạnh và ổn định,
  nhưng đứng sau `Qwen3-Embedding-8B` và `bge-m3`.
- `riphunter7001x/bge-base-financial` không phù hợp với corpus tiếng Việt bảo
  hiểm của repo này.
- `gemini-embedding-2` đã có adapter/fallback tốt hơn rõ rệt, nhưng vẫn chỉ có
  partial run vì quota runtime nên chưa thể xếp hạng công bằng với các model
  local đã hoàn tất full-corpus.

## 2. Mục tiêu và phạm vi

- Ghi lại **đầy đủ** các phương pháp embedding đã chạy.
- Ghi lại cùng một chỗ:
  - cấu hình benchmark
  - trạng thái từng run
  - metric retrieval
  - tradeoff tốc độ/chất lượng
  - artifact và raw file results
- Làm tài liệu kết quả duy nhất cho embedding benchmark ngày `2026-05-10`.

Phạm vi benchmark:

- Benchmark JSONL:
  `data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.jsonl`
- Corpus:
  `data/health_insurance/health_insurance_markdowns_interpreted_cleaned`
- Số source document: `42`
- Số benchmark case retrieval: `100`
- Source selection: `expected`
- Baseline chunking cố định:
  - `hierarchical_header_recursive`
  - `chunk_size=900`
  - `chunk_overlap=150`
- Retrieval evaluation:
  - `top_k=5`
  - `top_k=10`

## 3. Môi trường benchmark

- OS: `Linux-6.17.0-23-generic-x86_64-with-glibc2.39`
- Python: `3.12.3`
- GPU: `NVIDIA GeForce RTX 4060`
- VRAM: `8188 MiB`
- NVIDIA driver: `595.58.03`

Phân loại công việc:

- Data pipeline phase: `Training & Eval`
- Evidence foundation: `Qdrant`
- System tier: `Core Services / Evaluation tooling`

## 4. Danh sách phương pháp đã đánh giá

### 4.1 Full-corpus local runs

| Method | Provider | Adapter path | Output dim | Batch | Stream status | Ghi chú |
| --- | --- | --- | ---: | ---: | --- | --- |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `sentence_transformers` | `SentenceTransformerEmbeddings` | 384 | 32 | `completed` | Baseline nhanh |
| `BAAI/bge-m3` | `sentence_transformers` | `SentenceTransformerEmbeddings` | 1024 | 8 | `completed` | Ứng viên open-source mạnh |
| `intfloat/multilingual-e5-large` | `sentence_transformers` | `SentenceTransformerEmbeddings` + E5 prefix | 1024 | 8 | `completed` | Query/doc prefix bắt buộc |
| `riphunter7001x/bge-base-financial` | `sentence_transformers` | `SentenceTransformerEmbeddings` | 768 | 8 | `completed` | English finance fine-tune |
| `Qwen/Qwen3-Embedding-8B` | `sentence_transformers` | `Qwen3AutoModelEmbeddings` | 4096 | 4 | `completed` | `transformers + 4-bit + device_map=auto` |

### 4.2 Google Gemini partial / exploratory runs

| Run | Model | Provider | Batch | Status | Ghi chú |
| --- | --- | --- | ---: | --- | --- |
| `20260510_embedding_benchmark_gemini_768` | `gemini-embedding-2` | `google_genai` | 16 | `partial` | Early invalid/blocked attempt |
| `20260510_embedding_benchmark_gemini_768_valid` | `gemini-embedding-2` | `google_genai` | 16 | `partial` | Alias fixed, vẫn quota blocked |
| `20260510_embedding_benchmark_gemini_768_pool` | `gemini-embedding-2` | `google_genai` | 16 | `partial` | Multi-key pool attempt sơ bộ |
| `20260510_embedding_benchmark_gemini_768_direct` | `gemini-embedding-2` | `google_genai` | 16 | `partial` | Best Gemini partial run |
| `20260510_embedding_benchmark_gemini_768_all_keys` | `gemini-embedding-2` | `google_genai` | 16 | `interrupted` | Multi-key fallback enabled |
| `20260510_embedding_benchmark_gemini_768_all_keys_wait` | `gemini-embedding-2` | `google_genai` | 32 | `interrupted` | `retryDelay` wait enabled |
| `20260510_embedding_benchmark_gemini_768_all_keys_smart` | `gemini-embedding-2` | `google_genai` | 32 | `interrupted` | merged cache + smart cooldown |

## 5. Ghi chú triển khai theo model family

### 5.1 `intfloat/multilingual-e5-large`

- Query phải có prefix `query: `
- Document phải có prefix `passage: `
- Benchmark đã encode đúng quy tắc này

### 5.2 `Qwen/Qwen3-Embedding-8B`

- Đường `SentenceTransformer(...)` mặc định không đủ ổn định trong môi trường
  hiện tại cho model này.
- Repo đã thêm adapter riêng `Qwen3AutoModelEmbeddings`:
  - dùng `transformers.AutoModel`
  - `BitsAndBytesConfig(load_in_4bit=True)`
  - `device_map="auto"`
  - `last_token_pool(...)` theo model card Qwen
  - query prompt:
    `Instruct: Given a web search query, retrieve relevant passages that answer the query`
- Smoke test adapter đã trả về vector `4096` chiều cho cả query và document.

### 5.3 `riphunter7001x/bge-base-financial`

- Snapshot local ban đầu chưa materialize đủ file, nên phải fetch lại snapshot
  đầy đủ trước khi load benchmark.
- Sau khi snapshot hoàn chỉnh, model load và benchmark bình thường.

### 5.4 `gemini-embedding-2`

- Đã đọc đủ `GOOGLE_API_KEY_1..N` từ `.env`
- Đã resolve alias env kiểu `RAG_EMBEDDING_API_KEY=GOOGLE_API_KEY_1`
- Đã có:
  - multi-key failover
  - parse `retryDelay`
  - per-key cooldown
  - invalid key disable
  - direct `google.genai` embedding call
- Hạn chế còn lại: quota runtime, không còn là blocker code path cơ bản

## 6. Bằng chứng và lệnh chính đã chạy

### 6.1 Verify code

```bash
pytest tests/unit/test_eval_strategy_embeddings.py \
  tests/unit/test_persisted_qdrant_retrieval_eval.py \
  tests/unit/test_streaming_qdrant_chunking.py \
  tests/unit/test_config.py -q
```

Kết quả vòng verify cuối:

- `37 passed`
- `6 warnings`

```bash
ruff check src/eval/embeddings/adapters.py \
  src/eval/embeddings/__init__.py \
  tests/unit/test_eval_strategy_embeddings.py
```

Kết quả:

- `All checks passed!`

### 6.2 Pattern command cho full-corpus local runs

Indexing:

```bash
python scripts/05_training_eval/run_streaming_chunking_embedding_qdrant.py \
  --benchmark-path data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.jsonl \
  --corpus-dir data/health_insurance/health_insurance_markdowns_interpreted_cleaned \
  --output-dir <run>/out \
  --qdrant-work-dir <run>/qdrant \
  --embedding-cache-path <run>/embedding_cache.sqlite \
  --strategies hierarchical_header_recursive \
  --limit-documents 0 \
  --source-selection expected \
  --embedding-provider <provider> \
  --embedding-model-name <model> \
  --embedding-device cuda \
  --embedding-batch-size <batch> \
  --keep-qdrant
```

Retrieval eval:

```bash
python scripts/05_training_eval/run_persisted_qdrant_retrieval_eval.py \
  --source-run-dir <run> \
  --output-dir <run>/retrieval_eval_top5 \
  --top-k 5 \
  --embedding-provider <provider> \
  --embedding-model-name <model> \
  --embedding-device cuda
```

```bash
python scripts/05_training_eval/run_persisted_qdrant_retrieval_eval.py \
  --source-run-dir <run> \
  --output-dir <run>/retrieval_eval_top10 \
  --top-k 10 \
  --embedding-provider <provider> \
  --embedding-model-name <model> \
  --embedding-device cuda
```

## 7. Kết quả đầy đủ

### 7.1 Bảng tổng hợp tất cả run dùng để đánh giá

| Run | Model | Provider | Batch | Stream status | Files | Qdrant points | Cache entries | Stream duration (s) | Top5 MRR | Top5 source recall | Top10 MRR | Top10 source recall | Ghi chú |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `20260510_embedding_benchmark_minilm` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `sentence_transformers` | 32 | `completed` | 42 | 9518 | 8619 | 64.115 | 0.3990 | 0.6200 | 0.4143 | 0.7300 | Baseline local |
| `20260510_embedding_benchmark_bge_m3` | `BAAI/bge-m3` | `sentence_transformers` | 8 | `completed` | 42 | 9518 | 8619 | 299.893 | 0.5772 | 0.8100 | 0.5865 | 0.8900 | Strong open-source |
| `20260510_embedding_benchmark_e5_large` | `intfloat/multilingual-e5-large` | `sentence_transformers` | 8 | `completed` | 42 | 9518 | 8619 | 302.385 | 0.5482 | 0.7600 | 0.5609 | 0.8600 | Strong multilingual |
| `20260510_embedding_benchmark_bge_base_financial` | `riphunter7001x/bge-base-financial` | `sentence_transformers` | 8 | `completed` | 42 | 9518 | 8619 | 158.170 | 0.2413 | 0.4100 | 0.2569 | 0.5200 | Poor VN fit |
| `20260510_embedding_benchmark_qwen3_embedding_8b` | `Qwen/Qwen3-Embedding-8B` | `sentence_transformers` | 4 | `completed` | 42 | 9518 | 8619 | 1710.045 | 0.5967 | 0.8300 | 0.6031 | 0.8800 | Best quality, heaviest run |
| `20260510_embedding_benchmark_gemini_768_direct` | `gemini-embedding-2` | `google_genai` | 16 | `partial` | 15 complete / 27 fail | 2265 | 3125 | 376.757 | 0.4532 | 0.5500 | 0.4588 | 0.5900 | Best Gemini partial run |

### 7.2 Kết quả retrieval đầy đủ cho các run có eval

| Model | Stream duration (s) | Top5 MRR | Top5 source recall | Top5 line recall | Top5 eval duration (s) | Top10 MRR | Top10 source recall | Top10 line recall | Top10 eval duration (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 64.115 | 0.3990 | 0.6200 | 0.2183 | 9.343 | 0.4143 | 0.7300 | 0.2533 | 1.814 |
| `BAAI/bge-m3` | 299.893 | 0.5772 | 0.8100 | 0.3583 | 13.737 | 0.5865 | 0.8900 | 0.4583 | 4.194 |
| `intfloat/multilingual-e5-large` | 302.385 | 0.5482 | 0.7600 | 0.3550 | 15.339 | 0.5609 | 0.8600 | 0.4767 | 4.420 |
| `riphunter7001x/bge-base-financial` | 158.170 | 0.2413 | 0.4100 | 0.0817 | 10.183 | 0.2569 | 0.5200 | 0.0883 | 3.288 |
| `Qwen/Qwen3-Embedding-8B` | 1710.045 | 0.5967 | 0.8300 | 0.4283 | 62.645 | 0.6031 | 0.8800 | 0.5083 | 16.239 |
| `gemini-embedding-2` (`direct`, partial index) | 376.757 | 0.4532 | 0.5500 | 0.2417 | 43.972 | 0.4588 | 0.5900 | 0.2967 | 1.098 |

### 7.3 Xếp hạng theo chất lượng retrieval thuần dense

1. `Qwen/Qwen3-Embedding-8B`
2. `BAAI/bge-m3`
3. `intfloat/multilingual-e5-large`
4. `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
5. `riphunter7001x/bge-base-financial`

`gemini-embedding-2` không được xếp hạng chính thức vì chỉ có partial run.

### 7.4 Xếp hạng theo tradeoff chất lượng / vận hành

1. `BAAI/bge-m3`
2. `Qwen/Qwen3-Embedding-8B`
3. `intfloat/multilingual-e5-large`
4. `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
5. `riphunter7001x/bge-base-financial`

Lý do:

- `bge-m3` thua nhẹ `Qwen3-Embedding-8B` ở quality, nhưng rẻ hơn nhiều về
  compute/time và không cần adapter riêng
- `Qwen3-Embedding-8B` là upper-bound retrieval quality rất mạnh, nhưng nặng
  hơn đáng kể trên GPU 8GB

### 7.5 Nhận xét từng phương pháp

#### `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

- Nhanh nhất để indexing
- Chất lượng thấp hơn rõ rệt so với nhóm model lớn
- Hợp để làm smoke baseline, không hợp để chốt production default

#### `BAAI/bge-m3`

- Rất mạnh ở `required_source_recall`
- `top10 required_source_recall=0.8900`, cao nhất trong các full runs
- Không nặng bất thường như Qwen
- Là điểm cân bằng tốt nhất hiện tại

#### `intfloat/multilingual-e5-large`

- Chất lượng tốt và ổn định
- `line_overlap_recall@10=0.4767`, nhỉnh hơn `bge-m3`
- Cần rất cẩn thận với E5 prefix, nếu encode sai sẽ làm benchmark méo

#### `riphunter7001x/bge-base-financial`

- Tốc độ indexing không tệ
- Retrieval quality quá thấp với corpus tiếng Việt bảo hiểm:
  - `top5 source recall=0.4100`
  - `top10 source recall=0.5200`
  - `top5 line recall=0.0817`
  - `top10 line recall=0.0883`
- Nên loại khỏi shortlist

#### `Qwen/Qwen3-Embedding-8B`

- Mạnh nhất về quality trong full runs:
  - `top5 MRR=0.5967`
  - `top5 source recall=0.8300`
  - `top5 line recall=0.4283`
  - `top10 MRR=0.6031`
  - `top10 line recall=0.5083`
- Chỉ thua `bge-m3` đúng `0.01` ở `top10 source recall`
- Nhược điểm lớn nhất là runtime:
  - indexing `1710.045s`
  - retrieval eval top5 `62.645s`
  - retrieval eval top10 `16.239s`

### 7.6 Các file chậm nhất ở 2 run mới

#### `riphunter7001x/bge-base-financial`

| Source file | Chunks | Upsert seconds |
| --- | ---: | ---: |
| `pacific_cross_all_pdfs/15042026_Medical-Provider-List-VN/...` | 1211 | 20.626 |
| `pacific_cross_all_pdfs/15042026_Medical-Provider-List-EN/...` | 1221 | 20.092 |
| `pacific_cross_all_pdfs/18082025_Medical-Provider-List-VN/...` | 485 | 15.248 |
| `aia.com.vn/Ho-Chieu-Suc-Khoe-AIA-Danh-sach-co-so-y-te/...` | 643 | 9.555 |

#### `Qwen/Qwen3-Embedding-8B`

| Source file | Chunks | Upsert seconds |
| --- | ---: | ---: |
| `pacific_cross_all_pdfs/15042026_Medical-Provider-List-VN/...` | 1211 | 280.108 |
| `pacific_cross_all_pdfs/15042026_Medical-Provider-List-EN/...` | 1221 | 267.055 |
| `pacific_cross_all_pdfs/18082025_Medical-Provider-List-VN/...` | 485 | 153.112 |
| `aia.com.vn/Ho-Chieu-Suc-Khoe-AIA-Danh-sach-co-so-y-te/...` | 643 | 131.846 |

### 7.7 Chronology các attempt Gemini

| Thứ tự | Run | Mục tiêu kỹ thuật | Kết quả |
| --- | --- | --- | --- |
| 1 | `20260510_embedding_benchmark_gemini_768` | thử provider Google ban đầu | `42/42` file fail, `0` điểm |
| 2 | `20260510_embedding_benchmark_gemini_768_valid` | sửa alias key/đầu vào hợp lệ | vẫn `0` điểm, tạo `97` cache entry |
| 3 | `20260510_embedding_benchmark_gemini_768_pool` | thử multi-key pool sơ bộ | vẫn `0` điểm, không có partial index có ích |
| 4 | `20260510_embedding_benchmark_gemini_768_direct` | chuyển sang `google.genai` direct | tốt nhất: `15/42` file complete, `2265` điểm |
| 5 | `20260510_embedding_benchmark_gemini_768_all_keys` | bật collector nhiều key từ `.env` | interrupted sau `2` file complete |
| 6 | `20260510_embedding_benchmark_gemini_768_all_keys_wait` | thêm wait theo `retryDelay` | complete file `485` chunks, sau đó ngủ quota dài |
| 7 | `20260510_embedding_benchmark_gemini_768_all_keys_smart` | merged cache + sticky key + cooldown thông minh | cache tốt hơn, nhưng vẫn quota-bound |

## 8. Artifact index

### 8.1 Full local run directories

- [MiniLM run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_minilm)
- [bge-m3 run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_bge_m3)
- [e5-large run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_e5_large)
- [bge-base-financial run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_bge_base_financial)
- [qwen3-embedding-8b run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_qwen3_embedding_8b)

### 8.2 Gemini run directories

- [gemini direct run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_gemini_768_direct)
- [gemini all keys run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_gemini_768_all_keys)
- [gemini all keys wait run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_gemini_768_all_keys_wait)
- [gemini all keys smart run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_gemini_768_all_keys_smart)

### 8.3 Raw result files quan trọng

- [bge-base-financial file results](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_bge_base_financial/out/streaming_file_results.csv)
- [bge-base-financial top5 summary](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_bge_base_financial/retrieval_eval_top5/retrieval_strategy_summary.csv)
- [bge-base-financial top10 summary](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_bge_base_financial/retrieval_eval_top10/retrieval_strategy_summary.csv)
- [qwen3-embedding-8b file results](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_qwen3_embedding_8b/out/streaming_file_results.csv)
- [qwen3-embedding-8b top5 summary](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_qwen3_embedding_8b/retrieval_eval_top5/retrieval_strategy_summary.csv)
- [qwen3-embedding-8b top10 summary](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_qwen3_embedding_8b/retrieval_eval_top10/retrieval_strategy_summary.csv)
- [gemini direct file results](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_gemini_768_direct/out/streaming_file_results.csv)
- [gemini direct top5 summary](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_gemini_768_direct/retrieval_eval_top5/retrieval_strategy_summary.csv)
- [gemini direct top10 summary](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_gemini_768_direct/retrieval_eval_top10/retrieval_strategy_summary.csv)

## 9. Xác minh

- Pytest vùng thay đổi: `37 passed`
- Ruff check vùng thay đổi: `All checks passed!`
- `Qwen3AutoModelEmbeddings` smoke test thành công với vector `4096` chiều
- Collector eval đọc được toàn bộ Google API key đã đánh số trong `.env`
- Gemini fallback hiện bị chặn bởi quota runtime, không còn bị chặn bởi lỗi
  adapter cơ bản

## 10. Rủi ro, giới hạn và kết luận

### 10.1 Rủi ro và giới hạn

- Benchmark này mới dừng ở **dense retrieval evaluation**
- Chưa có:
  - hybrid BM25 + dense
  - reranker evaluation
  - answer correctness evaluation
  - citation correctness evaluation
  - human review final slice
- `Qwen/Qwen3-Embedding-8B` phụ thuộc vào adapter riêng thay vì đường
  `SentenceTransformer(...)` thuần
- `gemini-embedding-2` chưa có full-corpus run thành công vì quota

### 10.2 Kết luận

- Nếu cần **best dense quality**: chọn `Qwen/Qwen3-Embedding-8B`
- Nếu cần **best production tradeoff ngay bây giờ**: chọn `BAAI/bge-m3`
- Nếu cần một lựa chọn multilingual mạnh và ít nặng hơn Qwen: chọn
  `intfloat/multilingual-e5-large`
- `riphunter7001x/bge-base-financial` nên loại khỏi shortlist tiếng Việt

## 11. Việc tiếp theo

1. Chạy `hybrid BM25 + dense` cho `BAAI/bge-m3` và `Qwen/Qwen3-Embedding-8B`
2. Giữ `BAAI/bge-m3` làm default nếu production budget compute chặt
3. Dùng `Qwen/Qwen3-Embedding-8B` làm upper-bound chất lượng hoặc offline
   benchmark reference
4. Chạy lại Gemini khi có quota reset hoặc project/key paid riêng
5. Sau khi chốt retriever, mới thêm reranker và answer/citation eval
