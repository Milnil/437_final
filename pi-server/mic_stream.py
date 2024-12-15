import asyncio
from websockets.server import serve
import logging
import pyaudio
import numpy as np
import time
import queue

logger = logging.getLogger(__name__)

class MicStreamHandler:
    def __init__(self):
        self.clients = set()
        
        # Audio settings
        self.sample_rate = 44100
        self.channels = 1
        self.chunk_size = 4096  # Increased buffer size
        self.format = pyaudio.paInt16
        
        # Audio buffer
        self.buffer = queue.Queue(maxsize=10)  # Limit buffer size
        
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
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
            logger.info(f"Started audio output stream: rate={self.sample_rate}Hz, channels={self.channels}, format={self.format}")
        except Exception as e:
            logger.error(f"Failed to start audio output stream: {e}")
            raise

    def _audio_callback(self, in_data, frame_count, time_info, status):
        try:
            data = self.buffer.get_nowait()
            return (data, pyaudio.paContinue)
        except queue.Empty:
            return (b'\x00' * self.chunk_size * 2, pyaudio.paContinue)

    def clear_buffer(self):
        while not self.buffer.empty():
            try:
                self.buffer.get_nowait()
            except queue.Empty:
                break

    async def handle_client(self, websocket):
        client_id = id(websocket)
        try:
            self.clients.add(websocket)
            logger.info(f"New microphone client connected [ID: {client_id}]. Total clients: {len(self.clients)}")
            
            if not self.stream:
                self.start_audio_output()
            else:
                self.clear_buffer()
            
            async for message in websocket:
                try:
                    frames_received += 1
                    
                    if frames_received % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = frames_received / elapsed
                        logger.info(f"Receiving from client [ID: {client_id}] at {rate:.2f} fps")
                    
                    try:
                        self.buffer.put_nowait(data)
                    except queue.Full:
                        self.clear_buffer()  # Clear buffer if it gets full
                        self.buffer.put_nowait(data)
                    
                except Exception as e:
                    logger.error(f"Error processing audio from client [ID: {client_id}]: {e}")
                    break
                
        except Exception as e:
            logger.error(f"Microphone client error [ID: {client_id}]: {e}")
        finally:
            await self.cleanup_client(websocket, client_id)

    async def cleanup_client(self, websocket, client_id):
        if websocket in self.clients:
            self.clients.remove(websocket)
            logger.info(f"Microphone client disconnected [ID: {client_id}]. Remaining clients: {len(self.clients)}")
            
            if not self.clients:
                self.clear_buffer()
                self.cleanup()
                logger.info("All clients disconnected, cleaned up audio resources")

    async def start_server(self):
        async with serve(self.handle_client, "0.0.0.0", 5003):
            logger.info("Microphone server started on ws://0.0.0.0:5003")
            await asyncio.Future()

    def cleanup(self):
        self.clear_buffer()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            logger.info("Audio output stream closed")
        if hasattr(self, 'p'):
            self.p.terminate()
            logger.info("PyAudio instance terminated")