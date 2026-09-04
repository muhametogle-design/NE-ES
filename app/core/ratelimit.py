import time
from collections import defaultdict
from functools import wraps
from fastapi import HTTPException, Request

class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)

    def reset(self):
        self.requests.clear()

    def is_allowed(self, client_ip: str, max_requests: int, window_seconds: int) -> bool:
        now = time.time()
        self.requests[client_ip] = [t for t in self.requests[client_ip] if now - t < window_seconds]
        if len(self.requests[client_ip]) >= max_requests:
            return False
        self.requests[client_ip].append(now)
        return True

    def __call__(self, max_requests: int = 5, window_seconds: int = 300):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                request: Request = kwargs.get("request")
                if not request:
                    for arg in args:
                        if isinstance(arg, Request):
                            request = arg
                            break
                if request:
                    client_ip = request.client.host if request.client else "127.0.0.1"
                    if not self.is_allowed(client_ip, max_requests, window_seconds):
                        raise HTTPException(
                            status_code=429,
                            detail="Too many login attempts. Please wait before trying again."
                        )
                return await func(*args, **kwargs)
            return wrapper
        return decorator

rate_limit = RateLimiter()
