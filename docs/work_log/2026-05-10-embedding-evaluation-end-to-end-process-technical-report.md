# 2026-05-10 - Báo cáo kỹ thuật quy trình đánh giá embedding end-to-end

## 1. Tóm tắt điều hành

Báo cáo này mô tả quy trình chuẩn đã được áp dụng để đánh giá embedding model
cho corpus tiếng Việt bảo hiểm của InsureVN từ đầu đến cuối. Mục tiêu là biến
việc “chọn embedding model” từ một quyết định cảm tính thành một quy trình có
thể tái lập, có metric, có artifact, và có decision gate rõ ràng.

Quy trình thực tế đã đi qua đủ các bước:

1. đóng băng baseline chunking
2. chuẩn hóa benchmark corpus và source selection
3. mở rộng eval stack để hỗ trợ nhiều provider/model family
4. chạy indexing benchmark theo cùng một protocol
5. chạy retrieval eval `top_k=5` và `top_k=10`
6. đọc metric theo cả quality lẫn runtime/operability
7. ra shortlist và quyết định tạm thời

Kết quả cho thấy quy trình này đủ mạnh để phân biệt rõ 3 lớp model:

- nhóm mạnh: `Qwen/Qwen3-Embedding-8B`, `BAAI/bge-m3`, `intfloat/multilingual-e5-large`
- baseline nhanh nhưng yếu: `MiniLM`
- không phù hợp với corpus: `riphunter7001x/bge-base-financial`

## 2. Mục tiêu và phạm vi

- Tài liệu hóa **quy trình đánh giá embedding** từ đầu đến cuối
- Ghi lại:
  - inputs
  - control variables
  - pipeline thực thi
  - model-specific handling
  - metric được dùng để chấm
  - logic ra quyết định
- Là tài liệu tham chiếu cho các vòng benchmark kế tiếp:
  - hybrid retrieval
  - reranker
  - answer/citation evaluation

Phạm vi báo cáo này là **retrieval embedding evaluation**, không bao gồm:

- thay đổi benchmark dataset
- thay đổi chunking winner
- đánh giá answer generation
- đánh giá human review workflow

## 3. Bối cảnh

Trước vòng đánh giá embedding, baseline chunking của repo đã được chốt. Điều
đó rất quan trọng vì embedding benchmark đúng phải **cố định mọi biến khác**
ngoài embedding model.

Phân loại công việc:

- Data pipeline phase: `Training & Eval`
- Evidence foundation: `Qdrant`
- System tier: `Core Services / Evaluation tooling`

Môi trường benchmark:

- Python `3.12.3`
- GPU `NVIDIA GeForce RTX 4060 8GB`
- Local Qdrant persisted trên filesystem
- Corpus sạch từ:
  `data/health_insurance/health_insurance_markdowns_interpreted_cleaned`

## 4. Triển khai quy trình end-to-end

### 4.1 Bước 1 - Đóng băng baseline chunking

Mọi embedding model trong vòng benchmark này đều dùng cùng baseline:

- strategy: `hierarchical_header_recursive`
- `chunk_size=900`
- `chunk_overlap=150`

Lý do:

- nếu vừa đổi chunking vừa đổi embedding thì không biết model thắng do đâu
- việc này cô lập đúng biến cần đo: `embedding model`

### 4.2 Bước 2 - Cố định benchmark dataset và selection rule

Input đánh giá được cố định:

- benchmark JSONL:
  `data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.jsonl`
- source selection: `expected`
- source documents: `42`
- retrieval benchmark cases: `100`

Ý nghĩa:

- mỗi model nhìn cùng corpus
- cùng source universe
- cùng câu hỏi
- cùng expected evidence

### 4.3 Bước 3 - Chuẩn hóa eval stack

Để benchmark nhiều model công bằng, eval stack phải hỗ trợ:

- nhiều provider
- nhiều model family
- nhiều quy ước encode query/document

Các thay đổi chính:

- reorg `src/eval` theo boundary rõ hơn
- thêm `build_retrieval_embeddings(...)`
- thêm adapter `GoogleGenAIEmbeddings`
- thêm adapter `Qwen3AutoModelEmbeddings`
- giữ import compatibility wrapper để CLI cũ không gãy

