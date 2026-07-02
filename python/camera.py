import cv2
import threading
from abc import ABC, abstractmethod

from config import (
    RTSP_MAIN,
    RTSP_IR,
    OUT_MAIN,
    OUT_IR,
)

# =========================
# Интерфейс камеры
# =========================
class ICamera(ABC):
    @abstractmethod
    def open(self):
        pass

    @abstractmethod
    def read(self):
        pass

    @abstractmethod
    def release(self):
        pass


# =========================
# RTSP камера (реализация)
# =========================
class RTSPCamera(ICamera):
    def __init__(self, url: str):
        self.url = url
        self.cap = None

    def open(self):
        self.cap = cv2.VideoCapture(self.url)
        return self.cap.isOpened()

    def read(self):
        if self.cap is None:
            return False, None
        return self.cap.read()

    def release(self):
        if self.cap:
            self.cap.release()
            self.cap = None


# =========================
# Класс записи потока
# =========================
class StreamRecorder:
    def __init__(self, camera: ICamera, output_file: str, fps: int = 25):
        self.camera = camera
        self.output_file = output_file
        self.fps = fps

        self.stop_event = threading.Event()
        self.thread = None

        self.writer = None

    def start(self):
        self.thread = threading.Thread(target=self._record, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join()

    def _record(self):
        if not self.camera.open():
            print("Не удалось открыть камеру")
            return

        ret, frame = self.camera.read()
        if not ret:
            print("Не удалось получить кадр")
            return

        h, w = frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(self.output_file, fourcc, self.fps, (w, h))

        print(f"Запись началась: {self.output_file}")

        while not self.stop_event.is_set():
            ret, frame = self.camera.read()
            if not ret:
                print("Поток пропал")
                continue

            self.writer.write(frame)

        self._cleanup()

    def _cleanup(self):
        if self.writer:
            self.writer.release()
        self.camera.release()
        print(f"Файл сохранён: {self.output_file}")


# =========================
# Менеджер камер
# =========================
class CameraManager:
    def __init__(self):
        self.recorders = []
        self._running = False

    def add_recorder(self, recorder):
        self.recorders.append(recorder)

    def start(self):
        print("Запуск всех камер...")
        self._running = True

        for r in self.recorders:
            r.start()

    def stop(self):
        print("Остановка всех камер...")
        self._running = False

        for r in self.recorders:
            r.stop()


def start_camera(stop_event):
    manager = CameraManager()

    cameras = [
        (RTSP_MAIN, OUT_MAIN),
        (RTSP_IR, OUT_IR),
    ]

    for url, out in cameras:
        cam = RTSPCamera(url)
        rec = StreamRecorder(cam, out)
        manager.add_recorder(rec)

    manager.start()

    # нормальное ожидание остановки
    stop_event.wait()

    manager.stop()
   
   
if __name__ == "__main__":
    start_camera()
