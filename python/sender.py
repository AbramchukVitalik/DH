import socket
import struct
import time

BOARD_IP = "192.168.10.50"  # IP платы
BOARD_PORT = 5005

HEADER = struct.Struct("!HBBIIH")
OBJECT = struct.Struct("!BBffffiH")

MAGIC = 0xAA55
VERSION = 1
MSG_DETECTIONS = 1


def encode_packet(sequence, detections):
    payload = bytearray()

    for obj in detections:
        payload += OBJECT.pack(
            obj["class_id"],
            round(obj["confidence"] * 100),
            obj["x"],
            obj["y"],
            obj["width"],
            obj["height"],
            obj.get("distance_mm", -1),
            obj.get("flags", 0),
        )

    timestamp_ms = int(time.monotonic() * 1000) & 0xFFFFFFFF

    header = HEADER.pack(
        MAGIC,
        VERSION,
        MSG_DETECTIONS,
        sequence,
        timestamp_ms,
        len(payload),
    )

    return header + payload


def main():
    sequence = 0

    # Тестовые данные. Позже подключим результаты YOLO и LiDAR.
    detections = [
        {
            "class_id": 2,
            "confidence": 0.94,
            "x": 0.50,
            "y": 0.45,
            "width": 0.15,
            "height": 0.35,
            "distance_mm": 4200,
            "flags": 1,
        }
    ]

    while True:
        try:
            print(f"Подключение к {BOARD_IP}:{BOARD_PORT}")

            with socket.create_connection(
                (BOARD_IP, BOARD_PORT), timeout=5
            ) as sock:
                sock.settimeout(5)
                print("TCP подключение установлено")

                while True:
                    packet = encode_packet(sequence, detections)
                    sock.sendall(packet)

                    print(
                        f"Отправлен пакет #{sequence}, "
                        f"размер {len(packet)} байт"
                    )

                    sequence = (sequence + 1) & 0xFFFFFFFF
                    time.sleep(0.05)  # 20 Гц

        except (OSError, TimeoutError) as exc:
            print(f"Соединение потеряно: {exc}. Повтор через 2 с")
            time.sleep(2)


if __name__ == "__main__":
    main()
