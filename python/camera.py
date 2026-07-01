import cv2
import threading

from config import (
    RTSP_MAIN,
    RTSP_IR,
    OUT_MAIN,
    OUT_IR,
)

def record_stream(rtsp_url, output_file, stop_event, fps=25):
    """Функция записи одного RTSP-потока"""
    global stop_flag

    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        print(f"Не удалось открыть поток: {rtsp_url}")
        return

    ret, frame = cap.read()
    if not ret:
        print(f"Не удалось получить кадр из: {rtsp_url}")
        return

    height, width = frame.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_file, fourcc, fps, (width, height))

    print(f"Запись началась: {output_file}")

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            print(f"Поток пропал: {rtsp_url}")
            continue
        writer.write(frame)

    cap.release()
    writer.release()
    print(f"Файл сохранён: {output_file}")

def start_camera_recording(stop_event):
    """Запуск записи двух потоков в отдельных потоках"""
    global stop_flag
    stop_flag = False

    t1 = threading.Thread(
        target=record_stream,
        args=(RTSP_MAIN, OUT_MAIN, stop_event),
        daemon=True
    )

    t2 = threading.Thread(
        target=record_stream,
        args=(RTSP_IR, OUT_IR, stop_event),
        daemon=True
    )

    t1.start()
    t2.start()

    print("Камеры запущены.")

    return t1, t2

def stop_camera_recording():
    """Остановка записи"""
    global stop_flag
    stop_flag = True
    print("Остановка камер...")

def start_camera(stop_event):
    print("Начало записи")

    threads = start_camera_recording(stop_event)

    for t in threads:
        t.join()

    print("Запись остановлена.")

if __name__ == "__main__":
    start_camera()
