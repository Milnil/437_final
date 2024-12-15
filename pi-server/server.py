import logging
import asyncio
import threading
from video_stream import VideoStreamHandler
from audio_stream import AudioStreamHandler
from mic_stream import MicStreamHandler
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
import os
import time
import json
import cv2
import collections
import subprocess


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app for HTTP endpoints (Port 5004)
app = FastAPI()

# Add CORS middleware to the main app (port 5004)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (for production, specify the frontend URL)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers (like Authorization, Content-Type, etc.)
)

@app.get("/recordings")
async def get_recordings():
    """
    Get metadata for all video files in the storage directory.
    """
    try:
        video_path = "./videos"
        recordings = []
        for filename in os.listdir(video_path):
            if filename.endswith(".mp4"):
                filepath = os.path.join(video_path, filename)
                file_info = os.stat(filepath)
                recordings.append({
                    "filename": filename,
                    "size": file_info.st_size,
                    "created": file_info.st_ctime
                })
        return JSONResponse(content={"recordings": recordings})
    except Exception as e:
        logger.error(f"Error getting recordings: {e}")
        return JSONResponse(content={"error": "Failed to list recordings"}, status_code=500)

@app.get("/videos/{filename}")
async def get_video(filename: str):
    """
    Serve the video file as a streaming response.
    """
    video_path = f"./videos/{filename}"
    if not os.path.isfile(video_path):
        raise HTTPException(status_code=404, detail="Video not found")
    
    def video_stream():
        with open(video_path, "rb") as video_file:
            yield from video_file
    
    response = StreamingResponse(video_stream(), media_type="video/mp4")
    response.headers["Accept-Ranges"] = "bytes"
    return response

@app.delete("/videos/{filename}")
async def delete_video(filename: str):
    """
    Delete the video file for a given filename.
    """
    try:
        video_path = f"./videos/{filename}"
        if os.path.exists(video_path):
            os.remove(video_path)
            logger.info(f"Deleted video file: {video_path}")
            return JSONResponse(content={"message": "File deleted successfully"})
        else:
            logger.warning(f"File not found for deletion: {video_path}")
            raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"Error deleting video file: {e}")
        return JSONResponse(content={"error": "Failed to delete video"}, status_code=500)


# WebSocket server for notifications (Port 5005)
notifications_app = FastAPI()

# Add CORS middleware to the notifications app (port 5005)
notifications_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (you should restrict this in production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
video_handler = VideoStreamHandler()

@notifications_app.post("/save-video/{video_id}")
async def save_video(video_id: str):
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid video ID")
    try:
        output_path = f"videos/notification_{video_id}.mp4"
        await video_handler.save_last_4_seconds(output_path)
        return {"message": f"Saved last 4 seconds of video as {output_path}"}
    except Exception as e:
        logger.error(f"Error saving video: {e}")
        raise HTTPException(status_code=500, detail="Failed to save video")




async def main():
    audio_handler = AudioStreamHandler()
    mic_handler = MicStreamHandler()
    
    try:
        await asyncio.gather(
            video_handler.start_server(),
            audio_handler.start_server(),
            mic_handler.start_server()
        )
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
    finally:
        video_handler.cleanup()
        audio_handler.cleanup()
        mic_handler.cleanup()


if __name__ == "__main__":
    try:
        import uvicorn
        
        http_server_thread = threading.Thread(
            target=lambda: uvicorn.run(app, host="0.0.0.0", port=5004, log_level="info"),
            daemon=True
        )
        http_server_thread.start()

        notifications_server_thread = threading.Thread(
            target=lambda: uvicorn.run(notifications_app, host="0.0.0.0", port=5005, log_level="info"),
            daemon=True
        )
        notifications_server_thread.start()

        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
