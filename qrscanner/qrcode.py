import sys
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import hashlib
import os

sys.path.append("C:/Projects/hack")
import utils

#путь будет меняться в зависимости от машины, тестовый вариант
path = "C:/Projects/hack/qrscanner/images"

#генерация разных названий, чтобы данные о qr кодах поступали своевременно
def generate_filename(barcode_data: str) -> str:
    barcode_bytes = barcode_data.encode('utf-8')

    hash = hashlib.md5(barcode_bytes).hexdigest()

    filename = f"image_{hash}.jpg"

    return filename

#декодинг + сохранение изображения на указанный путь
def decoder(image):
    gray_img = cv2.cvtColor(image, 0)
    barcode = decode(gray_img)

    for obj in barcode:
        points = obj.polygon
        (x, y, w, h) = obj.rect
        pts = np.array(points, np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.polylines(image, [pts], True, (0, 255, 0), 3)

        barcodeData = obj.data.decode("utf-8")
        barcodeType = obj.type
        string = "Data " + str(barcodeData) + " | Type " + str(barcodeType)
        
        cv2.putText(frame, string, (x, y), cv2.FONT_ITALIC, 0.8, (255, 0, 0), 2)
        print("Barcode: " + barcodeData + " | Type: " + barcodeType)
        
        filename = generate_filename(barcodeData)
        # Сохранение изображения
        os.chdir(path) 
        cv2.imwrite(filename, image)

#захват видео с камеры (конкретно тут с вебки)
cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()
    decoder(frame)
    cv2.imshow('Image', frame)
    code = cv2.waitKey(10)
    if code == ord('q'):
        break

cv2.destroyAllWindows()
cap.release()
