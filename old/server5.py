import logging
import io
from PIL import Image
from picamera2 import Picamera2
import cv2
import socket
import queue
import time
import pyaudio
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import threading
import json
import struct
from http.server import HTTPServer, SimpleHTTPRequestHandler

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
    def __init__(self, host="192.168.10.59", video_port=65434):
        self.host = host
        self.video_port = video_port
        
        # Initialize components
        self.picam2 = Picamera2()
        self.configure_camera()
        self.object_detector = ObjectDetector(self.picam2)
        
        # Initialize audio
        self.audio = pyaudio.PyAudio()
        self.audio_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )
        
        # Create queues for thread communication
        self.video_queue = queue.Queue(maxsize=10)
        self.audio_queue = queue.Queue(maxsize=10)
        
        # Threading control
        self.running = True
        
        # Initialize server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.video_port))
        self.server_socket.listen(5)
        logging.info(f"Server listening on {self.host}:{self.video_port}")
        
        # Add a clients set to track active connections
        self.clients = set()
        self.clients_lock = threading.Lock()
        
        # Add HTTP server for serving the webpage
        self.http_server = HTTPServer((host, 8000), SimpleHTTPRequestHandler)
        logging.info(f"HTTP server started at http://{host}:8000")

    def configure_camera(self):
        video_config = self.picam2.create_still_configuration(main={"size": (320, 240)})
        self.picam2.configure(video_config)
        self.picam2.start()

    def capture_video_thread(self):
        while self.running:
            try:
                image = self.picam2.capture_array()
                _, jpeg_image = cv2.imencode('.jpg', image)
                frame_data = jpeg_image.tobytes()
                
                if not self.video_queue.full():
                    self.video_queue.put(frame_data)
                
                time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                logging.error(f"Error in video capture: {e}")

    def capture_audio_thread(self):
        while self.running:
            try:
                audio_data = self.audio_stream.read(1024)
                if not self.audio_queue.full():
                    self.audio_queue.put(audio_data)
            except Exception as e:
                logging.error(f"Error in audio capture: {e}")

    def client_handler(self, client_socket, addr):
        logging.info(f"New connection from {addr}")
        
        # Add client to active clients
        with self.clients_lock:
            self.clients.add(client_socket)
            
        try:
            while self.running:
                try:
                    # Send video frame
                    if not self.video_queue.empty():
                        frame_data = self.video_queue.get()
                        # Send frame size first, then frame data
                        size_data = struct.pack('!I', len(frame_data))
                        client_socket.sendall(size_data + frame_data)
                    
                    # Send audio data
                    if not self.audio_queue.empty():
                        audio_data = self.audio_queue.get()
                        # Send audio size first, then audio data
                        size_data = struct.pack('!I', len(audio_data))
                        client_socket.sendall(size_data + audio_data)
                    
                    # Add a small sleep to prevent CPU overload
                    time.sleep(0.001)
                    
                except socket.error as e:
                    if isinstance(e, BrokenPipeError) or isinstance(e, ConnectionResetError):
                        logging.info(f"Client {addr} disconnected")
                        break
                    logging.error(f"Socket error with client {addr}: {e}")
                    break
                    
        except Exception as e:
            logging.error(f"Error handling client {addr}: {e}")
        finally:
            # Remove client from active clients
            with self.clients_lock:
                self.clients.remove(client_socket)
                client_socket.close()
            logging.info(f"Connection closed for {addr}")

    def start(self):
        # Start HTTP server in a separate thread
        http_thread = threading.Thread(target=self.http_server.serve_forever)
        http_thread.daemon = True
        http_thread.start()
        
        # Start capture threads
        self.video_thread = threading.Thread(target=self.capture_video_thread)
        self.audio_thread = threading.Thread(target=self.capture_audio_thread)
        
        self.video_thread.start()
        self.audio_thread.start()
        
        # Accept client connections
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                # Set TCP keepalive
                client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                # Set socket timeout
                client_socket.settimeout(10.0)
                
                client_thread = threading.Thread(
                    target=self.client_handler,
                    args=(client_socket, addr)
                )
                client_thread.daemon = True  # Make thread daemon so it closes with main program
                client_thread.start()
            except Exception as e:
                logging.error(f"Error accepting connection: {e}")

    def cleanup(self):
        self.running = False
        # Close all client connections
        with self.clients_lock:
            for client_socket in self.clients:
                try:
                    client_socket.close()
                except:
                    pass
            self.clients.clear()
        
        self.picam2.stop()
        self.object_detector.close()
        self.audio_stream.stop_stream()
        self.audio_stream.close()
        self.audio.terminate()
        self.server_socket.close()
        self.http_server.shutdown()

if __name__ == "__main__":
    camera_system = CameraSystem()
    try:
        camera_system.start()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        camera_system.cleanup()
