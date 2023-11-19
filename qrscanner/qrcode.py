import hashlib

import cv2
import numpy as np
from dotenv import load_dotenv
from pyzbar.pyzbar import decode

from statuses.get_info_from_1c import *
from statuses.types_of_statuses import *

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(os.path.dirname(__file__))), "env.env"))

# путь для сохранения изображений
images_path = os.getenv("IMAGES_PATH")

get_qr_info_and_insert(os.getenv("1C_URL"))

def hash_from_barcode(barcode_data: str) -> str:
    """функция для преобразования данных из qr-кода в hash"""

    barcode_bytes = barcode_data.encode('utf-8')
    return hashlib.md5(barcode_bytes).hexdigest()


def process_and_save_barcode_image(image):
    """функция для обработки сохранения qr-кодов"""

    # преобразование изображения в оттенки серого
    gray_img = cv2.cvtColor(image, 0)

    qr_code_objects = [obj for obj in decode(gray_img) if obj.type == 'QRCODE']

    # для каждого распознанного qr-кода
    for obj in qr_code_objects:
        # извлечение координат и создание контура вокруг qr-кода
        points = obj.polygon
        (x, y, w, h) = obj.rect
        pts = np.array(points, np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.polylines(image, [pts], True, (0, 255, 0), 3)

        # извлечение данных и типа qr-кода
        barcode_data = obj.data.decode("utf-8")
        barcode_type = obj.type
        string = "Data " + str(barcode_data) + " | Type " + str(barcode_type)

        # отображение данных и типа qr-кода
        cv2.putText(frame, string, (x, y), cv2.FONT_ITALIC, 0.8, (255, 0, 0), 2)
        print("Barcode: " + barcode_data + " | Type: " + barcode_type)

        # генерация имени файла
        hash = hash_from_barcode(barcode_data)

        file_path = os.path.join(images_path, f"image_{hash}.jpg")
        sql = """UPDATE products SET status = ? WHERE id = ?;"""
        execute(sql, (Statuses.exists_production, hash))

        # сохранение изображения
        cv2.imwrite(file_path, image)


# захват видео с камеры
# в этом случае захват происходит в веб-камеры
cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()
    process_and_save_barcode_image(frame)
    cv2.imshow('Image', frame)
    code = cv2.waitKey(10)
    if code == ord('q'):
        break

cv2.destroyAllWindows()
cap.release()
