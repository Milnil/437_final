import asyncio
from picamera2 import Picamera2
import cv2
import logging
from libcamera import ColorSpace
from websockets.server import serve

logger = logging.getLogger(__name__)

class VideoStreamHandler:
    def __init__(self):
        self.picam2 = Picamera2()
        self.config = self.picam2.create_video_configuration(
            main={"size": (640, 480)},
            controls={"FrameDurationLimits": (33333, 33333)},  
            colour_space=ColorSpace.Smpte170m() 
        )
        self.picam2.configure(self.config)
        self.picam2.start()

        full_res = self.picam2.camera_properties['PixelArraySize']
        self.picam2.set_controls({"ScalerCrop": [0, 0, full_res[0], full_res[1]]})
        self.clients = set()

    async def capture_and_broadcast(self, storage_handler):
        while True:
            try:
                frame = self.picam2.capture_array()
                frame[:, :, [0, 2]] = frame[:, :, [2, 0]]  
                storage_handler.add_frame(frame)  
                
                ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    await asyncio.gather(*(client.send(jpeg.tobytes()) for client in self.clients if not client.closed))
                
                await asyncio.sleep(0.033)  
            except Exception as e:
                logger.error(f"Error capturing or broadcasting frame: {e}")

    async def handle_client(self, websocket, storage_handler):
        self.clients.add(websocket)
        try:
            while True:
                message = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                if message:
                    logger.info("Received 'person_detected' message from client")
                    filename = f"notification_{message}"
                    asyncio.create_task(storage_handler.save_video_clip(filename))
        except Exception as e:
            logger.error(f"Error handling WebSocket client: {e}")
        finally:
            self.clients.remove(websocket)

    async def start_server(self, storage_handler):
        logger.info("Starting video stream server...")
        broadcast_task = asyncio.create_task(self.capture_and_broadcast(storage_handler))
        
        try:
            async with serve(lambda ws: self.handle_client(ws, storage_handler), "0.0.0.0", 5001):
                logger.info("Video server started")
                await asyncio.Future()
        except Exception as e:
            logger.error(f"Error starting WebSocket server: {e}")
        finally:
            broadcast_task.cancel()


    def cleanup(self):
        """
        Cleans up the resources when the server is stopped.
        """
        self.picam2.stop()
        logger.info("VideoStreamHandler cleaned up.")
