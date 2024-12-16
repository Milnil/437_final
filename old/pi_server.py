import websockets
import asyncio
import logging

logging.basicConfig(level=logging.INFO)

async def send_message(websocket):
    while True:
        try:
            await websocket.send("Hello World from Raspberry Pi!")
            await asyncio.sleep(1)  # Send message every second
        except websockets.exceptions.ConnectionClosed:
            break

async def main():
    async with websockets.serve(send_message, "192.168.10.59", 8765):
        logging.info("Server started at ws://192.168.10.59:8765")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main()) 