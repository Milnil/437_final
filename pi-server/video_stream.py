import asyncio
from picamera2 import Picamera2
import io
import numpy as np
from websockets.server import serve
import cv2
import logging
from libcamera import ColorSpace
from video_storage_handler import VideoStorageHandler  # Import the VideoStorageHandler

logger = logging.getLogger(__name__)

class VideoStreamHandler:
    def __init__(self):
        """
        Initializes the VideoStreamHandler with the Picamera2 and video configuration.
        """
        self.picam2 = Picamera2()
        self.config = self.picam2.create_video_configuration(
            main={"size": (640, 480)},
            controls={"FrameDurationLimits": (33333, 33333)},  # ~30fps
            colour_space=ColorSpace.Smpte170m()  # Use Rec.709 color space
        )
        self.picam2.configure(self.config)
        self.picam2.start()

        full_res = self.picam2.camera_properties['PixelArraySize']
        self.picam2.set_controls({"ScalerCrop": [0, 0, full_res[0], full_res[1]]})
        self.clients = set()  # Store all connected clients

    async def capture_and_broadcast(self, storage_handler):
        """
        Continuously captures frames from the camera and sends them to all connected clients.
        Also adds frames to the VideoStorageHandler's frame buffer.
        """
        while True:
            try:
                # Capture a single frame from the camera
                frame = self.picam2.capture_array()

                # Swap red and blue channels for each pixel (RGB to BGR)
                frame[:, :, [0, 2]] = frame[:, :, [2, 0]]

                # Add frame to VideoStorageHandler's buffer for saving video clips
                storage_handler.add_frame(frame)

                # Convert frame to JPEG for WebSocket transmission
                ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                
                if ret:
                    # Send frame to all connected WebSocket clients
                    await asyncio.gather(*(client.send(jpeg.tobytes()) for client in self.clients if not client.closed))
                
                # Limit frame rate to ~30 fps
                await asyncio.sleep(0.033)
            except Exception as e:
                logger.error(f"Error capturing or broadcasting frame: {e}")

    async def handle_client(self, websocket, storage_handler):
        """
        Handles WebSocket client connections and streams video frames to them.
        Simultaneously, frames are added to the VideoStorageHandler's buffer.
        Listens for 'person_detected' message to save the last 4 seconds of video.
        """
        try:
            self.clients.add(websocket)
            logger.info(f"New video client connected. Total clients: {len(self.clients)}")
            
            while True:
                try:
                    # Check for any incoming messages from the client
                    message = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                    if message == "person_detected":
                        logger.info("Received 'person_detected' message from client")
                        # Save the last 4 seconds of video asynchronously
                        await storage_handler.save_video_clip(f"person_detected_{int(asyncio.get_event_loop().time() * 1000)}")
                except asyncio.TimeoutError:
                    pass  # No message received, continue processing frames

        except Exception as e:
            logger.error(f"Error handling WebSocket client: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info(f"Video client disconnected. Total clients: {len(self.clients)}")

    async def start_server(self, storage_handler):
        """
        Starts the WebSocket server to handle video streaming.
        """
        logger.info("Starting video stream server...")
        
        # Launch the frame capture and broadcast task
        broadcast_task = asyncio.create_task(self.capture_and_broadcast(storage_handler))
        
        try:
            async with serve(lambda ws: self.handle_client(ws, storage_handler), "0.0.0.0", 5001):
                logger.info("Video server started on ws://0.0.0.0:5001")
                await asyncio.Future()
        except Exception as e:
            logger.error(f"Error starting WebSocket server: {e}")
        finally:
            broadcast_task.cancel()  # Stop frame capture when server stops
            await broadcast_task
            logger.info("Video stream server has shut down.")

    def cleanup(self):
        """
        Cleans up the resources when the server is stopped.
        """
        self.picam2.stop()
        logger.info("VideoStreamHandler cleaned up.")
