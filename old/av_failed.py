import socket
import select
import queue
import logging
import io
import time
import struct
from picamera2 import Picamera2
from PIL import Image
import pyaudio
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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
        # You may need to adjust the device_index, channels, rate, and format depending on your USB mic.
        self.audio_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )

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

    def capture_audio_chunk(self):
        # Read a chunk of audio data from the microphone
        data = self.audio_stream.read(1024, exception_on_overflow=False)
        return data

    def run(self):
        logging.info("Starting server run loop")
        self.server_socket.setblocking(False)
        inputs = [self.server_socket]
        outputs = []
        message_queues = {}

        while inputs:
            try:
                readable, writable, exceptional = select.select(
                    inputs, outputs, inputs, 0.1
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
                    # For this simplified server, we don't expect meaningful inbound data.
                    # If the client closes, data will be empty.
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

            # Send video and audio data to all connected clients
            video_data = self.capture_video_frame()
            audio_data = self.capture_audio_chunk()

            # Prepare header: 
            # We'll send two lengths: video_size and audio_size, each as 4-byte integers (network byte order)
            header = struct.pack('!II', len(video_data), len(audio_data))
            payload = header + video_data + audio_data

            for s in inputs:
                if s is not self.server_socket:
                    # Queue the message
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
