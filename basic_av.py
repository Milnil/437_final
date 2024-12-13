import logging
import io
from PIL import Image
from picamera2 import Picamera2
import cv2
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import wave

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/video':
            logging.info("Video stream requested")
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
            logging.info("Audio stream requested")
            self.send_response(200)
            self.send_header('Content-type', 'application/octet-stream')
            self.end_headers()
            
            try:
                with wave.open('BabyElephantWalk60.wav', 'rb') as wav_file:
                    chunk_size = 1024
                    while self.server.running:
                        data = wav_file.readframes(chunk_size)
                        if not data:
                            wav_file.rewind()
                            logging.info("Rewinding WAV file")
                            continue
                        
                        logging.info(f"Sending WAV chunk: {len(data)} bytes")
                        self.wfile.write(data)
                        self.wfile.flush()
                        time.sleep(0.01)  # Control streaming rate
                        
            except Exception as e:
                logging.error(f"Error streaming WAV file: {e}")
        
        else:
            # Serve static files (index.html, etc.)
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
                self.end_headers()
                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File not found")

class CameraServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.picam2 = Picamera2()
        self.configure_camera()
        self.running = True
        self.frame = None
        self.lock = threading.Lock()
        
        # Start video capture thread
        self.capture_thread = threading.Thread(target=self.capture_frames)
        self.capture_thread.start()

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

    def get_frame(self):
        with self.lock:
            return self.frame

    def shutdown_server(self):
        self.running = False
        self.picam2.stop()
        super().shutdown()

if __name__ == "__main__":
    server = CameraServer(('0.0.0.0', 8000), MJPEGHandler)
    try:
        logging.info("Starting server on http://0.0.0.0:8000")
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        server.shutdown_server()