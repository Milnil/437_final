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
                frame[:, :, [0, 2]] = frame[:, :, [2, 0]]
                self.frame_buffer.append(frame)  # Store the frame in the buffer
                
                ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    await websocket.send(jpeg.tobytes())
                await asyncio.sleep(0.033)  # ~30fps
        except Exception as e:
            logger.error(f"Video client error: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info("Video client disconnected")

    async def save_last_4_seconds(self, output_path='last_4_seconds.mp4'):
        async with self.lock:
            if not self.frame_buffer:
                logger.warning("No frames available in the buffer to save.")
                return

            logger.info(f"Starting to save the last 4 seconds of video to {output_path}.")
            try:
                height, width, layers = self.frame_buffer[0].shape
                logger.info(f"Video frame size: {width}x{height} with {layers} color channels.")
                
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                video_writer = cv2.VideoWriter(output_path, fourcc, 30, (width, height))
                
                frame_count = 0
                for frame in list(self.frame_buffer):
                    if frame.shape != (height, width, layers):
                        logger.warning(f"Frame size mismatch: got {frame.shape}, expected {(height, width, layers)}. Resizing frame.")
                        frame = cv2.resize(frame, (width, height))
                    video_writer.write(frame)


                logger.info(f"Successfully saved {frame_count} frames to {output_path}.")
            except Exception as e:
                logger.error(f"Error while saving the video: {e}")
            finally:
                if 'video_writer' in locals() and video_writer.isOpened():
                    video_writer.release()
                logger.info(f"Finished saving video to {output_path}.")



    async def start_server(self):
        async with serve(self.handle_client, "0.0.0.0", 5001):
            logger.info("Video server started on ws://0.0.0.0:5001")
            await asyncio.Future()

    def cleanup(self):
        self.picam2.stop()
