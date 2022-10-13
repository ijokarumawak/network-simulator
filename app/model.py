from pydantic import BaseModel
from datetime import datetime
import math


class NetworkRequest(BaseModel):
  source_ip: str
  source_port: int
  destination_ip: str
  destination_port: int


class FlowRecord(BaseModel):
  host_name: str
  ingress_interface: int
  egress_interface: int
  source_bytes: int
  source_ip: str
  source_port: int
  source_locality: str
  destination_bytes: int
  destination_ip: str
  destination_port: int
  destination_locality: str

  def toEcs(self):
    now = datetime.utcnow().isoformat()
    source_packets = math.ceil(self.source_bytes / 2048)
    destination_packets = math.ceil(self.destination_bytes / 2048)
    ecs = {
      '@timestamp': now,
      'agent': {'name': self.host_name},
      'client': {
        'bytes': self.source_bytes,
        'ip': self.source_ip,
        'packets': source_packets,
        'port': self.source_port
      },
      'source': {
        'bytes': self.source_bytes,
        'ip': self.source_ip,
        'packets': source_packets,
        'port': self.source_port,
        'locality': self.source_locality
      },
      'destination': {
        'bytes': self.destination_bytes,
        'ip': self.destination_ip,
        'packets': destination_packets,
        'port': self.destination_port,
        'locality': self.destination_locality
      },
      'ecs': {'version': '8.4.0'},
      'event': {'action': 'netflow_flow', 'category': ['netword', 'session']},
      'created': now,
      'kind': 'event',
      'type': 'connection',
      'flow': {},
      'host': {'hostname': self.host_name, 'name': self.host_name},
      'input': {'type': 'netflow'},
      'netflow': {
        'ingress_interface': self.ingress_interface,
        'egress_interface': self.egress_interface,
        'locality': self.source_locality == 'external' or self.destination_locality == 'external'
      },
      'network': {
        'bytes': self.source_bytes + self.destination_bytes,
        'packets': source_packets + destination_packets
      }
    }
    return ecs