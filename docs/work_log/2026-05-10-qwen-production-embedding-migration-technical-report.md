# 2026-05-10 - Báo cáo kỹ thuật migration production embedding sang Qwen/Qwen3-Embedding-8B

## 1. Tóm tắt điều hành

Ngày 2026-05-10, production embedding path của InsureVN đã được chuyển sang `Qwen/Qwen3-Embedding-8B` cho phần code chính thức trong `src/` và các script ingestion production liên quan. Migration này giữ nguyên ranh giới với `src/eval`: code production không import, không gọi, và không phụ thuộc vào module trong `src/eval`.

Quyết định triển khai là dùng **official `transformers` usage** theo model card của Qwen, không dùng `langchain_huggingface.HuggingFaceEmbeddings` làm production adapter mặc định. Lý do chính là cần kiểm soát rõ `query instruction`, `left padding`, `last_token_pool`, `normalize`, `MRL dimension truncation`, và local 4-bit loading ngay trong đường chạy production hiện tại mà không phải thêm server phụ như TEI hoặc vLLM.

Kết quả xác minh:

- `ruff check` pass cho toàn bộ file đã sửa.
- `pytest tests/unit/test_qdrant_embedding_providers.py tests/unit/test_qdrant_indexing_script.py tests/unit/test_config.py -q` pass: `21 passed`.
- `scripts/06_db_ingestion/04_index_qdrant_documents.py --help` pass.
- `scripts/06_db_ingestion/09_index_all_markdowns.py --help` pass.
- `pytest tests/integration/test_real_qwen_embedding_provider.py -q` pass: `1 passed`.
- `pytest tests/integration/test_qdrant_retriever_filters.py::test_retrieve_applies_company_hard_filter_and_returns_parent_evidence -q` pass: `1 passed`.
- Smoke production embedding run với model thật pass: provider trả về vector `4096` chiều cho query thực tế.

## 2. Mục tiêu và phạm vi

### Mục tiêu

- Chốt production embedding model của dự án là `Qwen/Qwen3-Embedding-8B`.
- Thay đường chạy production đang mặc định `Google/Gemini embedding` sang Qwen.
- Không sử dụng `src/eval` trong code production.
- Cập nhật `.env` và `.env.example` để phản ánh cấu hình production mới.
- Giữ script ingestion production tương thích với cấu hình embedding mới.

### Phạm vi

Trong phạm vi task này, các thay đổi tập trung ở:

- `src/core/config.py`
- `src/services/document_retrieval/`
- `scripts/06_db_ingestion/04_index_qdrant_documents.py`
- `scripts/06_db_ingestion/09_index_all_markdowns.py`
- test unit/integration liên quan tới provider và config
- `.env`, `.env.example`, `pyproject.toml`, `requirements.txt`

Ngoài phạm vi:

- Không thay benchmark/evaluator trong `src/eval`.
- Không chạy full re-index corpus Qdrant.
- Không thay reranker hoặc retrieval fusion logic.

## 3. Bối cảnh

Trước thay đổi này, production retrieval path của dự án vẫn thiên về Google:

- `RAG_EMBEDDING_PROVIDER` default trong config cũ về Google/Gemini.
- `scripts/06_db_ingestion/04_index_qdrant_documents.py` chỉ build Google provider.
- `scripts/06_db_ingestion/09_index_all_markdowns.py` chỉ chấp nhận `google_genai`.

Trong khi đó, benchmark embedding trước đó đã chốt `Qwen/Qwen3-Embedding-8B` là dense embedding tốt nhất cho corpus tiếng Việt bảo hiểm của dự án theo chất lượng retrieval.

Người dùng cũng đưa ra ràng buộc rõ: code chính thức không được kết nối hay dùng folder `src/eval`, vì đó chỉ là khu vực đánh giá.

## 4. Quyết định kỹ thuật

### 4.1. LangChain có hỗ trợ Qwen/Hugging Face embeddings hay không

Có. Tài liệu LangChain hiện tại cho thấy `langchain_huggingface.HuggingFaceEmbeddings` là adapter chính thức cho Hugging Face embeddings, và adapter này dùng `sentence_transformers`. Tài liệu cũng cho thấy `encode_kwargs` hỗ trợ các tham số như `prompt_name`, `prompt`, `batch_size`, và `normalize_embeddings`.

Nguồn:

- LangChain HuggingFaceEmbeddings docs: https://api.python.langchain.com/en/latest/huggingface/embeddings/langchain_huggingface.embeddings.huggingface.HuggingFaceEmbeddings.html

### 4.2. Vì sao không chọn `langchain_huggingface.HuggingFaceEmbeddings` làm production default

