from datetime import datetime
import math

class FlowRecord():

  def __init__(self,
  host_name:str,
  interface_name:str,
  client_bytes:int,
  client_ip:str,
  client_port:int,
  destination_bytes:int,
  destination_ip:str,
  destination_port:int
) -> None:
    self.host_name = host_name
    self.interface_name = interface_name
    self.client_bytes = client_bytes
    self.client_ip = client_ip
    self.client_port = client_port
    self.destination_bytes = destination_bytes
    self.destination_ip = destination_ip
    self.destination_port = destination_port

  def toEcs(self):
    now = datetime.utcnow().isoformat()
    client_packet = math.ceil(self.client_bytes / 2048)
    destination_packet = math.ceil(self.destination_bytes / 2048)
    return {
      '@timestamp': now,
      'agent': {'name': self.host_name},
      'client': {
        'bytes': self.client_bytes,
        'ip': self.client_ip,
        'packets': client_packet,
        'port': self.client_port
      },
      'destination': {
        'bytes': self.destination_bytes,
        'ip': self.destination_ip,
        'packets': destination_packet,
        'port': self.destination_port
      },
      'ecs': {'version': '8.4.0'},
      'event': {'action': 'netflow_flow', 'category': ['netword', 'session']},
      'created': now,
      'kind': 'event',
      'type': 'connection',
      'flow': {},
      'host': {'hostname': self.host_name, 'name': self.host_name},
      'input': {'type': 'netflow'},
      'netflow': {'interface_name': self.interface_name},
      'network': {
        'bytes': self.client_bytes + self.destination_bytes,
        'packets': client_packet + destination_packet
      }
    }