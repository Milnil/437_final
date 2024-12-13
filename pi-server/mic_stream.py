import asyncio
from websockets.server import serve
import logging
import pyaudio
import numpy as np

logger = logging.getLogger(__name__)

class MicStreamHandler:
    def __init__(self):
        self.clients = set()
        self.current_broadcaster = None
        
        # Audio settings
        self.p = pyaudio.PyAudio()
        self.sample_rate = 44100
        self.channels = 1
        self.chunk_size = 1024
        self.format = pyaudio.paInt16
        self.stream = None

    def start_audio_output(self):
        if self.stream is None:
            self.stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,  # This makes it an output stream
                frames_per_buffer=self.chunk_size
            )
            logger.info("Audio output stream started")

    async def handle_client(self, websocket):
        try:
            self.clients.add(websocket)
            logger.info("New microphone broadcaster connected")
            
            # Start audio output when first client connects
            self.start_audio_output()
            
            while True:
                data = await websocket.recv()
                logger.info(f"Received audio chunk of size: {len(data)} bytes")
                
                try:
                    # Play the received audio
                    if self.stream:
                        self.stream.write(data)
                except Exception as e:
                    logger.error(f"Error playing audio: {e}")
                
        except Exception as e:
            logger.error(f"Microphone client error: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info("Microphone broadcaster disconnected")
            
            # Stop audio output if no clients are connected
            if not self.clients and self.stream:
                self.cleanup()

    async def start_server(self):
        async with serve(self.handle_client, "0.0.0.0", 5003):
            logger.info("Microphone server started on ws://0.0.0.0:5003")
            await asyncio.Future()

    def cleanup(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        if hasattr(self, 'p'):
            self.p.terminate()
        logger.info("Audio resources cleaned up") 