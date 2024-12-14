import os
import cv2
import logging
import asyncio
from websockets.server import serve

logger = logging.getLogger(__name__)

class VideoStorageHandler:
    """
    Handles the saving and removal of video files locally. Videos are saved with filenames corresponding to unique IDs.
    """

    def __init__(self, storage_directory="videos"):
        """
        Initializes the video storage handler.
        
        Args:
            storage_directory (str): The directory where videos will be stored.
        """
        self.storage_directory = storage_directory
        os.makedirs(self.storage_directory, exist_ok=True)
        logger.info(f"Video storage directory set to: {self.storage_directory}")

    async def handle_client(self, websocket):
        """
        Handles incoming client requests to save, delete, or list videos.
        
        Args:
            websocket: The websocket connection to the client.
        """
        try:
            async for message in websocket:
                command = message.get("command")
                video_id = message.get("video_id")
                
                if command == "save":
                    frames = message.get("frames", [])
                    fps = message.get("fps", 30)
                    await asyncio.to_thread(self.save_video, video_id, frames, fps)
                    await websocket.send({"status": "success", "message": f"Video {video_id} saved successfully."})
                
                elif command == "delete":
                    success = await asyncio.to_thread(self.remove_video, video_id)
                    if success:
                        await websocket.send({"status": "success", "message": f"Video {video_id} deleted successfully."})
                    else:
                        await websocket.send({"status": "error", "message": f"Failed to delete video {video_id}."})
                
                elif command == "list":
                    videos = await asyncio.to_thread(self.list_videos)
                    await websocket.send({"status": "success", "videos": videos})
                
                else:
                    await websocket.send({"status": "error", "message": "Invalid command."})
        except Exception as e:
            logger.error(f"Error handling client: {e}")

    async def start_server(self):
        """
        Starts the WebSocket server to handle incoming client requests.
        """
        async with serve(self.handle_client, "0.0.0.0", 5004):
            logger.info("Video storage server started on ws://0.0.0.0:5004")
            await asyncio.Future()

    def save_video(self, video_id: str, frames: list, fps: int = 30):
        """
        Saves a video locally with the specified ID.
        
        Args:
            video_id (str): The unique identifier for the video file.
            frames (list): A list of frames (images) to be written to the video file.
            fps (int): The frame rate of the video. Default is 30 fps.
        
        Returns:
            str: The path to the saved video file.
        """
        video_path = os.path.join(self.storage_directory, f"{video_id}.mp4")
        
        if not frames:
            logger.warning(f"No frames provided to save for video ID {video_id}")
            return None
        
        height, width, _ = frames[0].shape
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec for .mp4 files
        video_writer = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
        
        try:
            for frame in frames:
                video_writer.write(frame)
            logger.info(f"Video saved successfully at: {video_path}")
        except Exception as e:
            logger.error(f"Error while saving video {video_id}: {e}")
        finally:
            video_writer.release()
        
        return video_path

    def remove_video(self, video_id: str):
        """
        Removes a locally saved video file with the specified ID.
        
        Args:
            video_id (str): The unique identifier for the video file.
        
        Returns:
            bool: True if the file was successfully removed, False otherwise.
        """
        video_path = os.path.join(self.storage_directory, f"{video_id}.mp4")
        
        if not os.path.exists(video_path):
            logger.warning(f"Video with ID {video_id} does not exist at path: {video_path}")
            return False
        
        try:
            os.remove(video_path)
            logger.info(f"Video {video_id} successfully removed from {video_path}")
            return True
        except Exception as e:
            logger.error(f"Error while removing video {video_id}: {e}")
            return False

    def list_videos(self):
        """
        Lists all video files in the storage directory.
        
        Returns:
            list: A list of filenames for all saved videos.
        """
        try:
            video_files = [f for f in os.listdir(self.storage_directory) if f.endswith(".mp4")]
            logger.info(f"Found {len(video_files)} video(s) in storage directory.")
            return video_files
        except Exception as e:
            logger.error(f"Error while listing videos: {e}")
            return []

    def get_video_path(self, video_id: str):
        """
        Gets the full path to a saved video file by its ID.
        
        Args:
            video_id (str): The unique identifier for the video file.
        
        Returns:
            str: The path to the video file if it exists, None otherwise.
        """
        video_path = os.path.join(self.storage_directory, f"{video_id}.mp4")
        
        if os.path.exists(video_path):
            logger.info(f"Path for video {video_id}: {video_path}")
            return video_path
        else:
            logger.warning(f"Video with ID {video_id} does not exist at path: {video_path}")
            return None
