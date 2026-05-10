# 2026-05-10 - Báo cáo kỹ thuật đánh giá reranker open-source local

## 1. Tóm tắt điều hành

Trong ngày 2026-05-10, tôi đã nghiên cứu shortlist reranker open-source multilingual/Vietnamese phù hợp với stack hiện tại của InsureVN, triển khai local reranker adapter trong `src/services/document_retrieval`, benchmark hoàn chỉnh trên benchmark bảo hiểm sức khỏe tiếng Việt hiện có, và chốt model mặc định mới.

Quyết định cuối cùng:

- **Chọn `namdp-ptit/ViRanker` làm local reranker mặc định**
- **Chỉ khuyến nghị dùng rerank trong pipeline `HYBRID + hard filters + rerank`**
- **Không khuyến nghị bật rerank trên `HYBRID` thuần**, vì tất cả model local benchmark được đều làm giảm `source_hit_rate_at_5` so với baseline không rerank

Đồng thời, cấu hình production mặc định đã được chuyển khỏi `Jina API` sang local `ViRanker` trong `.env`, `.env.example`, và `src/core/config.py`.

## 2. Mục tiêu và phạm vi

### 2.1 Mục tiêu

1. Dừng phụ thuộc vào rerank API cho đường production mặc định
2. Nghiên cứu các reranker open-source mạnh, phù hợp với data bảo hiểm tiếng Việt
3. Benchmark lại rerank trên collection đã index bằng `Qwen/Qwen3-Embedding-8B`
4. Chọn model reranker tốt nhất và thực dụng nhất cho project

### 2.2 Phạm vi

- Data pipeline phase: `Training & Eval`
- System tier: `Core Services`
- Evidence foundation: `Qdrant`
- Retrieval lane chính: `Fast Q&A` và `Verified Advisor` style retrieval benchmark

Không có thay đổi vào `src/eval`. Toàn bộ adapter production nằm trong `src/services/document_retrieval` đúng theo yêu cầu tách biệt code đánh giá và code chính thức.

## 3. Bối cảnh

Trước task này, project đã chốt:

- Dense embedding production: `Qwen/Qwen3-Embedding-8B`
- Collection benchmark production-style: `insurevn_qwen_prod_eval_20260510_full`
- Baseline retrieval tốt nhất hiện tại:
  - `hybrid`
  - `hybrid_company_filter`

Các run trước đó cho thấy:

- `hard filters` tạo uplift rất lớn trên benchmark tiếng Việt bảo hiểm
- `Jina API rerank` không ổn định do rate limit `429`
- Người dùng yêu cầu bỏ API rerank và chuyển sang open-source local reranker

## 4. Triển khai

### 4.1 Nghiên cứu shortlist

Tôi đã rà các model card và tài liệu chính thức để chọn shortlist thực dụng:

1. `BAAI/bge-reranker-v2-m3`
   - Multilingual, mạnh, phổ biến, Apache 2.0
2. `Alibaba-NLP/gte-multilingual-reranker-base`
   - Multilingual, gọn, tốc độ tốt, Apache 2.0
3. `namdp-ptit/ViRanker`
   - Vietnamese cross-encoder, Apache 2.0
4. `Qwen/Qwen3-Reranker-0.6B`
   - Qwen series mới, multilingual, context dài, Apache 2.0

Candidate bị loại khỏi full benchmark:

1. `jinaai/jina-reranker-v2-base-multilingual`
   - Model tốt nhưng giấy phép `CC-BY-NC-4.0`, không phù hợp để chốt mặc định production
2. `Qwen/Qwen3-Reranker-4B`
   - Có tiềm năng chất lượng cao nhất theo model card, nhưng chưa hoàn tất smoke benchmark trong giới hạn phần cứng và thời gian hiện tại

### 4.2 Bổ sung local reranker adapter trong `src/`

Đã thêm:

