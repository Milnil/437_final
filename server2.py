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
from http.server import HTTPServer, BaseHTTPRequestHandler
import os


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MJPEGHandler(BaseHTTPRequestHandler):
    """
    A handler that serves a continuous MJPEG stream from the camera.
    """
    def do_GET(self):
        if self.path == '/video':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()

            # Continuously capture frames and send them as a multipart MJPEG stream
            while True:
                if not self.server.running:
                    break
                frame = self.server.get_frame()
                if frame is not None:
                    self.wfile.write(b"--frame\r\n")
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', str(len(frame)))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                time.sleep(0.033)  # ~30fps
        else:
            # Serve files from the current directory
            if self.path == '/':
                self.path = '/index.html'
            file_path = '.' + self.path
            if os.path.isfile(file_path):
                self.send_response(200)
                if file_path.endswith('.html'):
                    self.send_header('Content-type', 'text/html')
                elif file_path.endswith('.js'):
                    self.send_header('Content-type', 'application/javascript')
                elif file_path.endswith('.css'):
                    self.send_header('Content-type', 'text/css')
                else:
                    self.send_header('Content-type', 'application/octet-stream')
                self.end_headers()

                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File not found.")


class ObjectDetector:
    def __init__(self, picam2, model_path="efficientdet_lite0.tflite", max_results=5, score_threshold=0.25):
        self.picam2 = picam2
        self.model_path = model_path
        self.max_results = max_results
        self.score_threshold = score_threshold
        self.detection_result_list = []  # Added to store results

        base_options = python.BaseOptions(model_asset_path=self.model_path)
        
        options = vision.ObjectDetectorOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            max_results=self.max_results,
            score_threshold=self.score_threshold,
            result_callback=self.save_result
        )
        self.detector = vision.ObjectDetector.create_from_options(options)

    def save_result(self, result: vision.ObjectDetectorResult, unused_output_image: mp.Image, timestamp_ms: int):
        """Callback to handle detection results."""
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

class CameraServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.picam2 = Picamera2()
        self.configure_camera()
        self.running = True
        self.frame = None
        self.lock = threading.Lock()

        self.capture_thread = threading.Thread(target=self.capture_frames)
        self.capture_thread.start()

    def configure_camera(self):
        # Low resolution example, you can adjust as needed
        config = self.picam2.create_still_configuration(main={"size": (320, 240)})
        self.picam2.configure(config)
        self.picam2.start()

    def capture_frames(self):
        while self.running:
            image = self.picam2.capture_array()
            ret, jpeg = cv2.imencode('.jpg', image)
            if ret:
                with self.lock:
                    self.frame = jpeg.tobytes()
            time.sleep(0.033)  # ~30 fps

    def get_frame(self):
        with self.lock:
            return self.frame

    def shutdown_server(self):
        self.running = False
        self.picam2.stop()
        super().shutdown()


class CameraSystem:
    def __init__(self, host="0.0.0.0", video_port=65434):
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
        
        # Initialize server socket for video/audio streaming
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.video_port))
        self.server_socket.listen(5)
        logging.info(f"Server listening on {self.host}:{self.video_port}")
        
        # Add a clients set to track active connections
        self.clients = set()
        self.clients_lock = threading.Lock()
        
        # Add HTTP server for serving the webpage
        self.http_server = HTTPServer((self.host, 8000), SimpleHTTPRequestHandler)
        logging.info(f"HTTP server started at http://{self.host}:8000")

    def configure_camera(self):
        # Configure camera for a still configuration but can be used as a low-res video source
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
                    
                except (BrokenPipeError, ConnectionResetError):
                    logging.info(f"Client {addr} disconnected")
                    break
                except socket.error as e:
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
                client_thread.daemon = True
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
    server = CameraServer(('0.0.0.0', 8000), MJPEGHandler)
    try:
        logging.info("Starting server on http://0.0.0.0:8000")
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        server.shutdown_server()
