import logging
import io
from PIL import Image
from picamera2 import Picamera2
import cv2
import queue
import time
import pyaudio
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import threading
import asyncio
import websockets

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ObjectDetector:
    def __init__(self, picam2, model_path="efficientdet_lite0.tflite", max_results=5, score_threshold=0.25):
        self.picam2 = picam2
        self.model_path = model_path
        self.max_results = max_results
        self.score_threshold = score_threshold

        base_options = python.BaseOptions(model_asset_path=self.model_path)
        
        options = vision.ObjectDetectorOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            max_results=self.max_results,
            score_threshold=self.score_threshold,
            result_callback=self.save_result  # Provide the result callback
        )
        self.detector = vision.ObjectDetector.create_from_options(options)

    def save_result(self, result: vision.ObjectDetectorResult, unused_output_image: mp.Image, timestamp_ms: int):
        """Callback to handle detection results from the live stream."""
        logging.info(f"Detection result received at {timestamp_ms} ms")
        self.detection_result_list.append(result)

    def detect_objects_from_image(self, image):
        try:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
            self.detector.detect_async(mp_image, time.time_ns() // 1_000_000)
        except Exception as e:
            logging.error(f"Error during object detection: {e}")

    def close(self):
        self.detector.close()


class CameraSystem:
    def __init__(self):
        self.picam2 = Picamera2()
        self.configure_camera()

        self.object_detector = ObjectDetector(self.picam2)
        
        self.audio = pyaudio.PyAudio()
        self.audio_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )

    def configure_camera(self):
        video_config = self.picam2.create_still_configuration(main={"size": (320, 240)})
        self.picam2.configure(video_config)
        self.picam2.start()

    def capture_image(self):
        image = self.picam2.capture_array()
        _, jpeg_image = cv2.imencode('.jpg', image)
        return jpeg_image.tobytes()

    def capture_audio(self):
        audio_frames = self.audio_stream.read(1024)
        return audio_frames

    async def send_video_and_audio(self, websocket):
        try:
            while True:
                image_bytes = self.capture_image()
                await websocket.send(b'\x01' + image_bytes)  # Prefix \x01 to indicate video frame
                
                audio_bytes = self.capture_audio()
                await websocket.send(b'\x02' + audio_bytes)  # Prefix \x02 to indicate audio frame
        except websockets.exceptions.ConnectionClosed:
            logging.info("Client disconnected")
        except Exception as e:
            logging.error(f"Error in send_video_and_audio: {e}")

    async def server(self, websocket, path):
        logging.info(f"WebSocket path received: {path}")

        try:
            await self.send_video_and_audio(websocket)
        except Exception as e:
            logging.error(f"Websocket error: {e}")

    def cleanup(self):
        self.picam2.stop()
        self.object_detector.close()
        self.audio_stream.stop_stream()
        self.audio_stream.close()
        self.audio.terminate()


async def start_server(camera_system):
    async with websockets.serve(camera_system.server, "192.168.10.59", 65434):
        logging.info("WebSocket server running on ws://192.168.10.59:65434")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    logging.info("Starting CameraSystem...")
    camera_system = CameraSystem()
    try:
        asyncio.run(start_server(camera_system))
    except KeyboardInterrupt:
        logging.info("Exiting...")
        camera_system.cleanup()
