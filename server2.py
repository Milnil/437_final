import logging
import io
from PIL import Image
from picamera2 import Picamera2
import cv2
import socket
import select
import queue
import time
import pyaudio  # Import pyaudio for audio capture
import numpy as np  # Import numpy to process audio values
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ObjectDetector:
    def __init__(
        self,
        picam2,
        model_path="efficientdet_lite0.tflite",
        max_results=5,
        score_threshold=0.25,
        detection_confidence_threshold=0.5,
    ):
        self.picam2 = picam2  # Use existing Picamera2 instance
        self.model_path = model_path
        self.max_results = max_results
        self.score_threshold = score_threshold
        self.detection_confidence_threshold = detection_confidence_threshold
        
        self.COUNTER = 0
        self.FPS = 0
        self.START_TIME = time.time()
        self.fps_avg_frame_count = 10
        
        self.detection_result_list = []
        self.detected_objects = set()
        
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.ObjectDetectorOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            max_results=self.max_results,
            score_threshold=self.score_threshold,
            result_callback=self.save_result,
        )
        self.detector = vision.ObjectDetector.create_from_options(options)

    def save_result(self, result: vision.ObjectDetectorResult, unused_output_image: mp.Image, timestamp_ms: int):
        if self.COUNTER % self.fps_avg_frame_count == 0:
            self.FPS = self.fps_avg_frame_count / (time.time() - self.START_TIME)
            self.START_TIME = time.time()

        self.detection_result_list.append(result)
        self.COUNTER += 1

    def detect_objects_from_image(self, image):
        try:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
            self.detector.detect_async(mp_image, time.time_ns() // 1_000_000)
        except Exception as e:
            logging.error(f"Error during object detection: {e}")

    def visualize(self, image, detection_result) -> np.ndarray:
        for detection in detection_result.detections:
            bbox = detection.bounding_box
            start_point = bbox.origin_x, bbox.origin_y
            end_point = bbox.origin_x + bbox.width, bbox.origin_y + bbox.height
            cv2.rectangle(image, start_point, end_point, (255, 0, 255), 3)

            category = detection.categories[0]
            category_name = category.category_name
            probability = round(category.score, 2)
            result_text = category_name + " (" + str(probability) + ")"
            text_location = (bbox.origin_x + 10, bbox.origin_y + 20)
            cv2.putText(
                image, result_text, text_location, cv2.FONT_HERSHEY_DUPLEX, 1, (0, 0, 0), 1, cv2.LINE_AA
            )
        return image

    def close(self):
        logging.info("Closing object detector")
        self.detector.close()

class CameraSystem:
    def __init__(self, host="192.168.10.59", port=65434):
        logging.info("Initializing CameraSystem class")
        self.picam2 = Picamera2()
        self.configure_camera()
        
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        logging.info(f"Server listening on {self.host}:{self.port}")
        
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
        logging.info("Configuring camera")
        video_config = self.picam2.create_still_configuration(main={"size": (320, 240)})
        self.picam2.configure(video_config)
        self.picam2.start()
        logging.info("Camera started")

    def capture_image(self):
        logging.debug("Capturing image")
        try:
            image = self.picam2.capture_array()
            img = Image.fromarray(image)
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            image_bytes = img_byte_arr.getvalue()
            logging.debug(f"Image captured, size: {len(image_bytes)} bytes")
            return image_bytes, image
        except Exception as e:
            logging.error(f"Error capturing image: {e}")
            return None, None

    def capture_audio(self):
        logging.debug("Capturing audio")
        try:
            audio_frames = self.audio_stream.read(1024)
            audio_array = np.frombuffer(audio_frames, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_array**2))
            peak = np.max(np.abs(audio_array))
            logging.debug(f"Audio captured, size: {len(audio_frames)} bytes, RMS: {rms:.2f}, Peak: {peak}")
            return audio_frames
        except Exception as e:
            logging.error(f"Error capturing audio: {e}")
            return None

    def cleanup(self):
        logging.info("Cleaning up resources")
        self.picam2.stop()
        self.object_detector.close()
        self.audio_stream.stop_stream()
        self.audio_stream.close()
        self.audio.terminate()
        logging.info("Cleanup complete")

    def run(self):
        logging.info("Starting server run loop")
        self.server_socket.setblocking(False)
        inputs = [self.server_socket]
        message_queues = {}
        while True:
            audio_bytes = self.capture_audio()
            image_bytes, _ = self.capture_image()

        while inputs:
            try:
                readable, _, _ = select.select(inputs, [], inputs, 0.1)
            except Exception as e:
                logging.error(f"Select error: {e}")
                break
            for s in readable:
                if s is self.server_socket:
                    client_socket, client_address = s.accept()
                    client_socket.setblocking(False)
                    inputs.append(client_socket)
                    message_queues[client_socket] = queue.Queue()
                else:
                    try:
                        data = s.recv(1024).decode().strip()
                        if data == "capture_normal":
                            image_bytes, _ = self.capture_image()
                            if image_bytes:
                                message_queues[s].put(image_bytes)
                            
                        elif data == "capture_with_detection":
                            _, detected_image_bytes = self.capture_and_detect_objects()
                            if detected_image_bytes:
                                message_queues[s].put(detected_image_bytes)
                        elif data == "capture_audio":
                            audio_bytes = self.capture_audio()
                            if audio_bytes:
                                message_queues[s].put(audio_bytes)
                    except Exception as e:
                        logging.error(f"Error handling client data: {e}")
                        inputs.remove(s)
                        s.close()
                        del message_queues[s]
        self.cleanup()

if __name__ == "__main__":
    logging.info("Program is starting...")
    camera_system = CameraSystem()
    try:
        camera_system.run()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt caught, exiting program")
        camera_system.cleanup()
