# ============================================================
# TODO (tiêu chí 1): viết lại thành Dockerfile production
#   • Multi-stage build: stage builder cài dependencies, stage runtime chỉ copy kết quả
#   • Base image slim (vd python:3.11-slim) và chạy bằng user non-root
#   • Có HEALTHCHECK gọi GET /health
#   • Image cuối < 500 MB
#   • CMD lắng nghe theo biến PORT (mặc định 8000) và uvicorn phải là PID 1
#     (exec form, hoặc `sh -c "exec uvicorn ..."`) để nhận SIGTERM khi `docker stop`
#
# Bản dưới đây build và chạy được nhưng CHƯA đạt yêu cầu nào ở trên.
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
RUN useradd --create-home --shell /usr/sbin/nologin agent
USER agent
ENV PYTHONUNBUFFERED=1
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT','8000') + '/health')"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