- `src/services/document_retrieval/huggingface_rerank_cross_encoder.py`
  - Adapter local cho `sentence_transformers.CrossEncoder`
  - Dùng `rank()` và map score về đúng thứ tự input `BaseCrossEncoder.score()`
- `src/services/document_retrieval/rerank_cross_encoder.py`
  - Factory thống nhất cho:
    - `JinaRerankCrossEncoder`
    - `HuggingFaceRerankCrossEncoder`

Đã cập nhật:

- `src/services/evidence/evidence_merger.py`
  - Dùng builder generic thay vì import cứng Jina
- `src/services/document_retrieval/__init__.py`
  - Export adapter/builder mới
- `scripts/05_training_eval/run_production_qdrant_retrieval_eval.py`
  - Manifest ghi thêm thông tin rerank config
- `src/core/config.py`
  - Thêm typed settings cho rerank local
  - Đổi default sang `ViRanker`
- `.env` và `.env.example`
  - Đăng ký đầy đủ block `RAG_RERANK_*`

### 4.3 Benchmark protocol

- Collection: `insurevn_qwen_prod_eval_20260510_full`
- Corpus dir: `data/health_insurance/health_insurance_markdowns_interpreted_cleaned`
- Cases: `89`
- Scenarios rerank benchmark:
  - `hybrid_rerank`
  - `hybrid_company_filter_rerank`
- Baseline so sánh lấy từ artifact đã có:
  - `hybrid`
  - `hybrid_company_filter`

### 4.4 Cấu hình model khi benchmark

- `BAAI/bge-reranker-v2-m3`
  - `batch_size=8`
  - `max_length=1024`
  - GPU `cuda`
- `Alibaba-NLP/gte-multilingual-reranker-base`
  - `batch_size=8`
  - `max_length=1024`
  - `trust_remote_code=true`
  - GPU `cuda`
- `namdp-ptit/ViRanker`
  - `batch_size=8`
  - `max_length=1024`
  - GPU `cuda`
- `Qwen/Qwen3-Reranker-0.6B`
  - Ban đầu FP16 thường bị `CUDA OOM`
  - Cấu hình benchmark cuối:
    - `load_in_4bit=true`
    - `batch_size=1`
    - `device_map=auto`
    - `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`

## 5. Bằng chứng và lệnh đã chạy

### 5.1 Smoke model loading

Đã smoke load và score thực tế cho:

- `Qwen/Qwen3-Reranker-0.6B`
- `BAAI/bge-reranker-v2-m3`
- `Alibaba-NLP/gte-multilingual-reranker-base`
- `namdp-ptit/ViRanker`

Đã thử smoke `Qwen/Qwen3-Reranker-4B` 4-bit nhưng không đưa vào full benchmark trong phiên này.

### 5.2 Benchmark command pattern

Đã chạy theo pattern:

```bash
env RAG_RERANK_PROVIDER=HUGGINGFACE \
    RAG_RERANK_MODEL='<model>' \
    RAG_RERANK_BATCH_SIZE=<n> \
    RAG_RERANK_MAX_LENGTH=1024 \
    python scripts/05_training_eval/run_production_qdrant_retrieval_eval.py \
      --corpus-dir data/health_insurance/health_insurance_markdowns_interpreted_cleaned \
      --benchmark-dir data/health_insurance/health_insurance_markdowns_interpreted_cleaned/benchmark \
      --collection-name insurevn_qwen_prod_eval_20260510_full \
      --top-k 10 \
      --scenarios hybrid_rerank,hybrid_company_filter_rerank
```

### 5.3 Unit test và lint

Đã chạy:

```bash
ruff check src/core/config.py \
  src/services/document_retrieval/rerank_cross_encoder.py \
  src/services/document_retrieval/huggingface_rerank_cross_encoder.py \
  tests/unit/test_config.py \
  tests/unit/test_rerank_cross_encoder.py \
  tests/unit/test_huggingface_rerank_cross_encoder.py

pytest tests/unit/test_config.py \
  tests/unit/test_rerank_cross_encoder.py \
  tests/unit/test_huggingface_rerank_cross_encoder.py \
  tests/unit/test_evidence_merger.py \
  tests/unit/test_jina_rerank_cross_encoder.py -q
```

