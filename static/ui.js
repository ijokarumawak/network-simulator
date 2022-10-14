async function toggleInterfaceStatus(networkId, i) {
  const response = await fetch('/' + networkId + '/interfaces/' + i + '/toggle_status', {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    body: {},
  });
    
  response.json().then(data => {
    console.log(data);
    location.reload();
  });
}

async function setInterfaceDelay(event) {
  if (event.key === 'Enter') {
    const networkId = event.target.getAttribute('x-network');
    const i = event.target.getAttribute('x-interface');
    const delay = event.target.value;
    console.log(networkId, i, delay);

    const response = await fetch('/' + networkId + '/interfaces/' + i + '/set_delay?delay=' + delay, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      },
      body: {},
    });
      
    response.json().then(data => {
      console.log(data);
      location.reload();
    });
  }
}