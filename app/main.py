import asyncio
import random
import ipaddress
import yaml
import time
import math
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from elasticsearch import ConnectionError
from .es import es, DataStream
from .model import NetworkRequest, FlowRecord
from datetime import datetime


ds = DataStream(type='logs', dataset='netflow.log')

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
  start_timestamp = datetime.utcnow()

  # The flow went to the internet, end of story.
  if network_id == 'internet':
    # Add some delay.
    await asyncio.sleep(random.randrange(200, 2000) / 1000)
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
    # Add some delay.
    delay = network['interfaces'][ingress_interface]['delay'] + network['interfaces'][egress_interface]['delay']
    await asyncio.sleep(delay / 1000)

    # If the interfaces are active, then process the request.
    if destination_locality == 'external':
      # transport
      destination_locality = 'external'

      # if no routing found, then use gateway
      send_to = network['gateway']

      # if the network has routings, check that
      if 'routings' in network:
        for routing in network['routings']:
          if ipaddress.ip_address(request.destination_ip) in ipaddress.ip_network(get_network(routing)['network']):
            send_to = routing
            break

      res = await send(send_to, request)
      print(res)

      # update result with the final one for consistency.
      source_bytes = res['source_bytes']
      destination_bytes = res['destination_bytes']
      success = res['success']


  # Track sent data volumes.
  network['interfaces'][ingress_interface]['bytes_in'] += source_bytes
  network['interfaces'][egress_interface]['bytes_out'] += destination_bytes
  end_timestamp = datetime.utcnow()

  # Generate a FlowRecord
  record = FlowRecord(host_name=network_id,
    ingress_interface=ingress_interface,
    egress_interface=egress_interface,
    source_bytes=source_bytes, source_ip=request.source_ip, source_port=request.source_port, source_locality=source_locality,
    destination_bytes=destination_bytes, destination_ip=request.destination_ip, destination_port=request.destination_port, destination_locality=destination_locality,
    # 3 = end of Flow detected, 4 = forced end
    flow_end_reason= 3 if success else 4,
    event_start=start_timestamp, event_end=end_timestamp)
  doc = record.toEcs()
  ds.add_ds_fields(doc)

  try:
      res = await es.index(index=ds.name(), document=doc)
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


@app.post('/{network_id}/interfaces/{i}/set_delay')
async def set_delay(network_id: str, i: int, delay: int):
  network = get_network(network_id)
  print({'network_id': network_id, 'network': network, 'delay': delay})
  network['interfaces'][i]['delay'] = delay
  network['messages'].insert(0, {'timestamp':datetime.utcnow().isoformat(), 'message': 'Set delay of interface {} to {} ms.'.format(i, delay) })
  return {'success': True}

