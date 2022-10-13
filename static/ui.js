async function toggleInterfaceStatus(networkId, i) {
  const response = await fetch('/' + networkId + '/interfaces/' + i + '/toggle_status', {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    },
    body: `{}`,
  });
    
  response.json().then(data => {
    console.log(data);
    location.reload();
  });

}