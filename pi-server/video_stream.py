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

    async def handle_client(self, websocket, storage_handler):
        """
        Handles WebSocket client connections and streams video frames to them.
        Simultaneously, frames are added to the VideoStorageHandler's buffer.
        Listens for 'person_detected' message to save the last 4 seconds of video.
        """
        try:
            self.clients.add(websocket)
            logger.info("New video client connected")
            while True:
                # Check for any incoming messages from the client
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                    if message == "person_detected":
                        logger.info("Received 'person_detected' message from client")
                        storage_handler.save_video_clip('person_detected')
                except asyncio.TimeoutError:
                    pass  # No message received, continue processing frames
                
                # Capture frame from the camera
                frame = self.picam2.capture_array()

                # Swap red and blue channels for each pixel
                frame[:, :, [0, 2]] = frame[:, :, [2, 0]]

                # Add frame to VideoStorageHandler's buffer for saving video clips
                storage_handler.add_frame(frame)

                # Convert frame to JPEG to send over the WebSocket
                ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    await websocket.send(jpeg.tobytes())

                await asyncio.sleep(0.033)  # ~30fps
        except Exception as e:
            logger.error(f"Video client error: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info("Video client disconnected")

    async def start_server(self, storage_handler):
        """
        Starts the WebSocket server to handle video streaming.
        """
        async with serve(lambda websocket: self.handle_client(websocket, storage_handler), "0.0.0.0", 5001):
            logger.info("Video server started on ws://0.0.0.0:5001")
            await asyncio.Future()

    def cleanup(self):
        """
        Cleans up the resources when the server is stopped.
        """
        self.picam2.stop()
