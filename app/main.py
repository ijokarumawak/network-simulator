import random
import ipaddress
from numpy import source
from regex import F
import yaml
import requests
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from elasticsearch import AsyncElasticsearch
from elasticsearch import ConnectionError
from .config import settings
from .model import NetworkRequest, FlowRecord
from datetime import datetime


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
  for network in topology['networks']:
    network['messages'] = []
    network['interfaces'] = [{'i': i, 'active': True, 'delay': 0, 'bytes_in': 0, 'bytes_out': 0} for i  in range(0, network['num_of_interfaces'])]

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_network(id):
  return next(filter(lambda n : n['id'] == id, topology['networks']), None)

@app.get("/{network_id}/ui", response_class=HTMLResponse)
async def show_network(request: Request, network_id: str):
  network = get_network(network_id)
  return templates.TemplateResponse("network.html", {"request": request, "network": network})


@app.post('/{network_id}/send/')
async def send(network_id: str, request: NetworkRequest):
  network = get_network(network_id)
  print({'network_id': network_id, 'network': network, **request.dict()})

  # Generate some bytes randamly.
  source_bytes = random.randrange(200, 4096)
  destination_bytes = random.randrange(1024, 10240)

  # The flow went to the internet, end of story.
  if network_id == 'internet':
    return {'success': True, 'source_bytes': source_bytes, 'destination_bytes': destination_bytes, **request.dict()}

  # Pick interfaces randamly.
  num_of_interfaces = network['num_of_interfaces']
  ingress_interface = random.randrange(0, num_of_interfaces)
  egress_interface = random.randrange(0, num_of_interfaces)

  local_network = ipaddress.ip_network(network['network'])
  source_locality = 'internal' if ipaddress.ip_address(request.source_ip) in local_network else 'external'
  destination_locality = 'internal' if ipaddress.ip_address(request.destination_ip) in local_network else 'external'
  success = True

  # Check interface status, if it's down, return error response.
  if not network['interfaces'][ingress_interface]['active'] or not network['interfaces'][egress_interface]['active']:
    success = False
    source_bytes = 0
    destination_bytes = 0
  
  else:
    # If the interfaces are active, then process the request.
    if destination_locality == 'external':
      # transport
      destination_locality = 'external'
      res = await send(network['gateway'], request)
      print(res)

      # update result with the final one for consistency.
      source_bytes = res['source_bytes']
      destination_bytes = res['destination_bytes']
      success = res['success']


  # Track sent data volumes.
  network['interfaces'][ingress_interface]['bytes_in'] += source_bytes
  network['interfaces'][egress_interface]['bytes_out'] += destination_bytes

  # Generate a FlowRecord
  record = FlowRecord(host_name=network_id,
    ingress_interface=ingress_interface,
    egress_interface=egress_interface,
    source_bytes=source_bytes, source_ip=request.source_ip, source_port=request.source_port, source_locality=source_locality,
    destination_bytes=destination_bytes, destination_ip=request.destination_ip, destination_port=request.destination_port, destination_locality=destination_locality,
    # 3 = end of Flow detected, 4 = forced end
    flow_end_reason= 3 if success else 4)
  doc = record.toEcs()
  doc['data_stream'] = {'type': ds_type, 'dataset': ds_data_set, 'namespace': ds_namespace}

  try:
      res = await es.index(index=ds, document=doc)
      print(res)
  except (ConnectionError) as e:
      print('Elasticsearch data ingestion failed.')
      print(e)

  return {'success': success, 'source_bytes': source_bytes, 'destination_bytes': destination_bytes, **request.dict()}

@app.post('/{network_id}/interfaces/{i}/toggle_status')
async def toggle_status(network_id: str, i: int, request: Request):
  network = get_network(network_id)
  print({'network_id': network_id, 'network': network})
  status = not network['interfaces'][i]['active']
  network['interfaces'][i]['active'] = status
  network['messages'].insert(0, {'timestamp':datetime.utcnow().isoformat(), 'message': 'Interface {} is {}.'.format(i, 'UP' if status else 'DOWN') })
  return {'success': True}

