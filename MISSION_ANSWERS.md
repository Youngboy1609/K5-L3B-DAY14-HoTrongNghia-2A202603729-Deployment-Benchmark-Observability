# Day 14 Lab — Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

1. Hardcoded fake OpenAI key và PostgreSQL URL trong `01-localhost-vs-production/develop/app.py`.
2. `DEBUG = True` và `MAX_TOKENS` cố định thay vì cấu hình từ environment.
3. Request handler dùng `print()` và còn ghi API key vào log.
4. Không có `/health` hoặc `/ready` để platform kiểm tra process.
5. Uvicorn bind `localhost`, port `8000` và `reload=True`, nên không phù hợp container/cloud.

### Exercise 1.2: Test results

Đã gọi bằng FastAPI TestClient để tránh xung đột cổng đang dùng bởi service khác:

```text
develop POST /ask?question=Hello -> 200
production GET /health -> 200, GET /ready -> 200, POST /ask JSON -> 200
```

Develop log cũng cho thấy implementation ghi `[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this`. Production log cảnh báo thiếu `OPENAI_API_KEY` và dùng mock LLM.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
|---|---|---|---|
| Config | Giá trị cố định trong `app.py` | `config.py` đọc environment | Có thể đổi theo môi trường mà không sửa image |
| Secrets | Hardcoded và bị log ra | Environment, không log secret | Giảm nguy cơ lộ key và hỗ trợ rotate |
| Health/readiness | Không có endpoint | Có `/health` và `/ready` | Platform biết process sống và đã sẵn sàng |
| Shutdown | Reload/debug, không lifecycle | FastAPI lifespan và SIGTERM logging | Hoàn tất request trước khi dừng |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. Base image: `python:3.11` cho develop.
2. Working directory: `/app`.
3. `requirements.txt` được copy và cài trước source để Docker cache dependency layer.
4. Develop chạy `python app.py`; advanced runtime chạy Uvicorn với `main:app`, host `0.0.0.0`, port `8000`, 2 workers.

### Exercise 2.2–2.4: Test results

Đã build từ repo root bằng hai lệnh `docker build -f ...`.

```text
day14-agent-develop    1.67GB
day14-agent-production 240MB
```

Production dùng builder/runtime multi-stage, image slim và non-root user. Compose production gồm agent, Redis, Qdrant và Nginx. Nginx nhận traffic ngoài và proxy tới agent; Redis lưu state/cache; Qdrant phục vụ vector search.

| Image | Size | Command/source |
|---|---:|---|
| Develop | 1.67GB | `docker image ls day14-agent-develop` |
| Production | 240MB | `docker image ls day14-agent-production` |
| Difference | khoảng 85.6% nhỏ hơn | `(1670-240)/1670*100`, quy đổi theo số MB hiển thị |

Kiểm tra container riêng bằng các cổng host `18080` và `18081` để không ảnh hưởng service khác:

```text
day14-cp2-develop:   GET /health -> 200, POST /ask?question=Hello -> 200
day14-cp2-production: GET /health -> 200, GET /ready -> 200,
                      POST /ask JSON -> 200
```

Kiểm tra đúng production Compose qua Nginx bằng override tạm thời ánh xạ
`127.0.0.1:18082:80` (không dùng cổng 80/443 của file mẫu). Kết quả gọi qua
`http://127.0.0.1:18082`:

```text
GET /health -> 200, GET /ready -> 200, POST /ask JSON -> 200
```

Luồng request thực tế:

```text
Client (127.0.0.1:18082)
          |
          v
   Nginx reverse proxy :80
          |
          v
   agent FastAPI :8000  ----> Redis :6379 (state/cache)
          |
          +-----------------> Qdrant :6333 (vector search)
```

Compose kiểm tra: `redis` và `qdrant` healthy trước khi `agent` start; Nginx
nhận request bên ngoài và chuyển `/health`, `/ready`, `/ask` vào agent trên
network nội bộ. Sau kiểm tra đã hạ toàn bộ stack bằng `docker compose down`.

## Part 3: Cloud Deployment

