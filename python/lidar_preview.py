import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.animation import FFMpegWriter
import csv
import mplcursors

# ==========================
# Параметры файла
# ==========================
FILE = "lidar_raw.csv"

# ==========================
# Чтение файла
# ==========================
frames = []

ZOOM = 6   # < 1 = приближение, > 1 = отдаление

with open(FILE, newline='', encoding='utf-8') as f:
    reader = csv.reader(f)

    # пропускаем первые три строки
    next(reader)
    params = next(reader)
    next(reader)

    angle_start = float(params[3]) / 1000.0
    angle_end = float(params[4]) / 1000.0
    angle_step = float(params[5]) / 1000.0

    angles = np.arange(angle_start, angle_end + angle_step, angle_step)

    for row in reader:
        if len(row) < 2:
            continue

        distances = np.array(row[1:], dtype=float)

        if len(distances) != len(angles):
            continue

        frames.append(distances)

print(f"Кадров: {len(frames)}")
print(f"Точек в кадре: {len(angles)}")

# ==========================
# Настройка графика
# ==========================
fig = plt.figure(figsize=(8,8))
ax = plt.subplot(111)

ax.set_aspect('equal')
ax.set_xlim(-2200,2200)
ax.set_ylim(-2200,2200)

ax.grid(True)

scatter = ax.scatter([], [], s=8, color="royalblue")

# Подсветка выбранной точки
highlight = ax.scatter(
    [], [],
    s=160,
    color="yellow",
    edgecolors="black",
    linewidths=2,
    zorder=20
)

# Лидар (центр координат)
lidar = ax.scatter(
    [0], [0],
    s=180,          # размер точки
    c='red',        # цвет
    edgecolors='black',
    linewidths=2,
    zorder=10,
    label='LiDAR'
)

ax.legend(loc="upper right")

title = ax.set_title("")

info = ax.text(
    0.02,
    0.98,
    "",
    transform=ax.transAxes,
    va="top",
    fontsize=11,
    bbox=dict(facecolor="white", alpha=0.8)
)

current_x = np.array([])
current_y = np.array([])
current_dist = np.array([])

# ==========================
# Обновление кадра
# ==========================
def update(i):

    global current_x, current_y, current_dist

    dist = frames[i]

    rad = np.deg2rad(angles)

    x = dist * np.cos(rad) * ZOOM
    y = dist * np.sin(rad) * ZOOM

    current_x = x
    current_y = y
    current_dist = dist

    scatter.set_offsets(np.column_stack((x, y)))

    title.set_text(f"Frame {i+1}/{len(frames)}")

    return scatter, lidar, title, highlight

ani = FuncAnimation(
    fig,
    update,
    frames=len(frames),
    interval=40,
    blit=False,
    repeat=True
)

SAVE_VIDEO = True       # False — только просмотр
VIDEO_NAME = "lidar_animation.mp4"

if SAVE_VIDEO:
    print("Сохранение видео...")

    writer = FFMpegWriter(
        fps=25,
        metadata={"artist": "ChatGPT"},
        bitrate=4000
    )

    ani.save(VIDEO_NAME, writer=writer)

    print(f"Видео сохранено: {VIDEO_NAME}")

def on_move(event):

    if event.inaxes != ax:
        return

    if len(current_x) == 0:
        return

    mx = event.xdata
    my = event.ydata

    d = np.hypot(current_x - mx, current_y - my)

    idx = np.argmin(d)

    # Максимальное расстояние курсора до точки
    if d[idx] > 50:
        highlight.set_offsets(np.empty((0, 2)))
        info.set_text("")
        fig.canvas.draw_idle()
        return

    highlight.set_offsets([[current_x[idx], current_y[idx]]])

    info.set_text(
        f"X: {current_x[idx]:7.1f} см\n"
        f"Y: {current_y[idx]:7.1f} см\n"
        f"Угол: {angles[idx]:6.1f}°\n"
        f"Расстояние: {current_dist[idx]:7.1f} см\n"
        f"{current_dist[idx]/100:.2f} м"
    )

    fig.canvas.draw_idle()

fig.canvas.mpl_connect("motion_notify_event", on_move)

plt.show()
