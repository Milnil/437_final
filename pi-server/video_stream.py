# pi-server/video_stream.py
import asyncio
from picamera2 import Picamera2
import io
import numpy as np
from websockets.server import serve
from PIL import Image
import logging

logger = logging.getLogger(__name__)

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
            logger.info("New video client connected")
            while True:
                # Capture frame and convert to JPEG
                frame = self.picam2.capture_array()
                # Convert numpy array to PIL Image
                img = Image.fromarray(frame)
                # Convert to JPEG bytes
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG', quality=85)
                await websocket.send(img_byte_arr.getvalue())
                await asyncio.sleep(0.033)  # ~30fps
        except Exception as e:
            logger.error(f"Video client error: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info("Video client disconnected")

    async def start_server(self):
        async with serve(self.handle_client, "0.0.0.0", 5001):  # Changed port to 5001
            logger.info("Video server started on ws://0.0.0.0:5001")
            await asyncio.Future()

    def cleanup(self):
        self.picam2.stop()