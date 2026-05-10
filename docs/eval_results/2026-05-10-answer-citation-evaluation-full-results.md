# 2026-05-10 - Answer + Citation Evaluation Full Results

## Tóm tắt

- Retrieval scenario: `hybrid_company_filter_rerank`
- Generation mode: `extractive`
- Cases: `89`
- Success threshold: `0.65`
- Overall success rate: `0.7640`
- Mean answer quality score: `0.7741`
- Expected source in context rate: `0.9326`
- Expected source cited rate: `0.8427`
- Valid citation rate mean: `1.0000`
- Citation coverage mean: `1.0000`
- Gold token recall mean: `0.6247`
- Context token precision mean: `0.9888`
- Numeric claim support rate: `1.0000`

Ghi chú sau review: `success=True` hiện yêu cầu score đạt threshold, citation hợp lệ 100%, coverage hợp lệ 100%, và nếu case yêu cầu source thì answer phải cite đúng expected source.

Artifact đầy đủ nằm tại:

- `data/eval_runs/20260510_answer_citation_eval/answer_eval_rows.csv`
- `data/eval_runs/20260510_answer_citation_eval/answer_eval_rows.jsonl`
- `data/eval_runs/20260510_answer_citation_eval/answers.md`
- `data/eval_runs/20260510_answer_citation_eval/answer_eval_summary.csv`
- `data/eval_runs/20260510_answer_citation_eval/manifest.json`

## Summary

| Group | Cases | Success | Quality | Source in context | Source cited | Valid citation | Citation coverage | Gold recall | Context precision | Numeric support |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall:all | 89 | 0.7640 | 0.7741 | 0.9326 | 0.8427 | 1.0000 | 1.0000 | 0.6247 | 0.9888 | 1.0000 |
| provider:aia.com.vn | 6 | 0.3333 | 0.6192 | 0.3333 | 0.3333 | 1.0000 | 1.0000 | 0.4792 | 1.0000 | 1.0000 |
| provider:baominh.com.vn | 5 | 0.6000 | 0.7220 | 1.0000 | 0.6000 | 1.0000 | 1.0000 | 0.5549 | 1.0000 | 1.0000 |
| provider:bic.vn | 6 | 0.1667 | 0.6044 | 0.8333 | 0.3333 | 1.0000 | 1.0000 | 0.4692 | 0.8333 | 1.0000 |
| provider:libertyinsurance.com.vn | 5 | 0.6000 | 0.7549 | 0.8000 | 0.6000 | 1.0000 | 1.0000 | 0.6374 | 1.0000 | 1.0000 |
| provider:pacific_cross_all_pdfs | 1 | 1.0000 | 0.7735 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.2941 | 1.0000 | 1.0000 |
| provider:pti.com.vn | 66 | 0.8788 | 0.8091 | 1.0000 | 0.9697 | 1.0000 | 1.0000 | 0.6613 | 1.0000 | 1.0000 |
| risk:high | 33 | 0.8485 | 0.8129 | 0.9697 | 0.8788 | 1.0000 | 1.0000 | 0.7336 | 1.0000 | 1.0000 |
| risk:low | 11 | 0.8182 | 0.7515 | 0.9091 | 0.9091 | 1.0000 | 1.0000 | 0.4516 | 1.0000 | 1.0000 |
| risk:medium | 45 | 0.6889 | 0.7512 | 0.9111 | 0.8000 | 1.0000 | 1.0000 | 0.5871 | 0.9778 | 1.0000 |

## Full Case Results

