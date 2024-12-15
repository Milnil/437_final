import asyncio
from picamera2 import Picamera2
import io
import numpy as np
from websockets.server import serve
import cv2  # Add cv2 for image conversion
import logging
from libcamera import ColorSpace
import collections  # For deque to store video frames
import time  # For timestamping video clips
import imageio  # Use imageio for video writing

logger = logging.getLogger(__name__)

class VideoStreamHandler:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.picam2 = Picamera2()
        self.config = self.picam2.create_video_configuration(
            main={"size": (640, 480)},
            controls={
                "FrameDurationLimits": (33333, 33333)
            },  # ~30fps
            colour_space=ColorSpace.Smpte170m()  # Use Rec.709 color space
        )
        self.picam2.configure(self.config)
        self.picam2.start()
        full_res = self.picam2.camera_properties['PixelArraySize']
        self.picam2.set_controls({"ScalerCrop": [0, 0, full_res[0], full_res[1]]})
        self.clients = set()
        self.frame_buffer = collections.deque(maxlen=120)  # Stores 4 seconds of video at 30fps (4 * 30 = 120 frames)

    async def handle_client(self, websocket):
        try:
            self.clients.add(websocket)
            logger.info("New video client connected")
            while True:
                # Capture frame and convert to JPEG using cv2
                frame = self.picam2.capture_array()
                frame2 = frame.copy()
                frame[:, :, [0, 2]] = frame[:, :, [2, 0]]
                
                
                ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    await websocket.send(jpeg.tobytes())

                asyncio.create_task(self.add_frame_to_buffer(frame2))
                await asyncio.sleep(0.033)  # ~30fps
        except Exception as e:
            logger.error(f"Video client error: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info("Video client disconnected")

    async def add_frame_to_buffer(self, frame):
        """Asynchronously add frame to the frame buffer."""
        self.frame_buffer.append(frame)

    async def save_last_4_seconds(self, output_path='last_4_seconds.mp4'):
        async with self.lock:
            if not self.frame_buffer:
                logger.warning("No frames available in the buffer to save.")
                return

            logger.info(f"Starting to save the last 4 seconds of video to {output_path}.")
            try:
                with imageio.get_writer(output_path, fps=30, codec='libx264') as writer:
                    for frame in list(self.frame_buffer):  # Convert deque to list to avoid issues during iteration
                        writer.append_data(frame)

                logger.info(f"Successfully saved video with {len(self.frame_buffer)} frames.")
            except Exception as e:
                logger.error(f"Error saving video: {e}")



    async def start_server(self):
        async with serve(self.handle_client, "0.0.0.0", 5001):
            logger.info("Video server started on ws://0.0.0.0:5001")
            await asyncio.Future()

    def cleanup(self):
        self.picam2.stop()
