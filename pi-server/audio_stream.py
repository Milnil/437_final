# pi-server/audio_stream.py
import asyncio
import numpy as np
from websockets.server import serve
import logging
import pyaudio
import time

logger = logging.getLogger(__name__)

class AudioStreamHandler:
    def __init__(self):
        self.clients = set()
        self.sample_rate = 44100
        self.channels = 1
        self.chunk_size = 1024
        self.format = pyaudio.paInt16
        
        logger.info("Initializing PyAudio for microphone capture...")
        self.p = pyaudio.PyAudio()
        self.stream = None
        
        # Log available audio devices
        info = self.p.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        for i in range(0, numdevices):
            device_info = self.p.get_device_info_by_host_api_device_index(0, i)
            logger.info(f"Audio Device {i}: {device_info.get('name')}")
            if device_info.get('maxInputChannels') > 0:
                logger.info(f"  Input Device {i}: {device_info.get('name')}")

    def start_audio(self):
        try:
            self.stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            logger.info(f"Started audio input stream: rate={self.sample_rate}Hz, channels={self.channels}, format={self.format}")
        except Exception as e:
            logger.error(f"Failed to start audio input stream: {e}")
            raise

    async def handle_client(self, websocket):
        client_id = id(websocket)
        try:
            self.clients.add(websocket)
            logger.info(f"New audio client connected [ID: {client_id}]. Total clients: {len(self.clients)}")
            
            if not self.stream:
                self.start_audio()
            
            # Send sample rate to client first
            await websocket.send(str(self.sample_rate).encode())
            logger.info(f"Sent sample rate {self.sample_rate}Hz to client [ID: {client_id}]")
            
            start_time = time.time()
            frames_sent = 0
            
            while True:
                try:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    await websocket.send(audio_data.tobytes())
                    
                    frames_sent += 1
                    if frames_sent % 100 == 0:  # Log every 100 frames
                        elapsed = time.time() - start_time
                        rate = frames_sent / elapsed
                        logger.debug(f"Streaming to client [ID: {client_id}] at {rate:.2f} fps")
                        
                except Exception as e:
                    logger.error(f"Error streaming to client [ID: {client_id}]: {e}")
                    break
                    
                await asyncio.sleep(self.chunk_size / self.sample_rate)
                
        except Exception as e:
            logger.error(f"Audio client error [ID: {client_id}]: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info(f"Audio client disconnected [ID: {client_id}]. Remaining clients: {len(self.clients)}")
            if not self.clients and self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
                logger.info("Audio input stream stopped - no more clients")

    async def start_server(self):
        async with serve(self.handle_client, "0.0.0.0", 5002):
            logger.info("Audio server started on ws://0.0.0.0:5002")
            await asyncio.Future()

    def cleanup(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            logger.info("Audio input stream closed")
        if hasattr(self, 'p'):
            self.p.terminate()
            logger.info("PyAudio instance terminated")