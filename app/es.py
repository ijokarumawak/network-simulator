from typing import Union
from pydantic import BaseModel, Field
from elasticsearch import AsyncElasticsearch
from .config import settings

es = None
if settings.es_cloud_id:
    es = AsyncElasticsearch(cloud_id=settings.es_cloud_id, api_key=settings.es_api_key)
elif settings.es_hosts:
    es = AsyncElasticsearch(hosts=settings.es_hosts, api_key=settings.es_api_key)
else:
    raise Exception('Either ES_CLOUD_ID or ES_HOSTS is required.')


class DataStream(BaseModel):
  type: str
  dataset: str
  namespace: str = settings.es_ds_namespace

  def name(self):
    return '{}-{}-{}'.format(self.type, self.dataset, self.namespace)

  def add_ds_fields(self, doc):
    doc['data_stream'] = {'type': self.type, 'dataset': self.dataset, 'namespace': self.namespace}

