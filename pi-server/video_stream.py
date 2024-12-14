# pi-server/video_stream.py
import asyncio
from picamera2 import Picamera2
import io
import numpy as np
from websockets.server import serve
import cv2  # Add cv2 for image conversion
import logging
from libcamera import ColorSpace

logger = logging.getLogger(__name__)

class VideoStreamHandler:
    def __init__(self):
        self.picam2 = Picamera2()
        self.config = self.picam2.create_video_configuration(
            main={"size": (640, 480)},
            controls={"FrameDurationLimits": (33333, 33333),
                      "AwbMode" : 0
            },  # ~30fps
        colour_space=ColorSpace.Rec709()  # Use Rec.709 color space
        )
        self.picam2.configure(self.config)
        self.picam2.start()
        full_res = self.picam2.camera_properties['PixelArraySize']
        self.picam2.set_controls({"ScalerCrop": [0, 0, full_res[0], full_res[1]]})
        self.clients = set()

    async def handle_client(self, websocket):
        try:
            self.clients.add(websocket)
            logger.info("New video client connected")
            while True:
                # Capture frame and convert to JPEG using cv2
                frame = self.picam2.capture_array()
                ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    await websocket.send(jpeg.tobytes())
                await asyncio.sleep(0.033)  # ~30fps
        except Exception as e:
            logger.error(f"Video client error: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info("Video client disconnected")

    async def start_server(self):
        async with serve(self.handle_client, "0.0.0.0", 5001):
            logger.info("Video server started on ws://0.0.0.0:5001")
            await asyncio.Future()

    def cleanup(self):
        self.picam2.stop()