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
import struct

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MJPEGHandler(BaseHTTPRequestHandler):
    """
    A handler that serves:
    - MJPEG stream from /video
    - WAV-like streaming audio from /audio
    - Static files from /
    """
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
                time.sleep(0.033)  # ~30 fps
        elif self.path == '/audio':
            # Serve a continuous WAV stream
            # We'll send a WAV header with an arbitrary large data chunk size, then continuous PCM data.
            # WAV header for 16-bit PCM, 1 channel, 16000 Hz
            audio_format = self.server.get_audio_format()
            if audio_format is None:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"No audio format available.")
                return

            self.send_response(200)
            self.send_header('Content-Type', 'audio/wav')
            self.end_headers()

            # Write WAV header
            # WAV header format:
            # ChunkID: "RIFF"
            # ChunkSize: 36 + Subchunk2Size (we'll put a large arbitrary value)
            # Format: "WAVE"
            # Subchunk1ID: "fmt "
            # Subchunk1Size: 16
            # AudioFormat: 1 (PCM)
            # NumChannels: 1
            # SampleRate: 16000
            # ByteRate: SampleRate * NumChannels * BitsPerSample/8
            # BlockAlign: NumChannels * BitsPerSample/8
            # BitsPerSample: 16
            # Subchunk2ID: "data"
            # Subchunk2Size: large arbitrary value
            num_channels = 1
            sample_rate = 16000
            bits_per_sample = 16
            byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
            block_align = num_channels * (bits_per_sample // 8)

            # We don't know the total size, so put Subchunk2Size as 0xFFFFFFFF (max for unsigned 32-bit).
            # Some players might handle this as a never-ending stream.
            wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
                                     b'RIFF',  # ChunkID
                                     36 + 0xFFFFFFFF,  # ChunkSize (fake large size)
                                     b'WAVE',  # Format
                                     b'fmt ',  # Subchunk1ID
                                     16,       # Subchunk1Size
                                     1,        # AudioFormat (PCM)
                                     num_channels,
                                     sample_rate,
                                     byte_rate,
                                     block_align,
                                     bits_per_sample,
                                     b'data',  # Subchunk2ID
                                     0xFFFFFFFF)  # Subchunk2Size (fake large size)

            self.wfile.write(wav_header)

            # Now continuously write raw PCM frames from the audio queue
            while self.server.running:
                audio_data = self.server.get_audio_frame()
                if audio_data:
                    self.wfile.write(audio_data)
                # A small sleep to prevent CPU hogging
                time.sleep(0.01)

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

class CameraServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.picam2 = Picamera2()
        self.configure_camera()
        self.running = True
        self.frame = None
        self.lock = threading.Lock()

        # Setup audio recording from USB mic
        # Adjust as needed for your microphone
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
        
        # Start capture threads
        self.capture_thread = threading.Thread(target=self.capture_frames)
        self.capture_thread.start()

        self.audio_thread = threading.Thread(target=self.capture_audio)
        self.audio_thread.start()

    def configure_camera(self):
        # Set a small resolution for demonstration
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
            time.sleep(0.033)  # ~30 fps

    def capture_audio(self):
        # Continuously read audio data from the microphone and store it in a buffer
        while self.running:
            data = self.audio_stream.read(self.chunk_size)
            with self.audio_lock:
                self.audio_queue.append(data)

    def get_frame(self):
        with self.lock:
            return self.frame

    def get_audio_frame(self):
        # Return the oldest available audio frame if any
        with self.audio_lock:
            if self.audio_queue:
                return self.audio_queue.pop(0)
            else:
                return None

    def get_audio_format(self):
        # Return information about the audio format, if needed
        return {
            'rate': self.audio_rate,
            'channels': self.audio_channels,
            'format': self.audio_format
        }

    def shutdown_server(self):
        self.running = False
        self.picam2.stop()
        self.audio_stream.stop_stream()
        self.audio_stream.close()
        self.pyaudio_instance.terminate()
        super().shutdown()

if __name__ == "__main__":
    server = CameraServer(('0.0.0.0', 8000), MJPEGHandler)
    try:
        logging.info("Starting server on http://0.0.0.0:8000")
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
        server.shutdown_server()
