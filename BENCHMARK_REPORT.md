# Benchmark & Observability Report — Day 14

**Họ tên:** Hồ Trọng Nghĩa (MSSV: 2A202603729)
**Ngày chạy:** 26/11/2026
**Môi trường:** Windows PowerShell, Python `.venv`, benchmark agent v2 chạy local tại `127.0.0.1:8002`. Observability stack chạy trên Docker Desktop Engine 29.4.3 với 4 vCPU và 7,76 GiB RAM.

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---:|---|
| p95 latency `/ask` | `≤ 500 ms` | Giữ phần lớn request trong mức phản hồi tương tác. |
| Error rate `/ask` | `≤ 2%` | Giới hạn lỗi đo được trong một batch benchmark. |
| Accuracy trên golden dataset | `≥ 100%` cho quality gate | Bắt regression kiến thức trước khi coi bản sửa đạt. |

## 2. Benchmark hiệu năng

### 2.1 Concurrency vs latency, agent v2

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 3.95 | 203.6 | 238.3 | 1704.1 | 0.67% | PASS |
| 10 | 36.97 | 192.3 | 238.4 | 1684.7 | 0.33% | PASS |
| 50 | 104.88 | 202.6 | 335.3 | 1696.1 | 1.33% | PASS |
| 100 | 53.44 | 382.8 | 3675.3 | 3937.9 | 1.00% | FAIL (p95) |

Source files: `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json`.

**Nhận xét:** Throughput tăng từ 3.95 RPS ở concurrency 1 lên 104.88 RPS ở concurrency 50, nhưng giảm còn 53.44 RPS ở concurrency 100. Tail latency tăng mạnh ở concurrency 100 (p95 3675.3 ms), vượt SLO dù error rate vẫn dưới 2%; đây là dấu hiệu cần giới hạn concurrency hoặc scale thêm instance.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|
| 0 | 189.7 | 224.7 | 232.7 |
| 0.03 | 222.9 | 227.6 | 1683.8 |
| 0.1 | 316.3 | 1683.9 | 1714.9 |

**Nhận xét:** Tăng `MOCK_SLOW_RATE` làm average tăng từ 189.7 lên 316.3 ms và làm tail latency xấu rõ rệt; ở 0.1, p95 đạt 1683.9 ms nên không đạt SLO. P99 cũng nhảy lên 1683.8–1714.9 ms khi xuất hiện slow path.

## 3. Benchmark chất lượng

| Chỉ số | Agent v1 | Agent v2 | Agent v2 sau sửa KB |
|---|---:|---:|---:|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100.00% (23/23) |
| Avg tokens/câu | 57.0 | 109.1 | 117.4 |
| Tổng cost (USD) | 0.000402 | 0.000762 | 0.000818 |
| Cost/câu đúng (USD) | 0.000402 | 0.000036 | 0.000036 |
| Quality gate | FAIL | PASS | PASS |

| ID | Keyword thiếu | Cách sửa |
|---|---|---|
| security-02; scaling-03 | `token`, `hết hạn`, `chữ ký`; `cpu`, `memory`, `custom metrics` | Bổ sung các thuật ngữ vào knowledge base/mock response; chạy lại eval v2 fixed đạt 23/23. |

Sources: `reports/eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json`.

**Nhận xét trade-off:** v2 tăng độ dài trung bình từ 57.0 lên 109.1 tokens nhưng accuracy tăng mạnh lên 91.3%. Bản sửa KB tăng nhẹ lên 117.4 tokens và cost tổng lên 0.000818 USD, đổi lại đạt quality gate 100% với không có regression; cost/câu đúng vẫn khoảng 0.000036 USD.

### Quality gate trong CI

`run_eval.py` trả exit code `0` khi accuracy đạt `--min-accuracy` và không có regression so với `--baseline`; nếu một điều kiện không đạt, script trả exit code `1`. CI có thể chạy eval với golden dataset và baseline đã chấp nhận, rồi chỉ cho phép merge khi bước eval thành công. Trong kết quả nộp, `eval_v2_fixed.json` đạt 23/23, accuracy 100%, không có regression và quality gate pass.

## 4. Observability stack

- [Grafana khi có tải](screenshots/grafana-dashboard.png)
- [Jaeger trace chậm](screenshots/jaeger-slow-trace.png)
- [Jaeger trace lỗi](screenshots/jaeger-error-trace.png)
- [Prometheus với ba alert cùng firing](screenshots/prometheus-alert-firing.png)

`promtool test rules alert_rules_test.yml` trả `SUCCESS`. Lượt quan sát A–C áp dụng ba thay đổi cùng lúc, sau đó chạy Locust với 60 user, ramp 10 user/s trong 5 phút. Thời gian được tính từ lúc Locust bắt đầu đến mẫu `ALERTS{alertstate="firing"}` đầu tiên, với bước truy vấn 5 giây. Các thay đổi được bật cùng lúc nên số đo thể hiện tác động kết hợp của cấu hình.