### 4.4 Bước 4 - Xử lý model-specific behavior

Đây là bước tối quan trọng. Nếu encode sai giao thức của model, benchmark sẽ
không còn công bằng.

#### E5

- query phải thêm `query: `
- document phải thêm `passage: `

#### Qwen3 Embedding

- query dùng prompt instruction theo model card
- pooling dùng `last_token_pool(...)`
- trên GPU 8GB phải dùng `4-bit` quantization + `device_map=auto`

#### Gemini

- phải dùng direct `google.genai` content embedding call
- phải có multi-key fallback
- phải parse `retryDelay` và cooldown theo từng key

### 4.5 Bước 5 - Chạy indexing benchmark

Mỗi model được chạy cùng một pattern:

```bash
python scripts/05_training_eval/run_streaming_chunking_embedding_qdrant.py \
  --benchmark-path ... \
  --corpus-dir ... \
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

Output chính của bước này:

- `streaming_file_results.csv`
- `streaming_strategy_results.csv`
- `streaming_chunk_records.jsonl`
- persisted Qdrant collection
- embedding cache SQLite

### 4.6 Bước 6 - Chạy retrieval evaluation

Sau khi có persisted index, mỗi model được chấm retrieval bằng 2 mức:

- `top_k=5`
- `top_k=10`

Pattern lệnh:

```bash
python scripts/05_training_eval/run_persisted_qdrant_retrieval_eval.py \
  --source-run-dir <run> \
  --output-dir <run>/retrieval_eval_top5 \
  --top-k 5 \
  --embedding-provider <provider> \
  --embedding-model-name <model> \
  --embedding-device cuda
```

và lặp lại cho `--top-k 10`.

Output chính:

- `retrieval_strategy_summary.csv`
- `retrieval_case_metrics.csv`
- `retrievals.jsonl`

### 4.7 Bước 7 - Đọc metric đúng thứ tự ưu tiên

Với bài toán insurance-VN của InsureVN, metric nên đọc theo thứ tự:

1. `required_source_recall_at_k`
2. `line_overlap_recall_at_k`
3. `primary_mrr_at_k`
4. runtime / operability

Lý do:

- cần lấy đúng nguồn chứng cứ trước
- sau đó mới quan tâm việc span có sát hay không
- rồi mới đến ranking quality tổng quát

### 4.8 Bước 8 - Đọc quality cùng runtime

Không được chỉ nhìn quality. Cần đọc thêm:

- `stream_duration_seconds`
- retrieval eval duration
- batch size khả dụng
- mức độ cần adapter đặc biệt
- mức độ ổn định của provider/runtime

Ví dụ:

- `Qwen/Qwen3-Embedding-8B` mạnh nhất về quality nhưng rất nặng
- `BAAI/bge-m3` yếu hơn chút ở một số metric, nhưng dễ vận hành hơn nhiều

### 4.9 Bước 9 - Xử lý partial/failed runs

Không phải mọi run đều nên bị loại bỏ hoàn toàn khỏi báo cáo.

Rule thực tế đã dùng:

- full-corpus completed run: được xếp hạng chính thức
- partial run nhưng có artifact meaningful: vẫn ghi vào report, nhưng
  **không xếp hạng ngang hàng**
- failed/blocked exploratory run: ghi lại chronology và lý do để tránh lặp lỗi

Đó là lý do `gemini-embedding-2` vẫn có mặt trong kết quả, nhưng ở trạng thái
`unranked`.

## 5. Bằng chứng và lệnh đã chạy

### 5.1 Các model đã chạy trong quy trình này

- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- `BAAI/bge-m3`
- `intfloat/multilingual-e5-large`
- `riphunter7001x/bge-base-financial`
- `Qwen/Qwen3-Embedding-8B`
- `gemini-embedding-2` cùng các attempt Gemini fallback

### 5.2 Verify code

```bash
pytest tests/unit/test_eval_strategy_embeddings.py \
  tests/unit/test_persisted_qdrant_retrieval_eval.py \
  tests/unit/test_streaming_qdrant_chunking.py \
  tests/unit/test_config.py -q
```

Kết quả cuối:

- `37 passed`
- `6 warnings`

```bash
ruff check src/eval/embeddings/adapters.py \
  src/eval/embeddings/__init__.py \
  tests/unit/test_eval_strategy_embeddings.py
