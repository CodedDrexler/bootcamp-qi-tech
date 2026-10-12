import time
from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUESTS = Counter(
    "bank_http_requests_total", "HTTP responses", ["method", "route", "status"]
)
DURATION = Histogram(
    "bank_http_duration_seconds",
    "HTTP request duration",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)


def register_metrics(app):
    @app.middleware("http")
    async def observe(request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            if request.url.path not in ("/metrics", "/health_check", "/"):
                REQUESTS.labels(request.method, route, str(status)).inc()
                DURATION.labels(request.method, route).observe(
                    time.perf_counter() - start
                )

    def metrics():
        return Response(
            generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST}
        )

    app.add_api_route("/metrics", metrics, methods=["GET"])