Về mặt API, LangChain có thể dùng được. Tuy nhiên, với model production đã chốt là `Qwen/Qwen3-Embedding-8B`, đường chạy phù hợp nhất cho repo hiện tại là **custom provider dùng `transformers` trực tiếp**.

Lý do:

- Model card của Qwen cung cấp hướng dẫn `Transformers Usage` rất rõ cho retrieval:
  - query cần format theo dạng `Instruct: ...` + `Query:...`
  - document không cần thêm instruction
  - tokenizer nên dùng `padding_side='left'`
  - pooling dùng `last_token_pool`
  - embedding cần được `L2 normalize`
- Model card cũng khuyến nghị tùy biến instruction theo task, scenario, language; và khuyên dùng instruction tiếng Anh cho bối cảnh multilingual.
- Qwen3 embedding hỗ trợ `MRL` với output dimension tùy biến từ `32` đến `4096`, nên production adapter cần xử lý dimension truncation một cách minh bạch.
- Repo hiện tại đang chạy embedding như một phần của Python service/script local, chưa có hạ tầng TEI/vLLM riêng cho production.
- Dùng `transformers` trực tiếp giúp giữ logic này trong chính service layer của InsureVN mà không thêm dependency hành vi từ `sentence_transformers`.

Nguồn:

- Qwen model card: https://huggingface.co/Qwen/Qwen3-Embedding-8B

### 4.3. Phương thức được chọn

Phương thức được chọn là:

- `transformers.AutoTokenizer`
- `transformers.AutoModel`
- local inference
- `BitsAndBytesConfig(load_in_4bit=True)` khi không chạy CPU
- query instruction theo Qwen retrieval format
- `left padding`
- `last_token_pool`
- `L2 normalize`
- vector size production mặc định `4096`

Đây là phương thức “tốt nhất” cho **codebase hiện tại** vì:

- không cần thêm service phụ như TEI/vLLM
- bám sát official Qwen model card
- phù hợp với benchmark local đã chạy trước đó
- dễ nhúng vào `src/services/document_retrieval`

## 5. Triển khai

### 5.1. Production provider mới cho Qwen

Đã bổ sung provider mới tại:

- `src/services/document_retrieval/qwen_embedding_provider.py`

Provider này:

- triển khai interface `Embeddings` của LangChain Core
- dùng `AutoTokenizer.from_pretrained(..., padding_side="left")`
- dùng `AutoModel.from_pretrained(...)`
- format query theo:
  - `Instruct: {task_description}\nQuery:{query}`
- không thêm instruction cho document
- dùng `last_token_pool`
- chuẩn hóa vector bằng `torch.nn.functional.normalize`
- hỗ trợ `MRL` bằng cách cắt số chiều embedding về `vector_size` khi cần
- hỗ trợ `load_in_4bit`, `device_map`, `attn_implementation`

### 5.2. Factory production embedding thống nhất

Đã cập nhật factory tại:

- `src/services/document_retrieval/qdrant_retriever.py`

Factory `build_dense_embedding_provider(...)` bây giờ:

- nhận provider/model/config chung cho production
- route `HUGGINGFACE` / `TRANSFORMERS` / `QWEN` sang `Qwen3EmbeddingProvider`
- chỉ hỗ trợ production local HF path cho `Qwen/Qwen3-Embedding-8B`
- vẫn giữ `GoogleGenAIEmbeddingProvider` như compatibility path, nhưng không còn là default production

Điểm quan trọng: code chính thức không import gì từ `src/eval`.

### 5.3. Đổi default config production sang Qwen

Đã cập nhật `src/core/config.py`:

- `RAG_EMBEDDING_PROVIDER` default: `HUGGINGFACE`
- `RAG_EMBEDDING_MODEL` default: giá trị của `QWEN_EMBEDDING_MODEL`
- `RAG_DENSE_VECTOR_SIZE` default: `4096`
- `RAG_EMBEDDING_BATCH_SIZE` default: `4`
- thêm:
  - `RAG_EMBEDDING_MAX_LENGTH`
  - `RAG_EMBEDDING_LOAD_IN_4BIT`
  - `RAG_EMBEDDING_DEVICE_MAP`
  - `RAG_EMBEDDING_ATTN_IMPLEMENTATION`
  - `RAG_EMBEDDING_QUERY_TASK_DESCRIPTION`
- `RAG_EMBEDDING_API_KEY` không còn fallback mù sang Google key cho provider local

Ngoài ra, đã thêm `QWEN_EMBEDDING_MODEL` và giữ `GOOGLE_EMBEDDING_MODEL` như config riêng để các integration test Google không bị phụ thuộc vào default production mới.

