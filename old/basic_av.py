import socket
import select
import queue
import logging
import io
import time
import struct
import threading
from picamera2 import Picamera2
from PIL import Image
import pyaudio
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class AudioThread(threading.Thread):
    def __init__(self, audio_stream, audio_queue):
        super().__init__(daemon=True)
        self.audio_stream = audio_stream
        self.audio_queue = audio_queue
        self.running = True

    def run(self):
        while self.running:
            try:
                data = self.audio_stream.read(1024, exception_on_overflow=False)
                # Keep multiple audio chunks in the queue rather than clearing it.
                # This allows us to accumulate a small buffer of audio data.
                self.audio_queue.put(data)
            except Exception as e:
                logging.error(f"Audio thread error: {e}")
                break

    def stop(self):
        self.running = False

class VideoAudioServer:
    def __init__(self, host="0.0.0.0", port=65434, audio_chunks_per_frame=4):
        logging.info("Initializing VideoAudioServer")
        
        # Initialize camera
        self.picam2 = Picamera2()
        video_config = self.picam2.create_still_configuration(main={"size": (320, 240)})
        self.picam2.configure(video_config)
        self.picam2.start()
        
        # Initialize PyAudio for microphone input
        self.audio = pyaudio.PyAudio()
        self.audio_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )

        # Audio queue for storing multiple audio chunks
        self.audio_queue = queue.Queue()
        self.audio_thread = AudioThread(self.audio_stream, self.audio_queue)
        self.audio_thread.start()

        # How many audio chunks to combine per video frame
        self.audio_chunks_per_frame = audio_chunks_per_frame

        # Setup server socket
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        logging.info(f"Server listening on {self.host}:{self.port}")

    def capture_video_frame(self):
        image = self.picam2.capture_array()
        img = Image.fromarray(image)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        return img_byte_arr.getvalue()

    def get_combined_audio_data(self):
        # Try to pull multiple audio chunks from the queue to form one continuous audio segment.
        chunks = []
        for _ in range(self.audio_chunks_per_frame):
            if not self.audio_queue.empty():
                chunks.append(self.audio_queue.get_nowait())
            else:
                # If there's not enough audio yet, break early
                break
        if chunks:
            return b''.join(chunks)
        else:
            # If no audio is available, return empty bytes
            return b''

    def run(self):
        logging.info("Starting server run loop")
        self.server_socket.setblocking(False)
        inputs = [self.server_socket]
        outputs = []
        message_queues = {}

        # Send at a roughly steady rate (e.g., ~10 FPS)
        frame_interval = 0.1
        last_send_time = time.time()

        while inputs:
            try:
                readable, writable, exceptional = select.select(
                    inputs, outputs, inputs, 0.05
                )
            except Exception as e:
                logging.error(f"Select error: {e}")
                break

            for s in readable:
                if s is self.server_socket:
                    client_socket, client_address = s.accept()
                    logging.info(f"New connection from {client_address}")
                    client_socket.setblocking(False)
                    inputs.append(client_socket)
                    message_queues[client_socket] = queue.Queue()
                else:
                    try:
                        data = s.recv(1024)
                        if not data:
                            # Client disconnected
                            logging.info("Client disconnected")
                            if s in outputs:
                                outputs.remove(s)
                            inputs.remove(s)
                            s.close()
                            del message_queues[s]
                    except Exception as e:
                        logging.error(f"Error reading from client: {e}")
                        if s in outputs:
                            outputs.remove(s)
                        inputs.remove(s)
                        s.close()
                        del message_queues[s]

            current_time = time.time()
            # Send data at a steady interval
            if current_time - last_send_time >= frame_interval:
                last_send_time = current_time

                # Capture video frame
                video_data = self.capture_video_frame()
                # Get combined audio data (multiple chunks)
                audio_data = self.get_combined_audio_data()

                # Prepare header
                header = struct.pack('!II', len(video_data), len(audio_data))
                payload = header + video_data + audio_data

                # Queue the message for all clients
                for s in inputs:
                    if s is not self.server_socket:
                        message_queues[s].put(payload)
                        if s not in outputs:
                            outputs.append(s)

            for s in writable:
                try:
                    next_msg = message_queues[s].get_nowait()
                except queue.Empty:
                    outputs.remove(s)
                else:
                    try:
                        s.sendall(next_msg)
                    except Exception as e:
                        logging.error(f"Send error: {e}")
                        if s in outputs:
                            outputs.remove(s)
                        if s in inputs:
                            inputs.remove(s)
                        s.close()
                        del message_queues[s]

            for s in exceptional:
                logging.error(f"Exception on {s.getpeername()}")
                inputs.remove(s)
                if s in outputs:
                    outputs.remove(s)
                s.close()
                del message_queues[s]

        self.cleanup()

    def cleanup(self):
        logging.info("Cleaning up resources")
        self.audio_thread.stop()
        self.picam2.stop()
        self.audio_stream.stop_stream()
        self.audio_stream.close()
        self.audio.terminate()
        logging.info("Cleanup complete")

if __name__ == "__main__":
    logging.info("Program is starting...")
    server = VideoAudioServer(audio_chunks_per_frame=4)  # try adjusting this number
    try:
        server.run()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt caught, exiting program")
        server.cleanup()
