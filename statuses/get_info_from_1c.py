import requests


def get_qr_info(url: str, params: dict):
    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print("Failed to fetch data. Status code:", response.status_code)
        return None
