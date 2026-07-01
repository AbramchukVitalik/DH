from lidar import start_lidar
from camera import start_camera
import threading

def main():

    stop_event = threading.Event()

    lidar_thread = threading.Thread(
        target=start_lidar,
        args=(stop_event,)
    )

    camera_thread = threading.Thread(
        target=start_camera,
        args=(stop_event,)
    )

    lidar_thread.start()
    camera_thread.start()

    input("Нажмите Enter для остановки...")

    print("Останавливаем все потоки...")
    stop_event.set()

    lidar_thread.join()
    camera_thread.join()

    print("Все завершено.")

if __name__ == "__main__":
    main()
    