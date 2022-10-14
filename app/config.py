from typing import Union
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    es_hosts: str = None
    es_cloud_id: str = None
    es_api_key: str = None
    es_ds_namespace: Union[str, None] = Field(default='default')

    class Config:
        env_file = ".env"


settings = Settings()
