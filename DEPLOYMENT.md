# Deployment Information

## Public URL

https://agent-production-8573cb06.up.railway.app

## Platform

Railway Trial, project `k5-day14`, môi trường `production`. Railway build service `agent` từ Dockerfile của `06-lab-complete/`. Agent kết nối với service Redis trong cùng project qua mạng nội bộ.

## Test Commands

```bash
BASE="https://agent-production-8573cb06.up.railway.app"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # expected 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # expected 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'                              # expected 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'                              # expected 200
```

Kết quả kiểm tra từ máy local ngày 26/11/2026 bằng PowerShell `Invoke-WebRequest`. Lệnh `curl` ở trên gửi cùng HTTP method, header và body.

| Request | Kỳ vọng | Thực tế |
|---|---:|---:|
| `GET /health` | 200 | 200 |
| `GET /ready` | 200 | 200 |
| `POST /ask` thiếu API key | 401 | 401 |
| `POST /ask` có API key hợp lệ | 200 | 200 |

## Environment Variables Set

- `PORT` có giá trị `8000`.
- `REDIS_URL` tham chiếu biến `REDIS_URL` của service Redis.
- `AGENT_API_KEY` được đặt trong biến môi trường của service `agent`.
- `ENVIRONMENT` có giá trị `production`.
- Agent dùng giá trị mặc định `RATE_LIMIT_PER_MINUTE=10` và `DAILY_BUDGET_USD=1.0`.

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Kết quả HTTP từ lần kiểm tra lúc 13:13 GMT+7](screenshots/test.png)
