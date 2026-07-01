from dotenv import load_dotenv
import os

load_dotenv()

# ------------------------------------------ LIDAR ------------------------------------------ 
LIDAR_IP = os.getenv("LIDAR_IP")
LIDAR_PORT = int(os.getenv("LIDAR_PORT"))

CLIENT_ID = int(os.getenv("CLIENT_ID", 0))

LIM_TAG = int(os.getenv("LIM_TAG"), 0)
LIM_VER = int(os.getenv("LIM_VER"), 0)

LIM_CODE_HB = int(os.getenv("LIM_CODE_HB"))
LIM_CODE_HBACK = int(os.getenv("LIM_CODE_HBACK"))
LIM_CODE_LMD = int(os.getenv("LIM_CODE_LMD"))
LIM_CODE_LMD_RSSI = int(os.getenv("LIM_CODE_LMD_RSSI"))
LIM_CODE_START_LMD = int(os.getenv("LIM_CODE_START_LMD"))
LIM_CODE_STOP_LMD = int(os.getenv("LIM_CODE_STOP_LMD"))

# ------------------------------------------ CAMERA ------------------------------------------ 
RTSP_MAIN = os.getenv("RTSP_MAIN")
RTSP_IR = os.getenv("RTSP_IR")

OUT_MAIN = os.getenv("OUT_MAIN", "main.mp4")
OUT_IR = os.getenv("OUT_IR", "infrared.mp4")