```

Kết quả:

- `All checks passed!`

### 5.3 Artifact đại diện của quy trình

- [MiniLM run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_minilm)
- [bge-m3 run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_bge_m3)
- [e5-large run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_e5_large)
- [bge-base-financial run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_bge_base_financial)
- [qwen3-embedding-8b run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_qwen3_embedding_8b)
- [Gemini direct partial run](/home/quangnhvn34/dev/me/InsureVN/data/eval_runs/20260510_embedding_benchmark_gemini_768_direct)

## 6. Xác minh

- Tất cả full-corpus local runs đều tạo:
  - Qdrant persisted index
  - `streaming_strategy_results.csv`
  - retrieval eval `top5`
  - retrieval eval `top10`
- `Qwen3AutoModelEmbeddings` smoke test thành công
- `Qwen/Qwen3-Embedding-8B` đã chạy full-corpus end-to-end thành công trên GPU
  `RTX 4060 8GB`
- `gemini-embedding-2` vẫn không có full-corpus success do quota, không phải do
  import error hay adapter crash

## 7. Kết quả

### 7.1 Kết quả cuối theo quality

| Rank | Model | Top5 MRR | Top5 source recall | Top5 line recall | Top10 MRR | Top10 source recall | Top10 line recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `Qwen/Qwen3-Embedding-8B` | 0.5967 | 0.8300 | 0.4283 | 0.6031 | 0.8800 | 0.5083 |
| 2 | `BAAI/bge-m3` | 0.5772 | 0.8100 | 0.3583 | 0.5865 | 0.8900 | 0.4583 |
| 3 | `intfloat/multilingual-e5-large` | 0.5482 | 0.7600 | 0.3550 | 0.5609 | 0.8600 | 0.4767 |
| 4 | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 0.3990 | 0.6200 | 0.2183 | 0.4143 | 0.7300 | 0.2533 |
| 5 | `riphunter7001x/bge-base-financial` | 0.2413 | 0.4100 | 0.0817 | 0.2569 | 0.5200 | 0.0883 |

### 7.2 Kết quả cuối theo tradeoff vận hành

| Rank | Model | Lý do |
| --- | --- | --- |
| 1 | `BAAI/bge-m3` | recall rất mạnh, runtime chấp nhận được, đường triển khai đơn giản |
| 2 | `Qwen/Qwen3-Embedding-8B` | quality cao nhất nhưng runtime nặng và cần adapter riêng |
| 3 | `intfloat/multilingual-e5-large` | chất lượng tốt, cần encode prefix đúng |
| 4 | `MiniLM` | nhanh, nhưng quality kém |
| 5 | `bge-base-financial` | không phù hợp với corpus VN |

### 7.3 Kết luận quy trình

Quy trình này đã giúp trả lời được ba câu hỏi quan trọng:

1. Model nào mạnh nhất về dense retrieval quality?
   - `Qwen/Qwen3-Embedding-8B`
2. Model nào hợp production thực tế nhất hiện tại?
   - `BAAI/bge-m3`
3. Model nào nên loại khỏi shortlist?
   - `riphunter7001x/bge-base-financial`

## 8. Rủi ro và giới hạn

- Quy trình hiện tại mới đánh giá **dense retrieval**
- Chưa phản ánh:
  - hybrid sparse+dense
  - reranker uplift
  - answer quality cuối cùng
  - citation correctness
- `Qwen/Qwen3-Embedding-8B` dùng adapter tùy biến, nên khi môi trường package
  thay đổi cần verify lại
- Gemini vẫn cần vòng benchmark khác khi quota không còn là bottleneck

## 9. Việc tiếp theo

1. Giữ nguyên quy trình này làm protocol chuẩn cho mọi model embedding mới
2. Dùng `BAAI/bge-m3` và `Qwen/Qwen3-Embedding-8B` cho vòng `hybrid BM25 + dense`
3. Sau hybrid, mới chạy reranker
4. Sau reranker, mới chạy answer/citation evaluation
5. Nếu cần quyết định production ngay bây giờ:
   - default: `BAAI/bge-m3`
   - upper-bound quality reference: `Qwen/Qwen3-Embedding-8B`
