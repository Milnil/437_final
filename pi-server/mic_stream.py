import asyncio
from websockets.server import serve
import logging
import pyaudio
import numpy as np
import time

logger = logging.getLogger(__name__)

class MicStreamHandler:
    def __init__(self):
        self.clients = set()
        
        # Audio settings
        self.sample_rate = 44100
        self.channels = 1
        self.chunk_size = 1024
        self.format = pyaudio.paInt16
        
        logger.info("Initializing PyAudio for speaker output...")
        self.p = pyaudio.PyAudio()
        self.stream = None
        
        # Log available audio devices
        info = self.p.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        for i in range(0, numdevices):
            device_info = self.p.get_device_info_by_host_api_device_index(0, i)
            logger.info(f"Audio Device {i}: {device_info.get('name')}")
            if device_info.get('maxOutputChannels') > 0:
                logger.info(f"  Output Device {i}: {device_info.get('name')}")

    def start_audio_output(self):
        try:
            self.stream = self.p.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.chunk_size
            )
            logger.info(f"Started audio output stream: rate={self.sample_rate}Hz, channels={self.channels}, format={self.format}")
        except Exception as e:
            logger.error(f"Failed to start audio output stream: {e}")
            raise

    async def handle_client(self, websocket):
        client_id = id(websocket)
        try:
            self.clients.add(websocket)
            logger.info(f"New microphone client connected [ID: {client_id}]. Total clients: {len(self.clients)}")
            
            if not self.stream:
                self.start_audio_output()
            
            start_time = time.time()
            frames_received = 0
            
            while True:
                try:
                    data = await websocket.recv()
                    frames_received += 1
                    
                    if frames_received % 100 == 0:  # Log every 100 frames
                        elapsed = time.time() - start_time
                        rate = frames_received / elapsed
                        logger.debug(f"Receiving from client [ID: {client_id}] at {rate:.2f} fps")
                        logger.debug(f"Received audio chunk of size: {len(data)} bytes")
                    
                    if self.stream:
                        self.stream.write(data)
                    
                except Exception as e:
                    logger.error(f"Error processing audio from client [ID: {client_id}]: {e}")
                    break
                
        except Exception as e:
            logger.error(f"Microphone client error [ID: {client_id}]: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info(f"Microphone client disconnected [ID: {client_id}]. Remaining clients: {len(self.clients)}")
            
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
            logger.info("Audio output stream closed")
        if hasattr(self, 'p'):
            self.p.terminate()
            logger.info("PyAudio instance terminated")