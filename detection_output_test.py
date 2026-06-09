import argparse
import socket
from pathlib import Path

import cv2
import numpy as np

from vision.detector import GormeEngelliGozu


UDP_IP = "0.0.0.0"
UDP_PORT = 6050
BUFFER_SIZE = 1024 * 1024


def receive_unity_frame(port: int = UDP_PORT, timeout: float = 30.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, port))
    sock.settimeout(timeout)
    print(f"[UNITY TEST] UDP dinleniyor: {UDP_IP}:{port} (max {timeout}s)")

    try:
        data, addr = sock.recvfrom(BUFFER_SIZE)
    except socket.timeout:
        raise RuntimeError("Unity'den gelen veri alınamadı: timeout oldu.")
    finally:
        sock.close()

    jpeg_start = data.find(b"\xff\xd8")
    if jpeg_start == -1:
        raise RuntimeError("UDP paketi içinde JPEG başlığı bulunamadı.")

    meta = data[:jpeg_start].decode("utf-8", errors="ignore").strip()
    jpeg_data = data[jpeg_start:]
    frame = cv2.imdecode(np.frombuffer(jpeg_data, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError("JPEG verisi çözümlenemedi.")

    print(f"[UNITY TEST] Görüntü alındı: {frame.shape[1]}x{frame.shape[0]} px")
    if meta:
        print(f"[UNITY TEST] Meta: {meta}")

    return frame, meta


def draw_detections(frame, detections):
    output = frame.copy()
    for det in detections:
        x1 = int(det.get("x1", 0))
        y1 = int(det.get("y1", 0))
        x2 = int(det.get("x2", 0))
        y2 = int(det.get("y2", 0))
        label = det.get("ad", "bilinmeyen")
        score = det.get("guven", 0.0)
        text = f"{label} {score * 100:.0f}%"

        cv2.rectangle(output, (x1, y1), (x2, y2), (0, 215, 255), 4)
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        cv2.rectangle(
            output,
            (x1, y1 - text_size[1] - 16),
            (x1 + text_size[0] + 12, y1),
            (0, 215, 255),
            cv2.FILLED,
        )
        cv2.putText(
            output,
            text,
            (x1 + 6, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )

    return output


def save_frame_image(frame, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), frame)
    print(f"[UNITY TEST] Çıktı kaydedildi: {output_path}")
    return output_path


def create_dummy_detection_image(output_path: Path | str = None) -> Path:
    if output_path is None:
        output_path = Path(__file__).resolve().parent / "unity_detection_output.png"
    else:
        output_path = Path(output_path)

    width, height = 1280, 720
    frame = np.full((height, width, 3), (38, 50, 56), dtype=np.uint8)
    cv2.rectangle(frame, (0, 0), (width, int(height * 0.55)), (58, 78, 89), cv2.FILLED)
    cv2.rectangle(frame, (0, int(height * 0.55)), (width, height), (79, 93, 102), cv2.FILLED)
    cv2.line(frame, (0, int(height * 0.55)), (width, int(height * 0.55)), (200, 200, 200), 3)
    cv2.putText(frame, "Detection Output", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.putText(frame, "Object Detection Accuracy Analysis", (40, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (220, 220, 220), 2, cv2.LINE_AA)
    save_frame_image(frame, output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Unity'den gelen görüntüyü nesne tespiti ile işleyen test scripti.")
    parser.add_argument("--unity", action="store_true", help="Unity UDP görüntüsünü dinle ve işleme al.")
    parser.add_argument("--port", type=int, default=UDP_PORT, help="UDP portu.")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "unity_detection_output.png", help="Kaydedilecek çıktı dosyası.")
    args = parser.parse_args()

    if args.unity:
        gozu = GormeEngelliGozu()
        frame, meta = receive_unity_frame(port=args.port)
        detections = gozu.nesneleri_tani(frame)
        if not detections:
            print("[UNITY TEST] Nesne tespiti sonucu herhangi bir nesne bulunamadı.")
        else:
            print(f"[UNITY TEST] Tespit edilen nesne sayısı: {len(detections)}")
            for det in detections:
                print(f" - {det['ad']} ({det['guven'] * 100:.0f}%)")

        output_frame = draw_detections(frame, detections)
        save_frame_image(output_frame, args.output)
    else:
        create_dummy_detection_image(args.output)


if __name__ == "__main__":
    main()
