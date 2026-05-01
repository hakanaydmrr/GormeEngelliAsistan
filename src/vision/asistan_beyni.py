import socket
import cv2
import numpy as np

# Ayarlar (Unity'dekiyle birebir aynı olmalı)
UDP_IP = "127.0.0.1"
UDP_PORT = 5005

# Soket oluşturma
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"Asistanın zihni hazır! {UDP_PORT} portu dinleniyor...")

while True:
    # Unity'den gelen veriyi al
    data, addr = sock.recvfrom(65535) # Maksimum paket boyutu
    
    if data:
        print("Unity'den bir görüntü paketi ulaştı!")
        # Burada ileride gelen veriyi YOLO'ya sokacağız.