### Exercise 3.1/3.2: Public deployment

- Platform: Railway Trial, project `k5-day14`, service `agent` và Redis.
- URL: https://agent-production-8573cb06.up.railway.app
- Evidence: `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`
- `GET /health`: 200.
- `GET /ready`: 200.
- `POST /ask` thiếu API key: 401.
- `POST /ask` có API key hợp lệ: 200.

Các mã HTTP được ghi nhận từ URL public ngày 26/11/2026. Xem cấu hình và lệnh tái chạy trong [DEPLOYMENT.md](DEPLOYMENT.md).

### Exercise 3.3: Cloud Run pipeline

Cloud Build chạy pytest trước, sau đó build image gắn `$COMMIT_SHA` và `latest`. Pipeline push cả hai tag lên Container Registry rồi deploy image theo commit lên Cloud Run ở `asia-southeast1`. Service giới hạn 1–10 instance, concurrency 80, timeout 60 giây và dùng Secret Manager cho key.

### Platform comparison

`railway.toml` dùng Railway builder Nixpacks, start command Uvicorn và healthcheck `/health`. `render.yaml` khai báo web service Python, build/start command, health check `/health`, secret `AGENT_API_KEY` với `generateValue: true` và Redis add-on. Railway config hiện là cho app mẫu Part 3, còn Part 6 cần dùng config trong `06-lab-complete/`.

## Part 4: API Security

### Exercise 4.1–4.3: Test results

Chạy lại app mẫu trong `04-api-gateway/production/` tại `127.0.0.1:18084` ngày 26/11/2026. Dưới đây là dòng trạng thái và các header liên quan trích từ output `curl -i` cho `POST /ask`. JWT chỉ được dùng trong request local.

```http
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
content-type: application/json

HTTP/1.1 200 OK
content-type: application/json

HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795679033
retry-after: 59
content-type: application/json
```

Khi gửi 11 request liên tiếp với cùng JWT sau khi khởi động app, 10 request đầu trả `200` và request thứ 11 trả `429`. `retry-after: 59` là thời gian chờ tính bằng giây tại lần đo này.

Các quy tắc đọc từ source:
- API key develop: thiếu key -> 401, key sai -> 403, key đúng -> 200.
- JWT production: `POST /auth/token` với `student/demo123`, token hết hạn sau 60 phút.
- Rate limiter dùng sliding-window counter in-memory, user 10 request/phút, admin 100 request/phút; vượt giới hạn -> 429 và `Retry-After`.
- Cost guard kiểm tra ngân sách trước khi gọi mock LLM. Ngân sách là $1/ngày cho mỗi user và $10/ngày cho toàn hệ thống. Vượt ngân sách của user trả `402`.

### Exercise 4.4: Cost guard implementation

`CostGuard` tính chi phí từ input/output tokens, reset record theo ngày, kiểm tra user budget trước request và ghi usage sau response. Khi user vượt $1/ngày, endpoint trả 402. Global budget $10/ngày làm service trả 503. Bản mẫu lưu state trong RAM, nên khi scale nhiều instance cần chuyển sang Redis.

## Part 5: Scaling & Reliability

### Exercise 5.1–5.3

- `/health` cho biết process vẫn hoạt động. `/ready` cho biết agent đã sẵn sàng nhận traffic và có thể trả `503` khi Redis chưa kết nối được.
- Khi nhận SIGTERM, Uvicorn ngừng nhận kết nối mới và chờ các request đang chạy. FastAPI gọi phần dọn dẹp của `lifespan` khi tắt.
- Agent production đọc và ghi session theo `session_id` trong Redis. Mỗi replica có RAM riêng, nên chuyển session sang Redis cho phép các replica đọc chung lịch sử.

### Exercise 5.4–5.5

Chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3`, sau đó chạy `python test_stateless.py`. Nginx nhận 5 request trên cổng 8080 và phân phối qua cả 3 replica (`instance-9f3f87`, `instance-18411e`, `instance-9c670c`). `GET /chat/{session_id}/history` trả 10 tin nhắn, gồm 5 câu hỏi và 5 câu trả lời trong cùng session. Kết quả xác nhận các replica chia sẻ được lịch sử qua Redis trong lúc cả ba đang hoạt động.

## Part 6: Final Project

### Production readiness check

Chạy `python check_production_ready.py --redis-url redis://127.0.0.1:6390/0 --public-url https://agent-production-8573cb06.up.railway.app` trong container Linux Python 3.11 dùng Docker Engine của máy. Checker chạy toàn bộ kiểm tra, gồm build và chạy image, Redis, SIGTERM và URL public.

```text
📋 Checklist Deliverable
✅ Dockerfile (multi-stage, < 500 MB)
✅ docker-compose.yml (agent + redis)
✅ .dockerignore
✅ Health check endpoint (GET /health)
✅ Readiness endpoint (GET /ready)
✅ API Key authentication
✅ Rate limiting
✅ Cost guard
✅ Config từ environment variables
✅ Structured logging
✅ Graceful shutdown
✅ Public URL ready (Railway / Render config)

Result: 12/12 tiêu chí đạt · 42/42 checks passed
🎉 PASS 12/12 — PRODUCTION READY!
```

Docker image đo được 56 MB. Request đang chạy vẫn trả 200 khi checker gửi SIGTERM, và process thoát với exit code 0. Kiểm tra `docker stop` cũng trả exit code 0 sau 0,4 giây.

## Part 7: Benchmark & Observability

Benchmark local chạy 300 request mỗi lượt ở bốn mức concurrency và ba giá trị `MOCK_SLOW_RATE`. Eval v2 sau khi bổ sung knowledge base đạt 23/23 và không có regression. Xem số đo và phân tích trong [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md).

## AI log

| Ngày | Nội dung yêu cầu AI | Phần AI hỗ trợ | Kiểm chứng ghi nhận |
|---|---|---|---|
| 25–26/11/2026 | Đọc rubric, lập kế hoạch và phân chia các phần của lab. | Codex đối chiếu yêu cầu, đề xuất thứ tự chạy và hỗ trợ soạn báo cáo. | Các kết quả runtime được ghi ở từng Part theo lệnh đã chạy. |
| 25–26/11/2026 | Hoàn thiện agent Part 6 và kiểm tra cấu hình production. | Codex dùng subagent hỗ trợ triển khai code và chạy checker. | Xem output checker ở trên. |
| 26/11/2026 | Deploy agent lên Railway và đo Part 7. | Codex hỗ trợ deploy, kiểm tra HTTP, chạy benchmark và tổng hợp bằng chứng. | Sinh viên xác nhận đăng nhập Railway trực tiếp. Xem kết quả deploy trong `DEPLOYMENT.md` và các số đo trong `BENCHMARK_REPORT.md`. |
| 26/11/2026 | Bổ sung câu trả lời Part 7 sau khi rà rubric K5. | Codex đối chiếu Exercise 7.4, quality gate và bằng chứng Grafana, cập nhật giải thích trong báo cáo benchmark. | Codex đối chiếu số liệu với ảnh và báo cáo hiện có. |
| 26/11/2026 | Chạy lại observability stack và cập nhật bằng chứng. | Codex chạy Locust, truy vấn Prometheus, đối chiếu log với Jaeger và cập nhật báo cáo. | Kết quả và ảnh từ lượt chạy lại nằm trong `BENCHMARK_REPORT.md`. |
| 26/11/2026 | Bổ sung output `curl -i` cho CP3. | Codex chạy lại app mẫu local và trích dòng trạng thái cùng các header liên quan. | Codex đối chiếu ba mã HTTP với log Uvicorn và chỉ lưu phần phản hồi không chứa JWT. |

Phần sinh viên tự thực hiện: đăng nhập Railway, mở project `k5-day14`, kiểm tra sơ đồ dịch vụ thấy `agent` và `Redis` đều Online, rồi kiểm tra deployment `c40f1f15` ở trạng thái Active và log `/health`, `/ready` trả HTTP 200. Ảnh chụp dashboard và deployment được lưu trong `screenshots/`.
