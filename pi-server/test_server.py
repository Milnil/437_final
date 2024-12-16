import asyncio
import os
from PIL import Image
import io
import wave
import numpy as np
from websockets.server import serve
import logging
import queue

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
        client_id = id(websocket)
        try:
            self.clients.add(websocket)
            logger.info(f"New video client connected [ID: {client_id}]. Total clients: {len(self.clients)}")
            while True:
                await websocket.send(self.frame_bytes)
                await asyncio.sleep(0.033)  # ~30fps
        except Exception as e:
            logger.error(f"Video client error [ID: {client_id}]: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info(f"Video client disconnected [ID: {client_id}]. Remaining clients: {len(self.clients)}")

    async def start_server(self):
        async with serve(self.handle_client, "localhost", 5001):
            logger.info("Video server started on ws://localhost:5001")
            await asyncio.Future()

    def cleanup(self):
        logger.info("Video server cleanup")

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
        client_id = id(websocket)
        try:
            self.clients.add(websocket)
            logger.info(f"New audio client connected [ID: {client_id}]. Sample rate: {self.sample_rate}Hz")
            
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
            logger.error(f"Audio client error [ID: {client_id}]: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info(f"Audio client disconnected [ID: {client_id}]. Remaining clients: {len(self.clients)}")

    async def start_server(self):
        async with serve(self.handle_client, "localhost", 5002):
            logger.info("Audio server started on ws://localhost:5002")
            await asyncio.Future()

    def cleanup(self):
        logger.info("Audio server cleanup")

class MockMicStream:
    def __init__(self):
        self.clients = set()
        self.sample_rate = 44100
        self.channels = 1
        self.chunk_size = 4096
        self.buffer = queue.Queue(maxsize=10)
        
        # Load test audio for simulating microphone input
        self.audio_data, _ = self.load_audio()
        self.position = 0

    def load_audio(self):
        with wave.open("test_assets/BabyElephantWalk60.wav", 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            frames = wav_file.readframes(-1)
            return np.frombuffer(frames, dtype=np.int16), sample_rate

    async def handle_client(self, websocket):
        client_id = id(websocket)
        try:
            self.clients.add(websocket)
            logger.info(f"New microphone client connected [ID: {client_id}]. Total clients: {len(self.clients)}")
            
            while True:
                # Simulate receiving audio data from client
                data = await websocket.recv()
                
                # Echo the received audio back (simulating speaker output)
                try:
                    self.buffer.put_nowait(data)
                except queue.Full:
                    # Clear buffer if full
                    while not self.buffer.empty():
                        self.buffer.get_nowait()
                    self.buffer.put_nowait(data)
                
        except Exception as e:
            logger.error(f"Microphone client error [ID: {client_id}]: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info(f"Microphone client disconnected [ID: {client_id}]. Remaining clients: {len(self.clients)}")

    async def start_server(self):
        async with serve(self.handle_client, "localhost", 5003):
            logger.info("Microphone server started on ws://localhost:5003")
            await asyncio.Future()

    def cleanup(self):
        while not self.buffer.empty():
            try:
                self.buffer.get_nowait()
            except queue.Empty:
                break
        logger.info("Microphone server cleanup")

async def main():
    video_stream = MockVideoStream()
    audio_stream = MockAudioStream()
    mic_stream = MockMicStream()
    
    try:
        await asyncio.gather(
            video_stream.start_server(),
            audio_stream.start_server(),
            mic_stream.start_server()
        )
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
    finally:
        video_stream.cleanup()
        audio_stream.cleanup()
        mic_stream.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")