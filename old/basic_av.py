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
        # Continuously read audio data and put into the queue
        while self.running:
            try:
                data = self.audio_stream.read(1024, exception_on_overflow=False)
                # We store the latest data. If you want to buffer multiple chunks,
                # you could append them. Here we just put the latest chunk.
                # To ensure we always have the latest chunk available, we can clear previous queue.
                with self.audio_queue.mutex:
                    self.audio_queue.queue.clear()
                self.audio_queue.put(data)
            except Exception as e:
                logging.error(f"Audio thread error: {e}")
                break

    def stop(self):
        self.running = False


class VideoAudioServer:
    def __init__(self, host="0.0.0.0", port=65434):
        logging.info("Initializing VideoAudioServer")
        
        # Initialize camera
        self.picam2 = Picamera2()
        video_config = self.picam2.create_still_configuration(main={"size": (320, 240)})
        self.picam2.configure(video_config)
        self.picam2.start()
        
        # Initialize PyAudio for microphone input
        self.audio = pyaudio.PyAudio()
        # Adjust device_index, channels, rate as needed
        self.audio_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )

        # Audio queue for storing the latest audio chunk
        self.audio_queue = queue.Queue()
        self.audio_thread = AudioThread(self.audio_stream, self.audio_queue)
        self.audio_thread.start()

        # Setup server socket
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        logging.info(f"Server listening on {self.host}:{self.port}")

    def capture_video_frame(self):
        # Capture image using Picamera2
        image = self.picam2.capture_array()
        img = Image.fromarray(image)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        return img_byte_arr.getvalue()

    def get_latest_audio_chunk(self):
        # Get the most recent audio chunk from the audio_queue
        # If none available, return empty bytes or possibly wait briefly
        if not self.audio_queue.empty():
            return self.audio_queue.get_nowait()
        else:
            # If no audio available, send empty audio to avoid stalling
            return b''

    def run(self):
        logging.info("Starting server run loop")
        self.server_socket.setblocking(False)
        inputs = [self.server_socket]
        outputs = []
        message_queues = {}

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

            # Prepare data to send
            # Capture video frame
            video_data = self.capture_video_frame()
            # Get latest audio chunk
            audio_data = self.get_latest_audio_chunk()

            # If audio_data is empty, we still send something to maintain timing.
            # You can choose to skip sending if no audio is present, but it may cause the client to stall.
            
            header = struct.pack('!II', len(video_data), len(audio_data))
            payload = header + video_data + audio_data

            # Send video and audio data to all connected clients
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
    server = VideoAudioServer()
    try:
        server.run()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt caught, exiting program")
        server.cleanup()