## 6. Xác minh

### 6.1 Kết quả xác minh code

- `ruff check` pass
- `29 passed`

### 6.2 Kết quả xác minh benchmark

Đã hoàn tất artifact cho:

- `data/eval_runs/20260510_opensource_reranker_benchmark_bge_m3`
- `data/eval_runs/20260510_opensource_reranker_benchmark_gte_multilingual`
- `data/eval_runs/20260510_opensource_reranker_benchmark_viranker`
- `data/eval_runs/20260510_opensource_reranker_benchmark_qwen3_0_6b_4bit`
- Aggregate summary:
  - `data/eval_runs/20260510_opensource_reranker_benchmark_summary.csv`

## 7. Kết quả

### 7.1 Kết quả quan trọng nhất

1. `ViRanker` là model duy nhất giữ được toàn bộ `source_hit_rate_at_5/@10` của baseline `hybrid_company_filter` rồi tăng tiếp `MRR`.
2. Không model nào cải thiện `hybrid` thuần ở metric quan trọng nhất `source_hit_rate_at_5`.
3. Vì vậy, quyết định đúng không phải là “bật rerank mọi nơi”, mà là:
   - **chỉ bật rerank sau hard filters**
   - **model dùng là `ViRanker`**

### 7.2 Metric quyết định

Trên `hybrid_company_filter_rerank`:

- Baseline `hybrid_company_filter`
  - `source_hit_rate_at_5 = 0.9438`
  - `MRR@5 = 0.8519`
  - `quote_hit_rate_at_5 = 0.8701`
- `ViRanker`
  - `source_hit_rate_at_5 = 0.9438`
  - `MRR@5 = 0.8781`
  - `quote_hit_rate_at_5 = 0.8831`

Diễn giải:

- Không làm mất nguồn top-5
- Tăng ranking quality
- Tăng quote precision ở top-5
- Runtime vẫn nằm trong vùng chấp nhận được

### 7.3 Provider behavior của model thắng

`ViRanker` mang lại lợi ích rõ nhất trên:

- `baominh.com.vn`
- `bic.vn`
- `pti.com.vn`

`AIA` vẫn là điểm yếu chưa được giải quyết bởi reranker hiện tại.

## 8. Rủi ro và giới hạn

1. `Qwen/Qwen3-Reranker-4B` chưa được benchmark hoàn chỉnh
   - Nếu có GPU lớn hơn hoặc chấp nhận một overnight run riêng, đây là candidate nên thử tiếp
2. `ViRanker` không cải thiện `hybrid` thuần
   - Nếu caller bật rerank trước khi có hard filters, chất lượng top-5 có thể giảm
3. Benchmark hiện tại vẫn là benchmark retrieval nội bộ
   - Chưa phải end-to-end answer/citation benchmark có LLM generation
4. `AIA` còn yếu
   - Có thể cần benchmark slice riêng hoặc rà benchmark cases của provider này

## 9. Việc tiếp theo

1. Wire `ViRanker` vào production retrieval lane theo rule:
   - chỉ rerank khi supervisor đã trích được `company_code` hoặc hard filters đủ mạnh
2. Chạy thêm benchmark slice riêng cho `AIA`
3. Nếu muốn tối ưu thêm, chạy một round riêng cho `Qwen/Qwen3-Reranker-4B` trên GPU lớn hơn
4. Sau khi chốt retrieval pipeline, chuyển sang answer + citation evaluation
5. Nên tạo ADR nếu project muốn chính thức hóa quyết định:
   - `Qwen/Qwen3-Embedding-8B` cho dense retrieval
   - `ViRanker` cho local rerank sau hard filters
