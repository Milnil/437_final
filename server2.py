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

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MJPEGHandler(BaseHTTPRequestHandler):
    # ... Your existing request handler code ...
    def do_GET(self):
        if self.path == '/video':
            # Serve MJPEG video as before
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            while self.server.running:
                frame = self.server.get_frame()
                if frame is not None:
                    self.wfile.write(b"--frame\r\n")
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', str(len(frame)))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                time.sleep(0.033)
        elif self.path == '/audio':
            # Serve raw PCM audio
            self.send_response(200)
            self.send_header('Content-type', 'application/octet-stream')
            self.end_headers()
            while self.server.running:
                audio_data = self.server.get_audio_frame()
                if audio_data:
                    self.wfile.write(audio_data)
                else:
                    time.sleep(0.01)
        else:
            # Serve static files
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

        # Audio settings
        self.audio_rate = 16000
        self.audio_channels = 1
        self.audio_format = pyaudio.paInt16
        self.chunk_size = 1024

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
    # Change the port to 8443 for HTTPS
    server = CameraServer(('0.0.0.0', 8443), MJPEGHandler)

    # Wrap server socket with SSL
    server.socket = ssl.wrap_socket(
        server.socket,
        keyfile="key.pem",
        certfile="cert.pem",
        server_side=True,
        ssl_version=ssl.PROTOCOL_TLS_SERVER
    )

    try:
        logging.info("Starting server on https://0.0.0.0:8443")
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        server.shutdown_server()
