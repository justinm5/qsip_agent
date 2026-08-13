import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    kafka_brokers: str = "localhost:9092"
    db_dsn: str = "postgres://qsip:qsip@localhost:5432/qsip?sslmode=disable"
    redis_addr: str = "localhost:6379"
    otel_endpoint: str = ""
    model_path: str = "/models"
    polygon_api_key: str = ""
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    newsapi_key: str = ""
    finnhub_key: str = ""
    ollama_host: str = "http://localhost:11434"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "qsip"
    minio_secret_key: str = "qsip12345678"
    alpha_vantage_key: str = ""
    fmp_key: str = ""
    jwt_secret: str = "change-me"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            kafka_brokers=os.getenv("KAFKA_BROKERS", "localhost:9092"),
            db_dsn=os.getenv("TIMESCALEDB_DSN", "postgres://qsip:qsip@localhost:5432/qsip?sslmode=disable"),
            redis_addr=os.getenv("REDIS_ADDR", "localhost:6379"),
            otel_endpoint=os.getenv("OTEL_ENDPOINT", ""),
            model_path=os.getenv("MODEL_PATH", "/models"),
            polygon_api_key=os.getenv("POLYGON_API_KEY", ""),
            alpaca_api_key=os.getenv("ALPACA_API_KEY", ""),
            alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            newsapi_key=os.getenv("NEWSAPI_KEY", ""),
            finnhub_key=os.getenv("FINNHUB_KEY", ""),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            minio_endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            minio_access_key=os.getenv("MINIO_ACCESS_KEY", "qsip"),
            minio_secret_key=os.getenv("MINIO_SECRET_KEY", "qsip12345678"),
            alpha_vantage_key=os.getenv("ALPHA_VANTAGE_KEY", ""),
            fmp_key=os.getenv("FMP_KEY", ""),
            jwt_secret=os.getenv("JWT_SECRET", "change-me"),
        )
