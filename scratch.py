import requests

r = requests.post("https://api.deepai.org/api/torch-srgan",
    data={
        'image': url,
    },
    headers={'api-key': os.environ['deepai_key']}
)
print(r.json()['output_url'])