import requests

response = requests.post(
    "http://localhost:8000/ask",
    json={"question": "Что такое конституция?"}
)

print(response.json())