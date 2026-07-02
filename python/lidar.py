import socket
import struct
import time
import threading
import csv
from abc import ABC, abstractmethod

from config import (
    LIDAR_IP,
    LIDAR_PORT,
    CLIENT_ID,
    LIM_TAG,
    LIM_VER,
    LIM_CODE_HB,
    LIM_CODE_HBACK,
    LIM_CODE_LMD,
    LIM_CODE_LMD_RSSI,
    LIM_CODE_START_LMD,
    LIM_CODE_STOP_LMD
)

# ==========================================
# 1. Интерфейсы (Абстракции)
# ==========================================

class ILidar(ABC):
    @abstractmethod
    def start(self) -> None:
        """Запуск лидара и потоков обработки"""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Остановка лидара и корректное закрытие соединений"""
        pass

class IDataHandler(ABC):
    @abstractmethod
    def handle_lmd(self, header_data, lmd_info, distances) -> None:
        """Обработка стандартных пакетов расстояний"""
        pass

    @abstractmethod
    def handle_lmd_rssi(self, header_data, lmd_info, distances, intensities) -> None:
        """Обработка пакетов с дистанцией и интенсивностью (RSSI)"""
        pass

    @abstractmethod
    def close(self) -> None:
        """Закрытие ресурсов (файлов, БД и т.д.)"""
        pass


# ==========================================
# 2. Обработчик данных (CSV)
# ==========================================

class CsvDataHandler(IDataHandler):
    def __init__(self, filename: str = "lidar_raw.csv"):
        self.filename = filename
        self.csv_file = open(self.filename, mode="w", newline="", encoding="utf-8")
        self.csv_writer = csv.writer(self.csv_file)
        self.header_written = False
        self.frame_id = 0

    def _write_header_if_needed(self, cid, n_code, lmd_info, has_rssi=False):
        if not self.header_written:
            nRange, nBAngle, nEAngle, nAnglePrecision, nRPM, nMDataNum = lmd_info
            
            # Базовые заголовки
            meta_header = [
                "ID клиента", "LIM-код", "Макс. дальность (см)", 
                "Нач. угол (мград)", "Кон. угол (мград)", 
                "Шаг угла (мград)", "Скорость (RPM)", "Кол-во точек", "Тип данных"
            ]
            self.csv_writer.writerow(meta_header)
            
            data_type = "Dist + RSSI" if has_rssi else "Dist Only"
            self.csv_writer.writerow([cid, n_code, nRange, nBAngle, nEAngle, nAnglePrecision, nRPM, nMDataNum, data_type])
            self.csv_writer.writerow(["Номер кадра", "Данные ->"])
            
            self.header_written = True

    def handle_lmd(self, header_data, lmd_info, distances):
        cid, n_code = header_data[2], header_data[3]
        self._write_header_if_needed(cid, n_code, lmd_info, has_rssi=False)
        
        self.frame_id += 1
        self.csv_writer.writerow([self.frame_id] + list(distances))

    def handle_lmd_rssi(self, header_data, lmd_info, distances, intensities):
        cid, n_code = header_data[2], header_data[3]
        self._write_header_if_needed(cid, n_code, lmd_info, has_rssi=True)
        
        self.frame_id += 1
        # Чередуем: Дистанция_1, Интенсивность_1, Дистанция_2, Интенсивность_2...
        combined = [val for pair in zip(distances, intensities) for val in pair]
        self.csv_writer.writerow([self.frame_id] + combined)

    def close(self):
        if self.csv_file and not self.csv_file.closed:
            self.csv_file.close()


# ==========================================
# 3. Протокол AkuSense (Хелпер)
# ==========================================

class AkuSenseProtocol:
    @staticmethod
    def calculate_checksum(packet_bytes: bytes) -> int:
        """Вычисляет контрольную сумму LIM через побитовый XOR (^) 32-битных слов."""
        remainder = len(packet_bytes) % 4
        if remainder:
            packet_bytes += b'\x00' * (4 - remainder)

        words_count = len(packet_bytes) // 4
        words = struct.unpack(f"<{words_count}I", packet_bytes)
        
        checksum = 0
        for word in words:
            checksum ^= word 
        return checksum & 0xFFFFFFFF

    @staticmethod
    def pack_lim_head(n_code: int, data_array: list = None, ext_data_len: int = 0) -> bytes:
        """Собирает структуру LIM_HEAD (ровно 40 байт)"""
        if data_array is None:
            data_array = [0, 0, 0, 0]

        total_lim_len = 40 + ext_data_len
        partial_packet = struct.pack(
            "<IIII4II",
            LIM_TAG,
            LIM_VER,
            CLIENT_ID,
            n_code,
            data_array[0], data_array[1], data_array[2], data_array[3],
            total_lim_len
        )
        
        checksum = AkuSenseProtocol.calculate_checksum(partial_packet)
        return partial_packet + struct.pack("<I", checksum)


# ==========================================
# 4. Реализация Лидара
# ==========================================

class AkuSenseTcpLidar(ILidar):
    def __init__(self, ip: str, port: int, data_handler: IDataHandler):
        self.ip = ip
        self.port = port
        self.handler = data_handler
        self.sock = None
        
        self._stop_event = threading.Event()
        self._thr_receive = None
        self._thr_heartbeat = None

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(2.0)
        self._stop_event.clear()

        try:
            print(f"[SYSTEM] Подключение к лидару {self.ip}:{self.port}...")
            self.sock.connect((self.ip, self.port))
            print("[SYSTEM] Успешно подключено к сокету!")
        except Exception as e:
            print(f"[ERROR] Не удалось подключиться к лидару: {e}")
            self.handler.close()
            return

        # Запуск потоков
        self._thr_receive = threading.Thread(target=self._receive_loop, daemon=True)
        self._thr_heartbeat = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thr_receive.start()
        self._thr_heartbeat.start()

        time.sleep(1.5)

        print("[SYSTEM] Отправка команды START_LMD...")
        start_packet = AkuSenseProtocol.pack_lim_head(LIM_CODE_START_LMD)
        self.sock.sendall(start_packet)

    def stop(self):
        if self._stop_event.is_set():
            return
            
        print("[SYSTEM] Остановка лидара и завершение работы...")
        self._stop_event.set()

        if self.sock:
            try:
                print("[SYSTEM] Отправка STOP_LMD...")
                stop_packet = AkuSenseProtocol.pack_lim_head(LIM_CODE_STOP_LMD)
                self.sock.sendall(stop_packet)
            except Exception:
                pass
            
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            
            self.sock.close()

        if self._thr_receive: self._thr_receive.join(timeout=2.0)
        if self._thr_heartbeat: self._thr_heartbeat.join(timeout=2.0)

        self.handler.close()
        print("[SYSTEM] Лидар успешно остановлен.")

    def _heartbeat_loop(self):
        print("[HEARTBEAT] Поток запущен.")
        while not self._stop_event.is_set():
            try:
                hb_packet = AkuSenseProtocol.pack_lim_head(LIM_CODE_HB)
                self.sock.sendall(hb_packet)
                # Ждем 3 секунды, но с возможностью быстрого выхода при stop_event
                self._stop_event.wait(timeout=3.0) 
            except Exception as e:
                if not self._stop_event.is_set():
                    print(f"[HEARTBEAT] Ошибка отправки: {e}")
                break
        print("[HEARTBEAT] Поток остановлен.")

    def _receive_loop(self):
        print("[RECEIVE] Поток приема данных запущен.")
        buffer = b""

        while not self._stop_event.is_set():
            try:
                data = self.sock.recv(65535)
                if not data:
                    print("[RECEIVE] Соединение закрыто устройством.")
                    self._stop_event.set()
                    break
                buffer += data

                while len(buffer) >= 40:
                    n_lim_len = struct.unpack("<I", buffer[32:36])[0]

                    if len(buffer) < n_lim_len:
                        break # Ждем следующую порцию данных

                    packet = buffer[:n_lim_len]
                    buffer = buffer[n_lim_len:]

                    header = struct.unpack("<10I", packet[:40])
                    n_code = header[3]
                    payload = packet[40:]

                    if n_code in (LIM_CODE_LMD, LIM_CODE_LMD_RSSI):
                        self._parse_and_dispatch(header, payload)
                    elif n_code == LIM_CODE_HBACK:
                        pass # Ответ на Heartbeat

            except socket.timeout:
                continue
            except Exception as e:
                if not self._stop_event.is_set():
                    print(f"[RECEIVE] Критическая ошибка при приеме данных: {e}")
                break
                
        print("[RECEIVE] Поток приема остановлен.")

    def _parse_and_dispatch(self, header_data, payload_bytes):
        """Парсинг полезной нагрузки и маршрутизация в обработчик"""
        if len(payload_bytes) < 24:
            return

        lmd_info = struct.unpack("<IiiIII", payload_bytes[:24])
        nMDataNum = lmd_info[5]
        n_code = header_data[3]

        data_bytes = payload_bytes[24:]

        if n_code == LIM_CODE_LMD:
            # Только дистанция (2 байта на точку)
            expected_len = nMDataNum * 2
            if len(data_bytes) >= expected_len:
                distances = struct.unpack(f"<{nMDataNum}H", data_bytes[:expected_len])
                self.handler.handle_lmd(header_data, lmd_info, distances)

        elif n_code == LIM_CODE_LMD_RSSI:
            # ИСПРАВЛЕНИЕ: Дистанция + Интенсивность.
            # По стандарту AkuSense: 2 байта (Dist) + 2 байта (RSSI) = 4 байта на точку
            expected_len = nMDataNum * 4
            if len(data_bytes) >= expected_len:
                # Читаем как массив пар (Dist, RSSI)
                points = struct.unpack(f"<{nMDataNum * 2}H", data_bytes[:expected_len])
                distances = points[0::2]   # Четные индексы
                intensities = points[1::2] # Нечетные индексы
                self.handler.handle_lmd_rssi(header_data, lmd_info, distances, intensities)


# ==========================================
# Точка входа
# ==========================================
def start_lidar(stop_event):
    # 1. Создаем обработчик данных (сохраняет в CSV)
    data_handler = CsvDataHandler("lidar_raw.csv")
    
    # 2. Инициализируем лидар
    lidar = AkuSenseTcpLidar(LIDAR_IP, LIDAR_PORT, data_handler)
    
    # 3. Запускаем (блокирует поток до прерывания)
    lidar.start()

    stop_event.wait()

    lidar.stop()

if __name__ == "__main__":
    start_lidar()
    