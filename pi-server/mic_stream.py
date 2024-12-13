import asyncio
from websockets.server import serve
import logging

logger = logging.getLogger(__name__)

class MicStreamHandler:
    def __init__(self):
        self.clients = set()
        self.current_broadcaster = None

    async def handle_client(self, websocket):
        try:
            if self.current_broadcaster is not None:
                logger.info("Rejected mic connection - someone else is broadcasting")
                await websocket.close()
                return

            self.current_broadcaster = websocket
            self.clients.add(websocket)
            logger.info("New microphone broadcaster connected")
            
            while True:
                data = await websocket.recv()
                logger.info(f"Received audio chunk of size: {len(data)} bytes")
                # TODO: Process and play the received audio
                
        except Exception as e:
            logger.error(f"Microphone client error: {e}")
        finally:
            self.clients.remove(websocket)
            if self.current_broadcaster == websocket:
                self.current_broadcaster = None
            logger.info("Microphone broadcaster disconnected")

    async def start_server(self):
        async with serve(self.handle_client, "0.0.0.0", 5003):
            logger.info("Microphone server started on ws://0.0.0.0:5003")
            await asyncio.Future()

    def cleanup(self):
        pass 