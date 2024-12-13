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
import wave

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
            
            # Open and read the test WAV file
            try:
                with wave.open('BabyElephantWalk60.wav', 'rb') as wav_file:
                    chunk_size = 1024
                    while self.server.running:
                        data = wav_file.readframes(chunk_size)
                        if not data:
                            # If we reach the end, go back to start
                            wav_file.rewind()
                            continue
                        
                        logging.info(f"Sending WAV chunk of length {len(data)} bytes to client")
                        try:
                            self.wfile.write(data)
                            self.wfile.flush()  # Ensure data is sent immediately
                        except Exception as e:
                            logging.error(f"Error sending audio data: {e}")
                            break
                        time.sleep(0.01)  # Small delay to control streaming rate
            except Exception as e:
                logging.error(f"Error opening or reading WAV file: {e}")
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
        self.audio_stream = self.pyaudio_instance.open(format=self.audio_format,
                                                       channels=self.audio_channels,
                                                       rate=self.audio_rate,
                                                       input=True,
                                                       frames_per_buffer=self.chunk_size)
        self.audio_lock = threading.Lock()
        self.audio_queue = []

        self.capture_thread = threading.Thread(target=self.capture_frames)
        self.capture_thread.start()

        self.audio_thread = threading.Thread(target=self.capture_audio)
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
            data = self.audio_stream.read(self.chunk_size)
            with self.audio_lock:
                self.audio_queue.append(data)
            # Log that we captured audio data
            logging.debug(f"Captured audio chunk of length {len(data)} bytes from microphone.")

    def get_frame(self):
        with self.lock:
            return self.frame

    def get_audio_frame(self):
        with self.audio_lock:
            if self.audio_queue:
                return self.audio_queue.pop(0)
            else:
                return None

    def shutdown_server(self):
        self.running = False
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
