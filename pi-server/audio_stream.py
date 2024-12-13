# pi-server/audio_stream.py
import asyncio
import numpy as np
from websockets.server import serve
import logging
import pyaudio

logger = logging.getLogger(__name__)

class AudioStreamHandler:
    def __init__(self):
        self.clients = set()
        self.sample_rate = 44100
        self.channels = 1
        self.chunk_size = 1024
        self.format = pyaudio.paInt16
        
        # Initialize PyAudio
        self.p = pyaudio.PyAudio()
        self.stream = None

    def start_audio(self):
        self.stream = self.p.open(
            format=self.format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        logger.info("Audio stream started")

    async def handle_client(self, websocket):
        try:
            self.clients.add(websocket)
            logger.info(f"New audio client connected. Sample rate: {self.sample_rate}Hz")
            
            # Start audio stream if not already started
            if not self.stream:
                self.start_audio()
            
            # Send sample rate to client first
            await websocket.send(str(self.sample_rate).encode())
            
            while True:
                # Read from microphone
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                # Convert to numpy array for consistency
                audio_data = np.frombuffer(data, dtype=np.int16)
                await websocket.send(audio_data.tobytes())
                await asyncio.sleep(self.chunk_size / self.sample_rate)
                
        except Exception as e:
            logger.error(f"Audio client error: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info("Audio client disconnected")
            # Stop audio stream if no clients are connected
            if not self.clients and self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
                logger.info("Audio stream stopped")

    async def start_server(self):
        async with serve(self.handle_client, "0.0.0.0", 5002):
            logger.info("Audio server started on ws://0.0.0.0:5002")
            await asyncio.Future()

    def cleanup(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
        logger.info("Audio resources cleaned up")