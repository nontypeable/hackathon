import requests

from statuses.types_of_statuses import Statuses

from db.db import *


def get_qr_info_and_insert(url: str):
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        qr_code = data.get("qr_code")

        if qr_code:
            # Проверяем, существует ли запись с таким QR-кодом в базе данных
            existing_record = fetch_one("SELECT * FROM qr_data WHERE qr_code=?", (qr_code,))
            if existing_record:
                print("Record with this QR code already exists.")
            else:
                execute("INSERT INTO products (qr_code, status) VALUES (?, ?)", (qr_code, Statuses.expected_production))

        return data
    else:
        print("Failed to fetch data. Status code:", response.status_code)
        return None