### 5.4. Cập nhật script ingestion production

Đã sửa hai script production để không còn tự build Google-only provider:

- `scripts/06_db_ingestion/04_index_qdrant_documents.py`
- `scripts/06_db_ingestion/09_index_all_markdowns.py`

Hai script này giờ dùng lại factory production trung tâm `build_dense_embedding_provider(...)`.

Ý nghĩa:

- production ingestion path bây giờ đi qua cùng một embedding factory với service layer
- tránh duplicate logic giữa script và `src/`
- tránh việc script production “nói là generic” nhưng thực tế chỉ dùng được Google

### 5.5. Cập nhật environment và dependencies

Đã cập nhật `.env.example` và `.env`:

- thêm `QWEN_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B`
- đổi `RAG_EMBEDDING_PROVIDER=HUGGINGFACE`
- đổi `RAG_EMBEDDING_MODEL=QWEN_EMBEDDING_MODEL`
- đặt:
  - `RAG_DENSE_VECTOR_SIZE=4096`
  - `RAG_EMBEDDING_BATCH_SIZE=4`
  - `RAG_EMBEDDING_MAX_LENGTH=8192`
  - `RAG_EMBEDDING_LOAD_IN_4BIT=true`
  - `RAG_EMBEDDING_DEVICE_MAP=auto`
  - `RAG_EMBEDDING_ATTN_IMPLEMENTATION=`
  - `RAG_EMBEDDING_QUERY_TASK_DESCRIPTION=Given a web search query, retrieve relevant passages that answer the query`

Đã thêm dependency:

- `accelerate>=0.31.0`
- `bitsandbytes>=0.43.1`

## 6. Bằng chứng và lệnh đã chạy

### 6.1. Kiểm tra runtime dependencies

Đã chạy:

```bash
python - <<'PY'
import importlib
for name in ['transformers','accelerate','bitsandbytes','torch']:
    ...
PY
```

Kết quả:

- `transformers OK 4.57.3`
- `accelerate OK 1.13.0`
- `bitsandbytes OK 0.49.2`
- `torch OK 2.6.0+cu124`

### 6.2. Lint

Đã chạy:

```bash
ruff check src/core/config.py \
  src/services/document_retrieval/qwen_embedding_provider.py \
  src/services/document_retrieval/qdrant_retriever.py \
  src/services/document_retrieval/__init__.py \
  scripts/06_db_ingestion/04_index_qdrant_documents.py \
  scripts/06_db_ingestion/09_index_all_markdowns.py \
  tests/unit/test_qdrant_embedding_providers.py \
  tests/unit/test_qdrant_indexing_script.py \
  tests/unit/test_config.py \
  tests/integration/test_real_google_embedding_provider.py \
  tests/integration/test_qdrant_retriever_filters.py
```

Kết quả:

- `All checks passed!`

### 6.3. Unit tests

Đã chạy:

```bash
pytest tests/unit/test_qdrant_embedding_providers.py \
  tests/unit/test_qdrant_indexing_script.py \
  tests/unit/test_config.py -q
```

Kết quả:

- `20 passed`

Ghi chú:

- Có warning từ `torchao` liên quan import path deprecation và cpp extension compatibility với `torch 2.6.0+cu124`.
- Đây không phải lỗi do code migration Qwen tạo ra.

### 6.4. CLI smoke cho ingestion scripts

Đã chạy:

```bash
python scripts/06_db_ingestion/04_index_qdrant_documents.py --help
python scripts/06_db_ingestion/09_index_all_markdowns.py --help
```

Kết quả:

- cả hai command đều exit code `0`
- CLI load/import thành công sau khi đổi sang factory embedding production mới

### 6.5. Smoke production embedding với model thật

Đã chạy:

```bash
python - <<'PY'
from src.core.config import settings
from src.services.document_retrieval.qdrant_retriever import build_dense_embedding_provider
...
PY
```

Run 1:

- provider: `Qwen3EmbeddingProvider`
- model: `Qwen/Qwen3-Embedding-8B`
- `vector_size=4096`
- `query_len=4096`
- `document_len=4096`
- `dot=0.756915`

Run 2 sau khi đổi `torch_dtype` sang `dtype`:

- provider: `Qwen3EmbeddingProvider`
- `query_len=4096`
- query vector head sinh ra bình thường

Kết luận:

- production path load model thật thành công
- embedding output đúng kích thước `4096`
- factory production mới hoạt động đúng với `.env` mới

## 7. Xác minh

### 7.1. Các file thay đổi chính

`git diff --name-status` trên phạm vi task cho thấy các file production/config/test liên quan đã được cập nhật:

