# Huấn Luyện VLM Và Đánh Giá RAG/Retrieval

## Mục tiêu

Nhóm script này tạo dataset cho VLM table extraction, fine-tune/evaluate/export
model, sinh benchmark RAG có ground truth, chạy chunking/indexing evaluation và
dùng LLM judge để đánh giá retrieval.

Pipeline tương ứng phase 5 trong
[`../work_log/2026-05-09-data-pipeline-processing-technical-report.md`](../work_log/2026-05-09-data-pipeline-processing-technical-report.md).

## Năng lực chính

### Chuẩn bị và huấn luyện VLM

- [`../../scripts/05_training_eval/01_prepare_oumi_vlm_dataset.py`](../../scripts/05_training_eval/01_prepare_oumi_vlm_dataset.py)
  chuyển cặp image/JSON extraction thành JSONL conversation format cho Oumi,
  chia train/test.
- [`../../scripts/05_training_eval/02_train_gemma4.py`](../../scripts/05_training_eval/02_train_gemma4.py)
  fine-tune Gemma 4 Vision bằng Unsloth LoRA.
- [`../../scripts/05_training_eval/03_eval_gemma4.py`](../../scripts/05_training_eval/03_eval_gemma4.py)
  đánh giá model/adaptor trên test set.
- [`../../scripts/05_training_eval/04_export_gemma4.py`](../../scripts/05_training_eval/04_export_gemma4.py)
  export hoặc merge adaptor/model sau training.
- [`../../scripts/05_training_eval/05_start_training.sh`](../../scripts/05_training_eval/05_start_training.sh)
  wrapper shell để khởi chạy training.
- [`../../scripts/05_training_eval/run_vlm_inference.py`](../../scripts/05_training_eval/run_vlm_inference.py)
  chạy inference VLM với base model và adapter.
- [`../../scripts/05_training_eval/train_gemma4_colab.ipynb`](../../scripts/05_training_eval/train_gemma4_colab.ipynb),
  [`../../scripts/06_ipynb/train_gemma4_colab.ipynb`](../../scripts/06_ipynb/train_gemma4_colab.ipynb),
  [`../../scripts/06_ipynb/Gemma4_(E2B)_Vision.ipynb`](../../scripts/06_ipynb/Gemma4_%28E2B%29_Vision.ipynb)
  là notebook Colab/Unsloth cho thí nghiệm Gemma 4 Vision.

Tài liệu kế hoạch VLM đã có:
[`../superpowers/plans/2026-04-30-vlm-table-extraction-plan.md`](../superpowers/plans/2026-04-30-vlm-table-extraction-plan.md).

### Sinh benchmark RAG

- [`../../scripts/05_training_eval/05_generate_health_rag_benchmark.py`](../../scripts/05_training_eval/05_generate_health_rag_benchmark.py)
  sinh benchmark từ Markdown đã làm sạch, có fallback deterministic và mode LLM.
- [`../../scripts/05_training_eval/06_generate_health_rag_context_benchmark_v2.py`](../../scripts/05_training_eval/06_generate_health_rag_context_benchmark_v2.py)
  wrapper cho benchmark v2 trong `src.eval.context_benchmark_v2`.

Tài liệu benchmark v2 đã có:
[`../architecture/2026-05-09-benchmark-v2-generation-logic-technical-report.md`](../architecture/2026-05-09-benchmark-v2-generation-logic-technical-report.md),
[`../superpowers/specs/2026-05-08-health-rag-context-benchmark-v2-design.md`](../superpowers/specs/2026-05-08-health-rag-context-benchmark-v2-design.md),
[`../superpowers/plans/2026-05-08-health-rag-context-benchmark-v2.md`](../superpowers/plans/2026-05-08-health-rag-context-benchmark-v2.md).

### Chunking, indexing và retrieval evaluation

- [`../../scripts/05_training_eval/run_streaming_chunking_embedding_qdrant.py`](../../scripts/05_training_eval/run_streaming_chunking_embedding_qdrant.py)
  chạy streaming chunking, embedding và upsert Qdrant cho nhiều strategy.
- [`../../scripts/05_training_eval/run_persisted_qdrant_retrieval_eval.py`](../../scripts/05_training_eval/run_persisted_qdrant_retrieval_eval.py)
  đánh giá retrieval trên các Qdrant index đã persist.
- [`../../scripts/05_training_eval/run_llm_retrieval_judge_eval.py`](../../scripts/05_training_eval/run_llm_retrieval_judge_eval.py)
  dùng LLM judge để chấm retrieval output.
- [`../../scripts/05_training_eval/run_safe_chunking_eval.py`](../../scripts/05_training_eval/run_safe_chunking_eval.py)
  wrapper an toàn tài nguyên cho benchmark chunking 10 tài liệu.
