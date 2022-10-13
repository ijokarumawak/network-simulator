from pydantic import BaseSettings


class Settings(BaseSettings):
    es_hosts: str = None
    es_cloud_id: str = None
    es_api_key: str = None

    class Config:
        env_file = ".env"


settings = Settings()
