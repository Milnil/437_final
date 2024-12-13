import logging
import io
from PIL import Image
from picamera2 import Picamera2
import cv2
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import pyaudio
import ssl
import queue

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/video':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()

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
        elif self.path == '/audio':
            self.send_response(200)
            self.send_header('Content-type', 'application/octet-stream')
            self.end_headers()

            # Continuously send raw PCM audio data
            while self.server.running:
                audio_data = self.server.get_audio_frame()
                if audio_data:
                    # Logging each audio chunk being sent
                    logging.debug(f"Sending audio chunk of length {len(audio_data)} bytes.")
                    self.wfile.write(audio_data)
                else:
                    time.sleep(0.01)
        else:
            # Serve files
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

class CameraServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.picam2 = Picamera2()
        self.configure_camera()
        self.running = True
        self.frame = None
        self.lock = threading.Lock()

        # Enhanced audio settings
        self.audio_rate = 16000
        self.audio_channels = 1
        self.audio_format = pyaudio.paInt16
        self.chunk_size = 1024
        
        # Use a queue instead of a list for better thread safety
        self.audio_queue = queue.Queue(maxsize=100)  # Limit queue size to prevent memory issues
        self.audio_lock = threading.Lock()

        self.pyaudio_instance = pyaudio.PyAudio()
        self.audio_stream = self.pyaudio_instance.open(
            format=self.audio_format,
            channels=self.audio_channels,
            rate=self.audio_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )

        # Start threads
        self.capture_thread = threading.Thread(target=self.capture_frames)
        self.audio_thread = threading.Thread(target=self.capture_audio)
        self.capture_thread.start()
        self.audio_thread.start()

    def configure_camera(self):
        config = self.picam2.create_preview_configuration(main={"size": (320, 240)})
        self.picam2.configure(config)
        self.picam2.start()

    def capture_frames(self):
        while self.running:
            image = self.picam2.capture_array()
            ret, jpeg = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if ret:
                with self.lock:
                    self.frame = jpeg.tobytes()
            time.sleep(0.033)

    def capture_audio(self):
        while self.running:
            try:
                data = self.audio_stream.read(self.chunk_size, exception_on_overflow=False)
                if data:
                    # Use queue instead of list
                    try:
                        self.audio_queue.put(data, block=False)
                        logging.debug(f"Captured audio chunk of length {len(data)} bytes")
                    except queue.Full:
                        # If queue is full, remove oldest item and add new one
                        try:
                            self.audio_queue.get_nowait()
                            self.audio_queue.put(data, block=False)
                        except:
                            pass
            except Exception as e:
                logging.error(f"Error capturing audio: {e}")
                time.sleep(0.1)  # Prevent tight loop on error

    def get_frame(self):
        with self.lock:
            return self.frame

    def get_audio_frame(self):
        try:
            # Non-blocking get with timeout
            return self.audio_queue.get(timeout=0.1)
        except queue.Empty:
            return None
        except Exception as e:
            logging.error(f"Error getting audio frame: {e}")
            return None

    def shutdown_server(self):
        self.running = False
        # Clear audio queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except:
                pass
        self.picam2.stop()
        self.audio_stream.stop_stream()
        self.audio_stream.close()
        self.pyaudio_instance.terminate()
        super().shutdown()

if __name__ == "__main__":
    # If you're serving over HTTPS, use a self-signed certificate as previously discussed.
    # Otherwise, just run over HTTP. Below is HTTP for simplicity:
    server = CameraServer(('0.0.0.0', 8000), MJPEGHandler)
    try:
        logging.info("Starting server on http://0.0.0.0:8000")
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        server.shutdown_server()
