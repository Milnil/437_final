# pi-server/video_stream.py
import asyncio
from picamera2 import Picamera2
import io
import numpy as np
from websockets.server import serve

class VideoStreamHandler:
    def __init__(self):
        self.picam2 = Picamera2()
        self.config = self.picam2.create_video_configuration(
            main={"size": (640, 480)},
            controls={"FrameDurationLimits": (33333, 33333)}  # ~30fps
        )
        self.picam2.configure(self.config)
        self.picam2.start()
        self.clients = set()

    async def handle_client(self, websocket):
        try:
            self.clients.add(websocket)
            while True:
                frame = self.picam2.capture_array()
                # Convert to bytes
                frame_bytes = frame.tobytes()
                await websocket.send(frame_bytes)
                await asyncio.sleep(0.033)  # ~30fps
        except Exception as e:
            print(f"Video client error: {e}")
        finally:
            self.clients.remove(websocket)

    async def start_server(self):
        async with serve(self.handle_client, "0.0.0.0", 500):
            await asyncio.Future()  # run forever

    def cleanup(self):
        self.picam2.stop()