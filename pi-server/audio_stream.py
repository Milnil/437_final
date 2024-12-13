# pi-server/audio_stream.py
import asyncio
import pyaudio
import numpy as np
from websockets.server import serve

class AudioStreamHandler:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.chunk_size = 1024
        self.format = pyaudio.paFloat32
        self.channels = 1
        self.rate = 44100
        self.stream = None
        self.clients = set()

    def start_audio(self):
        self.stream = self.p.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )

    async def handle_client(self, websocket):
        try:
            self.clients.add(websocket)
            if not self.stream:
                self.start_audio()
            
            while True:
                data = self.stream.read(self.chunk_size)
                audio_data = np.frombuffer(data, dtype=np.float32)
                await websocket.send(audio_data.tobytes())
                await asyncio.sleep(0.01)
        except Exception as e:
            print(f"Audio client error: {e}")
        finally:
            self.clients.remove(websocket)
            if not self.clients and self.stream:
                self.cleanup()

    async def start_server(self):
        async with serve(self.handle_client, "0.0.0.0", 5001):
            await asyncio.Future()  # run forever

    def cleanup(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()