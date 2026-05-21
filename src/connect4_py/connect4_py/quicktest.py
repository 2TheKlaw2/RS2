import pyrealsense2 as rs
import time

pipe = rs.pipeline()
cfg = rs.config()
cfg.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

print("Starting 'Hammer' Test. Attempting to wake up the sensor...")
try:
    pipe.start(cfg)
    for i in range(1, 11):
        print(f"Attempt {i}: Waiting for frame...")
        success, frames = pipe.try_wait_for_frames(2000) # 2-second bursts
        if success:
            print("--- SUCCESS! Data is flowing! ---")
            break
        time.sleep(1)
    pipe.stop()
except Exception as e:
    print(f"CRITICAL ERROR: {e}")