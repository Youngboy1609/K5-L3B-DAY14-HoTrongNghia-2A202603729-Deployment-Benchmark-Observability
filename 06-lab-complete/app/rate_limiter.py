"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""

import time
from fastapi import HTTPException
from .config import settings
from .redis_client import r


def check_rate_limit(key: str) -> None:
    # TODO: gợi ý dùng Redis sorted set: ZREMRANGEBYSCORE → ZCARD → ZADD → EXPIRE
    now = time.time()
    redis_key = f"rate:{key}"
    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - 60)
        pipe.zcard(redis_key)
        _, count = pipe.execute()
        if count >= settings.rate_limit_per_minute:
            raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "60"})
        member = f"{now:.6f}"
        r.zadd(redis_key, {member: now})
        r.expire(redis_key, 60)
    except HTTPException:
        raise
    except Exception:
        # Redis readiness is reported separately. Fail closed for protection.
        raise HTTPException(status_code=503, detail="Rate limiter unavailable")
