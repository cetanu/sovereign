import structlog


structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ]
)

LOG = structlog.getLogger()
