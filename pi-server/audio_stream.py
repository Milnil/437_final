# pi-server/audio_stream.py
import asyncio
import wave
import numpy as np
from websockets.server import serve
import logging

logger = logging.getLogger(__name__)

class AudioStreamHandler:
    def __init__(self):
        self.clients = set()
        self.sample_rate = 44100
        self.channels = 1
        self.chunk_size = 1024
        self.audio_data, self.sample_rate = self.load_audio()
        self.position = 0

    def load_audio(self):
        with wave.open("test_assets/BabyElephantWalk60.wav", 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            frames = wav_file.readframes(-1)
            return np.frombuffer(frames, dtype=np.int16), sample_rate

    async def handle_client(self, websocket):
        try:
            self.clients.add(websocket)
            logger.info(f"New audio client connected. Sample rate: {self.sample_rate}Hz")
            
            # Send sample rate to client first
            await websocket.send(str(self.sample_rate).encode())
            
            while True:
                end_pos = self.position + self.chunk_size
                if end_pos >= len(self.audio_data):
                    self.position = 0
                    end_pos = self.chunk_size
                    logger.info("Audio loop restarting")
                
                chunk = self.audio_data[self.position:end_pos]
                await websocket.send(chunk.tobytes())
                self.position = end_pos
                
                delay = self.chunk_size / self.sample_rate
                await asyncio.sleep(delay)
                
        except Exception as e:
            logger.error(f"Audio client error: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info("Audio client disconnected")

    async def start_server(self):
        async with serve(self.handle_client, "0.0.0.0", 5002):
            logger.info("Audio server started on ws://0.0.0.0:5002")
            await asyncio.Future()

    def cleanup(self):
        pass  # No cleanup needed for WAV file playback