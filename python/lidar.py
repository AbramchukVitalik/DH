import socket
import struct
import time
import threading
import csv

# --- НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ---
LIDAR_IP = "192.168.10.82"
LIDAR_PORT = 2112  # Фиксированный TCP-порт из мануала [cite: 215]
CLIENT_ID = 0

# --- КОДЫ КОМАНД LIM [cite: 158] ---
LIM_TAG = 0xF5EC96A5
LIM_VER = 0x01000000

LIM_CODE_HB = 10
LIM_CODE_HBACK = 11
LIM_CODE_LMD = 901
LIM_CODE_LMD_RSSI = 911
LIM_CODE_START_LMD = 1900
LIM_CODE_STOP_LMD = 1902

is_running = True
header_written = False
frame_id = 0

csv_file = open("lidar_raw.csv", mode="w", newline="", encoding="utf-8")
csv_writer = csv.writer(csv_file)


def calculate_checksum(packet_bytes_without_checksum):
    """
    Вычисляет контрольную сумму LIM через побитовый XOR (^) 32-битных слов.
    Это стандартный метод для протокола LIM AkuSense, если библиотека не используется.
    """
    remainder = len(packet_bytes_without_checksum) % 4
    if remainder:
        packet_bytes_without_checksum += b'\x00' * (4 - remainder)

    words_count = len(packet_bytes_without_checksum) // 4
    words = struct.unpack(f"<{words_count}I", packet_bytes_without_checksum)
    
    checksum = 0
    for word in words:
        checksum ^= word 
    return checksum & 0xFFFFFFFF


def pack_lim_head(n_code, data_array=[0, 0, 0, 0], ext_data_len=0):
    """Собирает структуру LIM_HEAD (ровно 40 байт) [cite: 147, 150]"""
    total_lim_len = 40 + ext_data_len

    # Заголовок без контрольной суммы (9 полей по 4 байта = 36 байт) 
    partial_packet = struct.pack(
        "<IIII4II",
        LIM_TAG,
        LIM_VER,
        CLIENT_ID,
        n_code,
        data_array[0], data_array[1], data_array[2], data_array[3],
        total_lim_len
    )
    
    checksum = calculate_checksum(partial_packet)
    full_packet = partial_packet + struct.pack("<I", checksum)
    return full_packet


def heartbeat_thread(sock):
    """Отправка Heartbeat каждые 3 секунды (строго < 5 секунд по мануалу) [cite: 216]"""
    global is_running
    print("[HEARTBEAT] Поток запущен.")
    while is_running:
        try:
            hb_packet = pack_lim_head(LIM_CODE_HB)
            sock.sendall(hb_packet)
            time.sleep(3.0) 
        except Exception as e:
            if is_running:
                print(f"[HEARTBEAT] Ошибка отправки: {e}")
            break
    print("[HEARTBEAT] Поток остановлен.")


def parse_and_save_data(header_data, payload_bytes): 
    """Парсит LMD_INFO и массив точек """
    global header_written, frame_id

    if len(payload_bytes) < 24:
        return

    # Распаковываем LMD_INFO (24 байта) 
    lmd_info = struct.unpack("<IiiIII", payload_bytes[:24])
    nRange, nBAngle, nEAngle, nAnglePrecision, nRPM, nMDataNum = lmd_info
    
    cid, n_code = header_data[2], header_data[3]

    if not header_written:
        csv_writer.writerow([
            "ID клиента", "LIM-код", "Максимальная дальность (см)", 
            "Начальный угол (мград)", "Конечный угол (мград)", 
            "Шаг угла (мград)", "Скорость вращения (RPM)", "Количество точек"
        ])
        csv_writer.writerow([cid, n_code, nRange, nBAngle, nEAngle, nAnglePrecision, nRPM, nMDataNum])
        csv_writer.writerow(["Номер кадра / Данные расстояний (см) ->"])
        header_written = True

    # Данные расстояний (LMD_D_Type, unsigned short, 2 байта на точку) 
    distance_bytes = payload_bytes[24 : 24 + (nMDataNum * 2)]
    
    if len(distance_bytes) == nMDataNum * 2:
        distances = struct.unpack(f"<{nMDataNum}H", distance_bytes)
        frame_id += 1
        csv_writer.writerow([frame_id] + list(distances))


def receive_thread(sock): #НЕОБХОДИМО ИСПРАВЛЕНИЕ RSSI ПАКЕТОВ КОД 911 LIM_CODE_LMD_RSSI - РАСТОЯНИЯ И ИНТЕНСИВНОСТЬ
    """Поток непрерывного чтения сокета с защитой от таймаутов"""
    global is_running
    print("[RECEIVE] Поток приема данных запущен.")

    buffer = b""

    while is_running:
        try:
            data = sock.recv(65535)
            if not data:
                print("[RECEIVE] Соединение закрыто устройством.")
                break
            buffer += data

            while len(buffer) >= 40:
                n_lim_len = struct.unpack("<I", buffer[32:36])[0]

                if len(buffer) < n_lim_len:
                    break

                packet = buffer[:n_lim_len]
                buffer = buffer[n_lim_len:]

                header = struct.unpack("<10I", packet[:40])
                n_code = header[3]

                if n_code in (LIM_CODE_LMD, LIM_CODE_LMD_RSSI):
                    if(n_code == LIM_CODE_LMD_RSSI):
                        print("LIM_CODE_LMD_RSSI Пакет")
                    payload = packet[40:]
                    parse_and_save_data(header, payload)
                elif n_code == LIM_CODE_HBACK:
                    # Лидар отвечает на наш Heartbeat 
                    pass

        except socket.timeout:
            # Если сработал таймаут сокета, просто игнорируем его и идем на следующий круг чтения.
            # Это предотвратит падение потока, если лидар задержал отправку кадра.
            continue
        except Exception as e:
            if is_running:
                print(f"[RECEIVE] Критическая ошибка при приеме данных: {e}")
            break
    print("[RECEIVE] Поток приема остановлен.")


def main():
    global is_running

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)  # Ставим таймаут поменьше, чтобы сокет оставался отзывчивым

    try:
        print(f"Подключение к лидару {LIDAR_IP}:{LIDAR_PORT}...")
        sock.connect((LIDAR_IP, LIDAR_PORT))
        print("Успешно подключено к сокету!")
    except Exception as e:
        print(f"Не удалось подключиться к лидару: {e}")
        csv_file.close()
        return

    thr_receive = threading.Thread(target=receive_thread, args=(sock,))
    thr_heartbeat = threading.Thread(target=heartbeat_thread, args=(sock,))
    thr_receive.start()
    thr_heartbeat.start()

    time.sleep(1.5)

    # Отправка корректной команды СТАРТ с XOR-чексуммой 
    print("Отправка команды START_LMD...")
    start_packet = pack_lim_head(LIM_CODE_START_LMD, data_array=[0, 0, 0, 0])
    sock.sendall(start_packet)

    input("\nНажмите ENTER для остановки сбора данных и завершения программы...\n")

    print("Отправка команды STOP_LMD...")
    stop_packet = pack_lim_head(LIM_CODE_STOP_LMD, data_array=[0, 0, 0, 0])
    try:
        sock.sendall(stop_packet)
    except Exception as e:
        print(f"Не удалось отправить команду STOP: {e}")

    is_running = False
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except:
        pass
    sock.close() 

    thr_receive.join()
    thr_heartbeat.join()

    csv_file.close()
    print("Программа успешно завершена. Данные сохранены.")


if __name__ == "__main__":
    main()