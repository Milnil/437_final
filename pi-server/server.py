import logging
import asyncio
from video_stream import VideoStreamHandler
from audio_stream import AudioStreamHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    video_handler = VideoStreamHandler()
    audio_handler = AudioStreamHandler()
    
    try:
        # Start both servers concurrently
        await asyncio.gather(
            video_handler.start_server(),
            audio_handler.start_server()
        )
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
    finally:
        video_handler.cleanup()
        audio_handler.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")