import random
import ipaddress
import yaml
import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from elasticsearch import AsyncElasticsearch
from elasticsearch import ConnectionError
from .config import settings
from .model import NetworkRequest, FlowRecord


if settings.es_cloud_id:
    es = AsyncElasticsearch(cloud_id=settings.es_cloud_id, api_key=settings.es_api_key)
elif settings.es_hosts:
    es = AsyncElasticsearch(hosts=settings.es_hosts, api_key=settings.es_api_key)
else:
    raise Exception('Either ES_CLOUD_ID or ES_HOSTS is required.')

ds_type = 'logs'
ds_data_set = 'netflow.log'
ds_namespace = 'test'
ds = '{}-{}-{}'.format(ds_type, ds_data_set, ds_namespace)

with open('topology.yml', 'r') as file:
  topology = yaml.safe_load(file)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/items/{id}", response_class=HTMLResponse)
async def read_item(request: Request, id: str):
    return templates.TemplateResponse("item.html", {"request": request, "id": id})


@app.post('/{network_id}/send/')
async def send(network_id: str, request: NetworkRequest):
  network = next(filter(lambda n : n['id'] == network_id, topology['networks']), None)
  print({'network_id': network_id, 'network': network, **request.dict()})

  if network_id == 'internet':
    return {'success': True}

  local_network = ipaddress.ip_network(network['network'])
  source_locality = 'internal' if ipaddress.ip_address(request.source_ip) in local_network else 'external'
  destination_locality = 'internal'
  if not ipaddress.ip_address(request.destination_ip) in local_network:
    # transport
    destination_locality = 'external'
    res = await send(network['gateway'], request)
    print(res)


  num_of_interfaces = network['num_of_interfaces']
  record = FlowRecord(host_name=network_id,
    ingress_interface=random.randrange(0, num_of_interfaces),
    egress_interface=random.randrange(0, num_of_interfaces),
    source_bytes=random.randrange(200, 4096), source_ip=request.source_ip, source_port=request.source_port, source_locality=source_locality,
    destination_bytes=random.randrange(1024, 10240), destination_ip=request.destination_ip, destination_port=request.destination_port, destination_locality=destination_locality)
  doc = record.toEcs()
  doc['data_stream'] = {'type': ds_type, 'dataset': ds_data_set, 'namespace': ds_namespace}

  try:
      res = await es.index(index=ds, document=doc)
      print(res)
  except (ConnectionError) as e:
      print('Elasticsearch data ingestion failed.')
      print(e)

  return {'success': True}
