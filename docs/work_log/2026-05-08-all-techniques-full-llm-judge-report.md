# Bao cao LLM Judge cho toan bo ky thuat chunking

**Ngay chay:** 2026-05-08  
**Phase:** Phase 5 - Training & Eval  
**Run dir:** `data/eval_runs/20260508_200007_all_techniques_full_llm_judge`  
**Input retrieval eval:** `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval`

## Muc tieu

Chay AI judge cho ket qua retrieval top-k=5 cua toan bo 9 ky thuat chunking tren full benchmark 150 cau hoi. Buoc nay chi cham ket qua retrieval da co san, khong chunk lai, khong embedding lai, khong rebuild Qdrant.

## Cach cham

- Moi dong cham tuong ung voi mot cap `(strategy, benchmark_case)`.
- Judge prompt nhan:
  - cau hoi benchmark,
  - cau tra loi vang,
  - source file ky vong,
  - top-k context lay tu retrieval output.
- AI judge tra ve JSON nghiem ngat voi 3 diem:
  - `context_precision`: context tra ve co tap trung vao noi dung can tim khong.
  - `answer_support`: context co du thong tin de tra loi cau hoi vang khong.
  - `context_relevancy`: context co lien quan truc tiep den cau hoi khong.
- `overall_score` la trung binh cua 3 diem tren.
- `success` khi `overall_score >= 0.6`.

## Provider

Khong dung OpenAI. Run nay dung provider pool tu `.env`:

- Slots khai bao: 21
- Slots healthy trong lan retry cuoi: 12
- Slots duoc chon: Gemini 4, NVIDIA 4, Ollama 4
- OpenRouter khong duoc chon trong lan nay vi health check bi loi/rate-limit.

Sau pass dau tien co 29 loi tam thoi do timeout/rate-limit/JSON khong hop le. Da retry tren cung output dir, script chi bo qua cac dong da completed va cham lai phan fail. Ket qua cuoi cung: **1350/1350 completed, 0 failed**.

## Ket qua tong hop

| Rank | Strategy | Cases | Failed | Overall | Support | Precision | Relevancy | Success rate |
| ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `markdown_header_recursive_table` | 150 | 0 | 0.2133 | 0.2527 | 0.1573 | 0.2300 | 0.1800 |
| 2 | `table_as_one_hybrid` | 150 | 0 | 0.2036 | 0.2420 | 0.1480 | 0.2207 | 0.1533 |
| 3 | `hierarchical_header_recursive` | 150 | 0 | 0.1758 | 0.2047 | 0.1267 | 0.1960 | 0.1267 |
| 4 | `insurance_contract_hybrid_late` | 150 | 0 | 0.1673 | 0.2100 | 0.1213 | 0.1707 | 0.1600 |
| 5 | `llm_markdown_optimal` | 150 | 0 | 0.1640 | 0.1920 | 0.1187 | 0.1813 | 0.1467 |
| 6 | `llamaindex_markdown_element` | 150 | 0 | 0.1522 | 0.1953 | 0.1027 | 0.1587 | 0.1267 |
| 7 | `markdown_then_semantic` | 150 | 0 | 0.1356 | 0.1573 | 0.1027 | 0.1467 | 0.1000 |
| 8 | `heading_level_table_safe` | 150 | 0 | 0.1338 | 0.1640 | 0.0920 | 0.1453 | 0.1067 |
| 9 | `semantic_embedding` | 150 | 0 | 0.1196 | 0.1867 | 0.0667 | 0.1053 | 0.0600 |

## Nhan dinh

`markdown_header_recursive_table` tiep tuc dung dau khi doi sang AI judge, khop voi ket qua deterministic retrieval truoc do. `table_as_one_hybrid` dung thu hai va rat gan top 1, cho thay cac ky thuat giu cau truc header/table dang tot hon cac ky thuat semantic-only trong bo benchmark nay.

Diem trung binh tuy thap vi AI judge yeu cau context top-k phai du dung de support cau tra loi vang, khong chi match source file. Vi vay metric nay nghiem khac hon hit@5/MRR deterministic.

## Artifact

- `llm_judge_scores.jsonl`: tat ca diem chi tiet theo case.
- `llm_judge_scores.csv`: bang diem phang de loc/sort.
- `llm_judge_strategy_summary.csv`: tong hop theo strategy.
- `llm_judge_report.md`: report sinh tu runner.
- `manifest.json`: cau hinh run va provider health.

## Ket luan

Neu chon theo AI judge, ky thuat tot nhat hien tai la **`markdown_header_recursive_table`**. Neu can shortlist de toi uu tiep, nen so sanh sau hon top 2: `markdown_header_recursive_table` va `table_as_one_hybrid`.
