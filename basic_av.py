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
import queue

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class StreamingBuffer:
    def __init__(self, maxsize=10):
        self.queue = queue.Queue(maxsize=maxsize)
        self.lock = threading.Lock()
    
    def put(self, data):
        try:
            self.queue.put_nowait(data)
        except queue.Full:
            # If queue is full, remove oldest item
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(data)
            except:
                pass
    
    def get(self):
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return None

class MJPEGHandler(BaseHTTPRequestHandler):
    def send_frame(self, frame_data, content_type):
        self.wfile.write(b"--frame\r\n")
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(frame_data)))
        self.end_headers()
        self.wfile.write(frame_data)
        self.wfile.write(b"\r\n")

    def do_GET(self):
        if self.path == '/video':
            logging.info("Video stream requested")
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()

            while self.server.running:
                frame = self.server.video_buffer.get()
                if frame is not None:
                    try:
                        self.send_frame(frame, 'image/jpeg')
                    except Exception as e:
                        logging.error(f"Error sending video frame: {e}")
                        break
                time.sleep(0.033)  # ~30fps
        
        elif self.path == '/audio':
            logging.info("Audio stream requested")
            self.send_response(200)
            self.send_header('Content-type', 'application/octet-stream')
            self.end_headers()
            
            while self.server.running:
                audio_data = self.server.audio_buffer.get()
                if audio_data is not None:
                    try:
                        self.wfile.write(audio_data)
                        self.wfile.flush()
                    except Exception as e:
                        logging.error(f"Error sending audio data: {e}")
                        break
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
        self.running = True
        
        # Initialize buffers
        self.video_buffer = StreamingBuffer(maxsize=10)
        self.audio_buffer = StreamingBuffer(maxsize=50)
        
        # Initialize camera
        self.picam2 = Picamera2()
        self.configure_camera()
        
        # Start the worker threads
        self.start_workers()

    def configure_camera(self):
        config = self.picam2.create_preview_configuration(main={"size": (320, 240)})
        self.picam2.configure(config)
        self.picam2.start()

    def start_workers(self):
        # Start video capture thread
        self.video_thread = threading.Thread(target=self.capture_frames)
        self.video_thread.daemon = True
        self.video_thread.start()
        
        # Start audio capture thread
        self.audio_thread = threading.Thread(target=self.stream_wav_file)
        self.audio_thread.daemon = True
        self.audio_thread.start()

    def capture_frames(self):
        while self.running:
            try:
                image = self.picam2.capture_array()
                ret, jpeg = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ret:
                    self.video_buffer.put(jpeg.tobytes())
            except Exception as e:
                logging.error(f"Error capturing video frame: {e}")
            time.sleep(0.033)

    def stream_wav_file(self):
        while self.running:
            try:
                with wave.open('BabyElephantWalk60.wav', 'rb') as wav_file:
                    chunk_size = 1024
                    while self.running:
                        data = wav_file.readframes(chunk_size)
                        if not data:
                            wav_file.rewind()
                            logging.info("Rewinding WAV file")
                            continue
                        self.audio_buffer.put(data)
                        time.sleep(0.01)  # Control streaming rate
            except Exception as e:
                logging.error(f"Error streaming WAV file: {e}")
                time.sleep(1)  # Wait before retrying

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