### Exercise 7.4: Đọc dashboard

Ảnh Grafana ghi nhận khoảng 27,9 request/s, p95 khoảng 1,92 giây và avg khoảng 0,7 giây tại thời điểm chụp. Chênh lệch cho thấy một nhóm request có tail latency cao dù phần lớn request nhanh hơn; percentile phản ánh trải nghiệm của nhóm request chậm rõ hơn số trung bình.

Dashboard có panel `Requests/s theo instance` để so sánh traffic giữa hai replica, nhưng ảnh đã nộp không hiển thị panel đó. Vì vậy bằng chứng hiện có chưa đủ để kết luận traffic được chia đều giữa hai replica.

Input tokens/s thường lớn hơn output tokens/s vì mỗi request gửi prompt cùng context/knowledge vào model, trong khi output chỉ là phần câu trả lời được sinh ra. Qua Nginx, `curl http://localhost:8080/metrics` trả HTTP 404 theo cấu hình. Nginx chặn route này để không công khai thông tin metrics; Prometheus scrape trực tiếp agent trong mạng Docker nội bộ.

| Thí nghiệm | Alert firing | Thời gian tới firing | Panel rõ nhất |
|---|---|---|---|
| A · `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | khoảng 85 giây | Grafana Error rate |
| B · `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | khoảng 145 giây | Grafana Latency p95 |
| C · `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | khoảng 150 giây | Grafana Cost |
| D · Pause 1 replica | `AgentInstanceDown` | 40,2 giây từ lúc pause đến lần đọc đầu tiên thấy firing | Prometheus `/alerts` |
| E · `AGENT_VERSION=v1` | Đánh giá chất lượng qua eval ở phần 3 | — | Accuracy và quality gate |

Quality gate phát hiện lỗi ở E bằng cách chạy lại golden dataset và so sánh từng câu với baseline. Agent v1 chỉ đạt 1/23 dù vẫn có thể trả HTTP 200. Alert đo latency, lỗi HTTP hoặc chi phí không phản ánh trực tiếp đáp án sai.

### Debug bằng trace

Trace chậm `078cea837a04db14da1472bbc4d2dd89` trả HTTP 200 sau 2061,3 ms. Span xử lý chính `chat mock-llm-large` chiếm khoảng 2,0 giây trong Jaeger. Log `llm_call` đo 1978,5 ms, tương đương khoảng 96% tổng thời gian request.

Trích các trường từ dòng log `http_request` cùng `trace_id`.

```json
{
  "trace_id": "078cea837a04db14da1472bbc4d2dd89",
  "request_id": "2595b9bf6d2c",
  "route": "/ask",
  "status": 200,
  "ms": 2061.3
}
```

Trace lỗi `95464bd25705236194af707dcaf2795c` trả HTTP 503 sau khoảng 107 ms. Span `chat mock-llm-small` có event `exception` với thông báo `Upstream LLM error: 503 Service Unavailable (mock)`.

## 5. Benchmark scaling

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---:|---:|---:|---:|---:|---:|
| 1 | 66.33 | 190 | 220 | 1700 | 77 / 7,892 (0.97%) |
| 3 | 66.19 | 190 | 220 | 1700 | 62 / 7,888 (0.79%) |

Sources: `benchmark-results/scale_1_stats.csv`, `scale_3_stats.csv`.

**Giải thích:** Mỗi lượt chạy 100 user, ramp 10 user/s trong 2 phút. Bảng dùng dòng `Aggregated` của CSV. RPS gần như giữ nguyên từ 66,33 đến 66,19 và p99 vẫn 1.700 ms. Tỷ lệ lỗi trong hai lượt lần lượt là 0,97% và 0,79%. Với một lượt cho mỗi cấu hình và lỗi mock được mô phỏng ngẫu nhiên, dữ liệu chưa cho thấy tăng replica làm giảm lỗi hay cải thiện thông lượng ở mức tải này.

## 6. Kết luận

1. Benchmark local đạt throughput cao nhất tại concurrency 50 trong các mức đã đo. Ở concurrency 100, p95 vượt SLO dù error rate vẫn dưới 2%.
2. Trace chậm cho thấy lời gọi mock LLM chiếm khoảng 96% thời gian. `trace_id` nối kết quả tổng hợp trên dashboard với một request trong Jaeger và log JSON.
3. Alert phát hiện lỗi HTTP, p95 và mức tiêu chi phí mô phỏng. Eval phát hiện chất lượng đáp án giảm, còn benchmark scaling chỉ cho thấy tác động của số replica trong workload đã đo.

Một metric bổ sung là tỷ lệ câu đúng trong lượt eval định kỳ theo phiên bản agent. Đặt cảnh báo khi quality gate thất bại hoặc accuracy giảm dưới baseline đã chấp nhận.