- [`../../scripts/08_chunking_compare/benchmark_health_chunking.py`](../../scripts/08_chunking_compare/benchmark_health_chunking.py)
  benchmark nhiều strategy chunking trên corpus health Markdown.
- [`../../scripts/08_chunking_compare/chunking_compare_api.py`](../../scripts/08_chunking_compare/chunking_compare_api.py)
  FastAPI API cho playground so sánh semantic/LLM/late/adaptive-density
  chunking.
- [`../../scripts/08_chunking_compare/00_chunking_compare.html`](../../scripts/08_chunking_compare/00_chunking_compare.html)
  playground browser để so sánh chunking trực quan.
- [`../../scripts/08_chunking_compare/llm_boundary_chunking_demo.py`](../../scripts/08_chunking_compare/llm_boundary_chunking_demo.py)
  demo LLM-guided boundary chunking trên một tài liệu.
- [`../../scripts/08_chunking_compare/test_chunking_compare_api.py`](../../scripts/08_chunking_compare/test_chunking_compare_api.py)
  pytest cho API chunking compare.

Các report chunking/retrieval đã có:
[`../work_log/2026-05-07-health-chunking-benchmark-end-to-end-process-technical-report.md`](../work_log/2026-05-07-health-chunking-benchmark-end-to-end-process-technical-report.md),
[`../work_log/2026-05-08-streaming-chunking-embedding-qdrant-technical-report.md`](../work_log/2026-05-08-streaming-chunking-embedding-qdrant-technical-report.md),
[`../work_log/2026-05-08-all-techniques-full-retrieval-eval-technical-report.md`](../work_log/2026-05-08-all-techniques-full-retrieval-eval-technical-report.md),
[`../work_log/2026-05-08-all-techniques-full-llm-judge-technical-report.md`](../work_log/2026-05-08-all-techniques-full-llm-judge-technical-report.md),
[`../work_log/2026-05-09-context-benchmark-v2-all-chunking-eval-technical-report.md`](../work_log/2026-05-09-context-benchmark-v2-all-chunking-eval-technical-report.md).

### Chunking strategy reference

Thư mục [`../../scripts/09_databricks_chunking_strategies`](../../scripts/09_databricks_chunking_strategies)
chứa các ví dụ/reference strategy như fixed-size, semantic, recursive-code,
adaptive, context-enriched, AI-driven dynamic và evaluation framework. Các file
chính gồm `fixed_size_chunking.py`, `semantic_chunking.py`,
`recursive_code_chunking.py`, `adaptive_chunking.py`,
`context_enriched_chunking.py`, `ai_driven_dynamic_chunking.py`,
`evaluation_framework.py`, `best_practices_guidelines.py`, `common.py`,
`README.md`, `requirements.txt` và `chunking_evaluation_results.csv`.
Đây là tài liệu tham khảo/experiment, không phải pipeline production chính.

## Luồng chạy đề xuất

1. Chuẩn bị dataset VLM:

```bash
python scripts/05_training_eval/01_prepare_oumi_vlm_dataset.py \
  --input data/health_insurance/good_content \
  --output data/health_insurance/vlm_dataset
```

2. Fine-tune và evaluate:

```bash
bash scripts/05_training_eval/05_start_training.sh
python scripts/05_training_eval/03_eval_gemma4.py
python scripts/05_training_eval/04_export_gemma4.py
```

3. Sinh benchmark RAG v2:

```bash
python scripts/05_training_eval/06_generate_health_rag_context_benchmark_v2.py \
  --verify-only
```

4. Chạy indexing/retrieval eval:

```bash
python scripts/05_training_eval/run_streaming_chunking_embedding_qdrant.py
python scripts/05_training_eval/run_persisted_qdrant_retrieval_eval.py
python scripts/05_training_eval/run_llm_retrieval_judge_eval.py
```

## Output quan trọng

- `oumi_vlm_train.jsonl` và `oumi_vlm_test.jsonl`.
- LoRA adapter hoặc merged model sau training.
- Benchmark JSONL/CSV/manifest/README.
- Persisted Qdrant run directories.
- Retrieval metrics, LLM judge metrics và work-log reports.

## Lưu ý vận hành

- VLM training phụ thuộc GPU và version của Unsloth/transformers; notebook Colab
  hữu ích cho môi trường T4 nhưng cần đồng bộ path Google Drive với dataset
  local.
- Với retrieval evaluation, giữ nguyên manifest/run-dir để so sánh strategy
  được tái lập.
- Benchmark sinh bằng LLM phải giữ citation/source span để tránh biến thành bộ
  câu hỏi không kiểm chứng được.
