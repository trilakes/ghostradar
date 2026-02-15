import requests, json

headers = {'Authorization': 'Bearer rnd_OdL3HoIrqUn5xJQAfzqnaGYVe3gY'}
r = requests.get('https://api.render.com/v1/services/srv-d68jhe1r0fns73fn5osg/deploys', headers=headers, params={'limit': 5})
for d in r.json():
    dep = d['deploy']
    msg = dep.get('commit', {}).get('message', 'n/a')[:60]
    print(f"{dep['id']}: {dep['status']} - {msg}")
