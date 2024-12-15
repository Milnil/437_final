import cv2
import os
import logging
import asyncio
import subprocess
import collections

logger = logging.getLogger(__name__)

class VideoStorageHandler:
    """
    Handles video frame buffering and storage to save the last 4 seconds of video when an event is triggered.
    """
    def __init__(self, buffer_time=4, fps=30, frame_size=(640, 480), video_path="./videos"):
        """
        Initialize the storage handler with a frame buffer, video encoding properties, and storage path.
        """
        self.buffer_time = buffer_time
        self.fps = fps
        self.frame_size = frame_size
        self.video_path = video_path
        self.frame_buffer = collections.deque(maxlen=buffer_time * fps)  # Circular buffer for 4 seconds of frames
        self.lock = asyncio.Lock()  # Ensure only one save operation happens at a time
        os.makedirs(self.video_path, exist_ok=True)

    def add_frame(self, frame):
        """Add a new frame to the buffer."""
        if frame is None or frame.shape[:2] != (self.frame_size[1], self.frame_size[0]):
            logger.warning(f"Invalid frame dimensions. Expected {self.frame_size}, but got {frame.shape[:2]}")
            return
        self.frame_buffer.append(frame)

    async def save_video_clip(self, filename):
        """
        Save the last 4 seconds of video as an MP4 file.
        This method locks the frame buffer while saving to prevent concurrent modifications.
        """
        async with self.lock:
            if not self.frame_buffer:
                logger.warning(f"No frames available to write for {filename}. Video will not be saved.")
                return

            video_filename = os.path.join(self.video_path, f"{filename}.mp4")
            
            # Set the codec to H.264 (most compatible) or fallback to XVID
            try:
                fourcc = cv2.VideoWriter_fourcc(*'H264')
            except Exception as e:
                logger.error(f"Failed to set H.264 codec, falling back to XVID. Error: {e}")
                fourcc = cv2.VideoWriter_fourcc(*'XVID')

            try:
                logger.info(f"Saving {len(self.frame_buffer)} frames to {video_filename}")
                out = cv2.VideoWriter(video_filename, fourcc, self.fps, self.frame_size)
                
                for i, frame in enumerate(self.frame_buffer):
                    if frame.shape[1] != self.frame_size[0] or frame.shape[0] != self.frame_size[1]:
                        logger.error(f"Frame size mismatch for frame {i}. Expected {self.frame_size} but got {frame.shape[:2]}")
                        continue
                    out.write(frame)

            finally:
                out.release()  # Finalize the file properly

            # Check the file size and log a warning if the file is too small
            self.check_file_size(video_filename)

            # Finalize the MOOV atom using FFmpeg
            try:
                await self.finalize_mp4(video_filename)
            except Exception as e:
                logger.error(f"Error finalizing video {video_filename}: {e}")

    def check_file_size(self, video_filename):
        """Check if the saved video file is large enough to be valid."""
        try:
            file_size = os.path.getsize(video_filename)
            if file_size < 1024:  # Less than 1KB likely means the file is incomplete
                logger.warning(f"Video file {video_filename} is suspiciously small ({file_size} bytes).")
        except Exception as e:
            logger.error(f"Failed to check file size for {video_filename}. Error: {e}")

    async def finalize_mp4(self, video_filename):
        """
        Ensure the MOOV atom is at the start of the file for better streaming performance.
        """
        finalized_filename = video_filename.replace('.mp4', '_finalized.mp4')
        command = ['ffmpeg', '-i', video_filename, '-c', 'copy', '-movflags', '+faststart', finalized_filename]

        try:
            process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"FFmpeg failed to finalize {video_filename}. Error: {stderr.decode().strip()}")
                return

            logger.info(f"Finalized video clip: {finalized_filename}")

        except Exception as e:
            logger.error(f"Error running FFmpeg for {video_filename}: {e}")