| Case | Provider | Risk | Score | OK | SrcCtx | SrcCited | ValidCite | CiteCov | Numeric | GoldRecall | CtxPrec | Query |
| --- | --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| hi_bench_001 | pti.com.vn | low | 1.0000 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Theo quy tắc bảo hiểm sức khỏe PTI, "bệnh có sẵn" được hiểu như thế nào? |
| hi_bench_002 | pti.com.vn | low | 0.9886 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.9545 | 1.0000 | Trong tài liệu PTI, điều trị nội trú khác điều trị ngoại trú ở điểm nào? |
| hi_bench_003 | pti.com.vn | medium | 0.7500 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.6000 | 1.0000 | PTI chi trả quyền lợi bảo hiểm sức khỏe dựa trên các giới hạn nào? |
| hi_bench_004 | pti.com.vn | medium | 0.9375 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.7500 | 1.0000 | Một cơ sở spa, massage hoặc nơi an dưỡng có được xem là cơ sở y tế/bệnh viện hợp lệ theo... |
| hi_bench_005 | pti.com.vn | high | 1.0000 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Theo PTI, giấy tờ nào là chứng từ cần thiết để yêu cầu bồi thường cho điều trị nội trú ho... |
| hi_bench_006 | pti.com.vn | low | 0.6984 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.1935 | 1.0000 | Theo PTI, thời hạn bảo hiểm thường kéo dài bao lâu? |
| hi_bench_007 | pti.com.vn | medium | 0.6192 | False | True | True | 1.0000 | 1.0000 | 1.0000 | 0.0769 | 1.0000 | So sánh khái niệm "cùng chi trả/mức miễn thường" và "giới hạn chi tiết" trong quy tắc PTI. |
| hi_bench_008 | pti.com.vn | medium | 0.6064 | False | True | True | 1.0000 | 1.0000 | 1.0000 | 0.0256 | 1.0000 | PTI định nghĩa "bệnh đặc biệt" gồm những nhóm bệnh nào? |
| hi_bench_009 | pacific_cross_all_pdfs | low | 0.7735 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.2941 | 1.0000 | Người dùng hỏi danh sách bệnh viện bảo lãnh viện phí của Pacific Cross năm 2026. Nên truy... |
| hi_bench_010 | aia.com.vn | low | 0.4077 | False | False | False | 1.0000 | 1.0000 | 1.0000 | 0.2308 | 1.0000 | Khách hàng hỏi biểu phí sản phẩm BHSK Bùng Gia Lực của AIA. Cần ưu tiên tài liệu nào tron... |
| hi_bench_011 | pti.com.vn | high | 0.6922 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.2188 | 1.0000 | Nếu người dùng chỉ mô tả triệu chứng và hỏi có chắc chắn được bồi thường không, trợ lý nê... |
| hi_bench_012 | pti.com.vn | high | 0.9667 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.8667 | 1.0000 | Quy tắc PTI có bảo hiểm mọi chi phí liên quan đến người hiến nội tạng không? |
| hi_bench_v2_001 | pti.com.vn | low | 0.6076 | False | True | True | 1.0000 | 1.0000 | 1.0000 | 0.0303 | 1.0000 | Bệnh đặc biệt theo PTI gồm những bệnh nào? |
| hi_bench_v2_002 | pti.com.vn | low | 0.6769 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.3077 | 1.0000 | PTI định nghĩa bệnh có sẵn như thế nào? |
| hi_bench_v2_003 | pti.com.vn | high | 0.9250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Chi phí phát sinh cho người hiến nội tạng có được bảo hiểm theo quy tắc PTI không? |
| hi_bench_v2_004 | pti.com.vn | medium | 0.7926 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.4706 | 1.0000 | Chi phí dưỡng nhi có bao gồm xét nghiệm tầm soát và thức ăn em bé không? |
| hi_bench_v2_005 | pti.com.vn | medium | 0.8972 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.8889 | 1.0000 | Chi phí y tế thực tế theo PTI cần đáp ứng điều kiện gì? |
| hi_bench_v2_006 | pti.com.vn | medium | 0.8694 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.7778 | 1.0000 | Cơ sở spa hoặc massage có được xem là cơ sở y tế hợp lệ theo PTI không? |
| hi_bench_v2_007 | pti.com.vn | medium | 0.7125 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.4500 | 1.0000 | Bệnh viện theo PTI có bao gồm nơi an dưỡng phục hồi sức khỏe không? |
| hi_bench_v2_008 | pti.com.vn | low | 0.6667 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.2667 | 1.0000 | Cùng chi trả/mức miễn thường là gì? |
| hi_bench_v2_009 | pti.com.vn | low | 0.7821 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.4286 | 1.0000 | Điều trị ngoại trú theo PTI là gì? |
| hi_bench_v2_010 | pti.com.vn | high | 0.9250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Điều trị nội trú cần chứng từ gì để yêu cầu bồi thường? |
| hi_bench_v2_011 | pti.com.vn | medium | 0.8893 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.8571 | 1.0000 | Điều trị trong ngày có cần ở lại bệnh viện qua đêm không? |
| hi_bench_v2_012 | pti.com.vn | medium | 0.6000 | False | True | True | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 1.0000 | Giới hạn chi tiết phụ có được vượt số tiền bảo hiểm tối đa không? |
| hi_bench_v2_013 | pti.com.vn | low | 0.9250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Chi phí tái khám ngay sau lần khám trước có được coi là một lần khám mới không? |
| hi_bench_v2_014 | pti.com.vn | low | 0.7402 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.2609 | 1.0000 | Thời hạn bảo hiểm thường là bao lâu? |
| hi_bench_v2_015 | pti.com.vn | medium | 0.6667 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.2667 | 1.0000 | Thời gian chờ trong bảo hiểm PTI là gì? |
| hi_bench_v2_016 | pti.com.vn | medium | 0.6417 | False | True | True | 1.0000 | 1.0000 | 1.0000 | 0.1667 | 1.0000 | Con phụ thuộc theo PTI có thể đến bao nhiêu tuổi nếu đang học toàn thời gian? |
| hi_bench_v2_017 | pti.com.vn | medium | 0.7375 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.2500 | 1.0000 | Nằm viện theo PTI được hiểu như thế nào? |
| hi_bench_v2_018 | pti.com.vn | medium | 0.9250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Phạm vi bảo hiểm chính của hợp đồng sức khỏe PTI là gì? |
| hi_bench_v2_019 | pti.com.vn | medium | 0.6700 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.2800 | 1.0000 | Chi phí xét nghiệm MRI/CT/PET khi nằm viện có cần chỉ định của bác sĩ không? |
| hi_bench_v2_020 | pti.com.vn | medium | 0.8809 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.8235 | 1.0000 | PTI có chi trả chi phí phẫu thuật ngoại trú không? |
| hi_bench_v2_021 | pti.com.vn | medium | 0.9250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Trợ cấp nằm viện được trả cho trường hợp nào? |
| hi_bench_v2_022 | pti.com.vn | medium | 0.9250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Chi phí y tế trước khi nhập viện được chi trả tối đa bao nhiêu ngày trước nhập viện? |
| hi_bench_v2_023 | pti.com.vn | medium | 0.9250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Chi phí điều trị sau khi xuất viện được chi trả tối đa bao nhiêu ngày? |
| hi_bench_v2_024 | pti.com.vn | high | 0.9250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Trợ cấp mai táng áp dụng khi nào? |
| hi_bench_v2_025 | pti.com.vn | high | 0.9250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Sinh mổ theo yêu cầu có được bảo hiểm trong mục biến chứng thai sản/sinh khó không? |
| hi_bench_v2_026 | pti.com.vn | high | 0.8500 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Điều trị ngoại trú có bị loại trừ nếu người được bảo hiểm không tham gia quyền lợi điều t... |
| hi_bench_v2_027 | pti.com.vn | high | 0.6750 | False | True | False | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Điều trị thẩm mỹ/cân nặng có thuộc điểm loại trừ PTI không? |
| hi_bench_v2_028 | pti.com.vn | high | 0.6455 | False | True | True | 1.0000 | 1.0000 | 1.0000 | 0.1818 | 1.0000 | Khám và xét nghiệm không có kết luận bệnh của bác sĩ có bị loại trừ không? |
| hi_bench_v2_029 | pti.com.vn | high | 0.3794 | False | True | False | 1.0000 | 1.0000 | 1.0000 | 0.1176 | 1.0000 | Điều trị ngoại trú về răng có luôn bị loại trừ không? |
| hi_bench_v2_030 | pti.com.vn | high | 0.6735 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.2941 | 1.0000 | Điều trị/phẫu thuật theo yêu cầu không liên quan điều kiện điều trị bình thường có bị loạ... |
| hi_bench_v2_031 | pti.com.vn | high | 0.9058 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.9231 | 1.0000 | Điều trị vô sinh hoặc thụ tinh nhân tạo có thuộc điểm loại trừ không? |
| hi_bench_v2_032 | pti.com.vn | high | 0.9111 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.9444 | 1.0000 | Bệnh đặc biệt trong năm bảo hiểm đầu tiên có bị loại trừ không? |
| hi_bench_v2_033 | pti.com.vn | high | 0.9103 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.9412 | 1.0000 | Bệnh có sẵn trong năm bảo hiểm đầu tiên có bị loại trừ không? |
| hi_bench_v2_034 | pti.com.vn | high | 0.6789 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.3158 | 1.0000 | AIDS, bệnh hoa liễu hoặc bệnh lây nhiễm qua đường tình dục có thuộc điểm loại trừ không? |
| hi_bench_v2_035 | pti.com.vn | high | 0.7250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.5000 | 1.0000 | Với hợp đồng dưới 50 nhân viên, thời gian chờ sinh đẻ là bao lâu? |
| hi_bench_v2_036 | pti.com.vn | high | 0.8809 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.8235 | 1.0000 | Với hợp đồng dưới 50 nhân viên, thời gian chờ sẩy thai/nạo thai theo chỉ định là bao lâu? |
| hi_bench_v2_037 | pti.com.vn | medium | 0.8500 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Với hợp đồng từ 50 nhân viên trở lên, điều trị bệnh tật có áp dụng thời gian chờ không? |
| hi_bench_v2_038 | pti.com.vn | high | 0.8500 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Với hợp đồng từ 50 nhân viên trở lên, điều trị bệnh có sẵn có áp dụng thời gian chờ không? |
| hi_bench_v2_039 | pti.com.vn | medium | 0.8500 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Với hợp đồng từ 50 nhân viên trở lên, điều trị bệnh đặc biệt có áp dụng thời gian chờ không? |
| hi_bench_v2_040 | pti.com.vn | medium | 0.9094 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.9375 | 1.0000 | Nếu muốn chấm dứt hợp đồng, bên yêu cầu phải thông báo trước bao nhiêu ngày? |
| hi_bench_v2_041 | pti.com.vn | medium | 0.7250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.5000 | 1.0000 | Nếu người được bảo hiểm yêu cầu chấm dứt hợp đồng, PTI hoàn trả phí như thế nào? |
| hi_bench_v2_042 | pti.com.vn | medium | 0.7364 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.5455 | 1.0000 | Nếu PTI yêu cầu chấm dứt hợp đồng, PTI hoàn trả phí như thế nào? |
| hi_bench_v2_043 | pti.com.vn | high | 0.7406 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.5625 | 1.0000 | Người được bảo hiểm phải thông báo tổn thất trong bao lâu? |
| hi_bench_v2_044 | pti.com.vn | high | 0.7250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.5000 | 1.0000 | Hồ sơ yêu cầu bồi thường phải gửi trong thời hạn nào? |
| hi_bench_v2_045 | pti.com.vn | medium | 0.6795 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.3182 | 1.0000 | Giấy yêu cầu bồi thường của PTI cần thông tin gì? |
| hi_bench_v2_046 | pti.com.vn | high | 0.8972 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.8889 | 1.0000 | Trường hợp thương tật vĩnh viễn hoặc tử vong cần giấy tờ nào? |
| hi_bench_v2_047 | pti.com.vn | high | 0.8222 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.8889 | 1.0000 | Điều trị nội trú hoặc điều trị trong ngày cần chứng từ y tế nào trong hồ sơ bồi thường? |
| hi_bench_v2_048 | pti.com.vn | high | 0.9000 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.9000 | 1.0000 | Trường hợp phẫu thuật cần chứng từ gì? |
| hi_bench_v2_049 | pti.com.vn | medium | 0.7071 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.4286 | 1.0000 | Dịch vụ y tá chăm sóc tại nhà cần chứng từ nào? |
| hi_bench_v2_050 | pti.com.vn | high | 0.9250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | PTI giải quyết bồi thường trong bao lâu sau khi nhận đủ hồ sơ hợp lệ? |
| hi_bench_v2_051 | pti.com.vn | high | 0.9083 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.9333 | 1.0000 | PTI có thể yêu cầu cung cấp hóa đơn gốc và kết quả sức khỏe trước khi chi trả không? |
| hi_bench_v2_052 | pti.com.vn | medium | 0.9250 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Đồng bảo hiểm/bảo hiểm trùng áp dụng cho loại quyền lợi nào? |
| hi_bench_v3_001 | aia.com.vn | medium | 0.5500 | False | False | False | 1.0000 | 1.0000 | 1.0000 | 0.5000 | 1.0000 | AIA Bùng Gia Lực chi trả chi phí y tế theo giới hạn nào? |
| hi_bench_v3_002 | aia.com.vn | medium | 0.6167 | False | False | False | 1.0000 | 1.0000 | 1.0000 | 0.6667 | 1.0000 | Số tiền bảo hiểm mỗi năm hợp đồng của các chương trình AIA Bùng Gia Lực là bao nhiêu? |
| hi_bench_v3_003 | aia.com.vn | high | 0.4211 | False | False | False | 1.0000 | 1.0000 | 1.0000 | 0.1778 | 1.0000 | Quyền lợi thai sản của AIA Bùng Gia Lực áp dụng theo phạm vi địa lý nào? |
| hi_bench_v3_004 | aia.com.vn | medium | 1.0000 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Bảo hiểm Sức Khỏe Trọn Đời của AIA được phân phối như thế nào trong hợp đồng? |
| hi_bench_v3_005 | aia.com.vn | medium | 0.7200 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.3000 | 1.0000 | Khách hàng AIA Sức Khỏe Trọn Đời có thể lựa chọn những gì? |
| hi_bench_v3_006 | baominh.com.vn | medium | 1.0000 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Đối tượng tham gia Bảo Minh BHSK toàn diện kết hợp BHYT là ai? |
| hi_bench_v3_007 | baominh.com.vn | high | 0.7895 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.4737 | 1.0000 | Nếu tham gia không đúng đối tượng, Bảo Minh xử lý thế nào? |
| hi_bench_v3_008 | baominh.com.vn | high | 0.6727 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.1818 | 1.0000 | Quyền lợi tử vong do ốm đau/bệnh tật/thai sản của Bảo Minh có giới hạn theo chương trình... |
| hi_bench_v3_009 | baominh.com.vn | medium | 0.4616 | False | True | False | 1.0000 | 1.0000 | 1.0000 | 0.2791 | 1.0000 | Phạm vi địa lý bảo hiểm thuyền viên Bảo Minh gồm những vùng nào? |
| hi_bench_v3_010 | baominh.com.vn | high | 0.6860 | False | True | False | 1.0000 | 1.0000 | 1.0000 | 0.8400 | 1.0000 | Hồ sơ và thời hạn yêu cầu bồi thường trong quy tắc thuyền viên Bảo Minh nằm ở chương nào? |
| hi_bench_v3_011 | bic.vn | medium | 0.4875 | False | True | False | 1.0000 | 1.0000 | 1.0000 | 0.3438 | 1.0000 | BIC đồng ý trả tiền bảo hiểm với điều kiện chung nào? |
| hi_bench_v3_012 | bic.vn | medium | 0.6942 | False | True | False | 1.0000 | 1.0000 | 1.0000 | 0.8605 | 1.0000 | Bên mua bảo hiểm của BIC phải đáp ứng điều kiện gì? |
| hi_bench_v3_013 | bic.vn | medium | 0.5000 | False | True | True | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | Tuổi của người được bảo hiểm BIC được tính như thế nào? |
| hi_bench_v3_014 | bic.vn | medium | 1.0000 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Nếu không chỉ định người thụ hưởng, BIC giải quyết quyền lợi cho ai? |
| hi_bench_v3_015 | bic.vn | medium | 0.3944 | False | True | False | 1.0000 | 1.0000 | 1.0000 | 0.1111 | 1.0000 | Con cái trong quy tắc BIC tai nạn và sức khỏe được định nghĩa theo độ tuổi nào? |
| hi_bench_v3_016 | bic.vn | medium | 0.5500 | False | False | False | 1.0000 | 1.0000 | 1.0000 | 0.5000 | 1.0000 | Chi phí y tế thực tế trong quy tắc BIC gồm những gì? |
| hi_bench_v3_017 | libertyinsurance.com.vn | medium | 1.0000 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Liberty HealthCare có hạn mức lên đến bao nhiêu cho nội trú và ngoại trú? |
| hi_bench_v3_018 | libertyinsurance.com.vn | medium | 0.8545 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.6364 | 1.0000 | Giới hạn trách nhiệm bảo hiểm tối đa mỗi năm của Liberty HealthCare H1/H2/H3 là bao nhiêu? |
| hi_bench_v3_019 | libertyinsurance.com.vn | medium | 1.0000 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Tiền phòng và ăn uống theo ngày của Liberty Classic H1 và Executive H2 là bao nhiêu? |
| hi_bench_v3_020 | libertyinsurance.com.vn | medium | 0.4643 | False | True | False | 1.0000 | 1.0000 | 1.0000 | 0.2857 | 1.0000 | Liberty bản 2023 chi trả điều trị trước và sau nhập viện trong khoảng thời gian nào? |
| hi_bench_v3_021 | libertyinsurance.com.vn | medium | 0.4559 | False | False | False | 1.0000 | 1.0000 | 1.0000 | 0.2647 | 1.0000 | Điều trị tâm thần trong Liberty bản 2023 áp dụng cho chương trình nào? |
| hi_bench_v3_022 | pti.com.vn | medium | 0.7032 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.2581 | 1.0000 | PTI định nghĩa bệnh có sẵn như thế nào? |
| hi_bench_v3_023 | pti.com.vn | high | 1.0000 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | Bệnh đặc biệt trong năm bảo hiểm đầu tiên có bị loại trừ không? |
| hi_bench_v3_024 | pti.com.vn | high | 0.8933 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 0.7333 | 1.0000 | Người được bảo hiểm PTI phải thông báo tổn thất trong bao lâu? |
| hi_bench_v3_025 | pti.com.vn | high | 1.0000 | True | True | True | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | PTI giải quyết bồi thường tối đa bao nhiêu ngày làm việc sau khi nhận đủ hồ sơ? |
