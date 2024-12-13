import asyncio
import os
from PIL import Image
import io
import wave
import numpy as np
from websockets.server import serve
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MockVideoStream:
    def __init__(self):
        self.clients = set()
        self.test_frame = Image.open("test_assets/test_frame.png")
        self.frame_bytes = self.prepare_frame()
        
    def prepare_frame(self):
        resized = self.test_frame.resize((640, 480))
        img_byte_arr = io.BytesIO()
        resized.save(img_byte_arr, format='JPEG', quality=85)
        return img_byte_arr.getvalue()

    async def handle_client(self, websocket):
        try:
            self.clients.add(websocket)
            logger.info("New video client connected")
            while True:
                await websocket.send(self.frame_bytes)
                await asyncio.sleep(0.033)  # ~30fps
        except Exception as e:
            logger.error(f"Video client error: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info("Video client disconnected")

class MockAudioStream:
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

async def main():
    video_stream = MockVideoStream()
    audio_stream = MockAudioStream()
    
    async with serve(video_stream.handle_client, "localhost", 5001):
        logger.info("Video server started on ws://localhost:5001")
        async with serve(audio_stream.handle_client, "localhost", 5002):
            logger.info("Audio server started on ws://localhost:5002")
            await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")