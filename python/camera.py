import cv2
import threading

# Глобальный флаг остановки
stop_flag = False

# RTSP каналы камеры
RTSP_MAIN = "rtsp://admin:123456abc*@192.168.10.13:554/media/video0"
RTSP_IR   = "rtsp://admin:123456abc*@192.168.10.13:554/media2/video0"

# Выходные файлы
OUT_MAIN = "main.mp4"
OUT_IR   = "infrared.mp4"


def record_stream(rtsp_url, output_file, fps=25):
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

    while not stop_flag:
        ret, frame = cap.read()
        if not ret:
            print(f"Поток пропал: {rtsp_url}")
            continue
        writer.write(frame)

    cap.release()
    writer.release()
    print(f"Файл сохранён: {output_file}")


def start_camera_recording():
    """Запуск записи двух потоков в отдельных потоках"""
    global stop_flag
    stop_flag = False

    t1 = threading.Thread(target=record_stream, args=(RTSP_MAIN, OUT_MAIN), daemon=True)
    t2 = threading.Thread(target=record_stream, args=(RTSP_IR, OUT_IR), daemon=True)

    t1.start()
    t2.start()

    print("Камеры запущены.")

    return t1, t2


def stop_camera_recording():
    """Остановка записи"""
    global stop_flag
    stop_flag = True
    print("Остановка камер...")


if __name__ == "__main__":
    print("Начало записи")
    threads = start_camera_recording()

    print("Нажмите q + Enter для остановки.")
    inp = input()
    if inp.lower() == "q":
        stop_camera_recording()

    for t in threads:
        t.join()

    print("Запись остановлена.")