- `.env.example`
- `pyproject.toml`
- `requirements.txt`
- `scripts/06_db_ingestion/04_index_qdrant_documents.py`
- `scripts/06_db_ingestion/09_index_all_markdowns.py`
- `src/core/config.py`
- `src/services/document_retrieval/__init__.py`
- `src/services/document_retrieval/qdrant_retriever.py`
- `tests/integration/test_qdrant_retriever_filters.py`
- `tests/integration/test_real_google_embedding_provider.py`
- `tests/unit/test_config.py`
- `tests/unit/test_qdrant_embedding_providers.py`
- `tests/unit/test_qdrant_indexing_script.py`

### 7.2. Không dùng `src/eval` trong production path

Trong phần triển khai của task này:

- provider production mới nằm ở `src/services/document_retrieval/qwen_embedding_provider.py`
- factory production nằm ở `src/services/document_retrieval/qdrant_retriever.py`
- script ingestion production chỉ gọi lại factory trong `src/services/document_retrieval`

Không có import production nào được thêm từ `src/eval`.

## 8. Kết quả

Kết quả cuối cùng của task:

1. Production default embedding model của dự án đã chuyển sang `Qwen/Qwen3-Embedding-8B`.
2. `.env` và `.env.example` đã phản ánh cấu hình production mới.
3. Production code trong `src/` không cần `src/eval`.
4. Ingestion scripts production không còn hardcode Google-only embedding path.
5. LangChain vẫn có chỗ đứng ở tầng interface `Embeddings`, nhưng adapter production cho Qwen dùng `transformers` trực tiếp theo official Qwen model card.
6. Runtime smoke với model thật đã thành công.

## 9. Rủi ro và giới hạn

### 9.1. Chi phí tài nguyên

`Qwen/Qwen3-Embedding-8B` là model nặng. Dù đã dùng 4-bit, thời gian load model vẫn đáng kể và cần GPU phù hợp để vận hành trơn tru.

### 9.2. Flash Attention 2 chưa bật mặc định

Model card khuyến nghị `flash_attention_2` cho hiệu năng/memory tốt hơn. Trong migration này, biến `RAG_EMBEDDING_ATTN_IMPLEMENTATION` đã được thêm nhưng để trống mặc định để tránh ép runtime phụ thuộc `flash-attn` khi môi trường chưa xác nhận sẵn sàng.

### 9.3. Chưa chạy full re-index toàn bộ corpus sau migration

Task này mới xác minh ở mức:

- import/config path
- unit tests
- CLI smoke
- real embedding smoke

Chưa chạy full Qdrant re-index toàn bộ corpus production trong phiên này.

### 9.4. Google compatibility path vẫn còn

Đã xóa Google embedding provider khỏi production service path trong `src/services/document_retrieval`. Phần Google/Gemini còn lại trong repo hiện chỉ thuộc các khu vực khác như eval hoặc LLM chunking, không còn là dense embedding path chính thức của production retrieval.

## 10. Việc tiếp theo

1. Chạy full re-index Qdrant corpus production bằng Qwen để materialize vector mới.
2. Chạy retrieval smoke/end-to-end trên các query bảo hiểm tiếng Việt quan trọng sau khi re-index.
3. Đánh giá có nên bật `RAG_EMBEDDING_ATTN_IMPLEMENTATION=flash_attention_2` trên máy production sau khi xác nhận dependency/runtime.
4. Nếu muốn tiếp tục giảm footprint vận hành, cân nhắc task riêng để dọn các cấu hình Google embedding không còn dùng trong `.env` cục bộ và tài liệu liên quan ngoài production path.

## 11. Cập nhật sau code review

Sau vòng review nội bộ, đã sửa thêm hai điểm:

1. `RAG_EMBEDDING_API_KEY` giờ dùng `_resolve_indirect(...)` trực tiếp, nên alias env như `RAG_EMBEDDING_API_KEY=SOME_ENV_NAME` sẽ được resolve đúng thay vì giữ nguyên tên biến.
2. Google embedding compatibility path đã bị loại khỏi `src/services/document_retrieval` và export công khai của module này, để production retrieval thực sự chốt về Qwen.

Các xác minh bổ sung sau fix review:

- `ruff check` pass
- `pytest tests/unit/test_qdrant_embedding_providers.py tests/unit/test_qdrant_indexing_script.py tests/unit/test_config.py -q` → `21 passed`
- `pytest tests/integration/test_real_qwen_embedding_provider.py -q` → `1 passed`
- `pytest tests/integration/test_qdrant_retriever_filters.py::test_retrieve_applies_company_hard_filter_and_returns_parent_evidence -q` → `1 passed`
