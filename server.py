import logging
import io
from PIL import Image
from picamera2 import Picamera2
import cv2
import socket
import select
import queue
import time
from object_detector import ObjectDetector  # Import the object detection class

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class CameraSystem:
    def __init__(self, host="192.168.10.59", port=65434):
        logging.info("Initializing CameraSystem class")
        # Initialize Picamera2
        self.picam2 = Picamera2()
        self.configure_camera()
        
        # Server setup
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        logging.info(f"Server listening on {self.host}:{self.port}")
        
        # Object detector initialization
        self.object_detector = ObjectDetector()

    def configure_camera(self):
        logging.info("Configuring camera")
        # Create a configuration suitable for video preview
        video_config = self.picam2.create_still_configuration(main={"size": (320, 240)})
        self.picam2.configure(video_config)
        # Start the camera
        self.picam2.start()
        logging.info("Camera started")

    def capture_image(self):
        # Capture image using Picamera2
        logging.debug("Capturing image")
        try:
            image = self.picam2.capture_array()
            # Convert the image array to JPEG bytes
            img = Image.fromarray(image)
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            image_bytes = img_byte_arr.getvalue()
            logging.debug(f"Image captured, size: {len(image_bytes)} bytes")
            return image_bytes, image  # Return both the raw bytes and the image array
        except Exception as e:
            logging.error(f"Error capturing image: {e}")
            return None, None

    def capture_and_detect_objects(self):
        logging.debug("Capturing image and detecting objects")
        try:
            image_bytes, image = self.capture_image()
            if image is not None:
                detection_result = self.object_detector.detect_objects_from_image(image)
                detected_image = self.object_detector.visualize(image, detection_result)
                # Convert the image array to JPEG bytes
                img = Image.fromarray(detected_image)
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                detected_image_bytes = img_byte_arr.getvalue()
                logging.debug(f"Object detection image captured, size: {len(detected_image_bytes)} bytes")
                return image_bytes, detected_image_bytes
            return None, None
        except Exception as e:
            logging.error(f"Error capturing and detecting objects in image: {e}")
            return None, None

    def cleanup(self):
        logging.info("Cleaning up camera resources")
        self.picam2.stop()
        self.object_detector.close()
        logging.info("Camera cleanup complete")

    def run(self):
        logging.info("Starting server run loop")
        self.server_socket.setblocking(False)
        inputs = [self.server_socket]
        outputs = []
        message_queues = {}

        while inputs:
            try:
                readable, writable, exceptional = select.select(
                    inputs, outputs, inputs, 0.1
                )
            except Exception as e:
                logging.error(f"Select error: {e}")
                break

            for s in readable:
                if s is self.server_socket:
                    client_socket, client_address = s.accept()
                    logging.info(f"New connection from {client_address}")
                    client_socket.setblocking(False)
                    inputs.append(client_socket)
                    message_queues[client_socket] = queue.Queue()
                else:
                    try:
                        data = s.recv(1024).decode().strip()
                        if data:
                            logging.debug(f"Received data: {data}")
                            if data == "capture_normal":
                                image_bytes, _ = self.capture_image()
                                if image_bytes:
                                    message_queues[s].put(image_bytes)
                            elif data == "capture_with_detection":
                                _, detected_image_bytes = self.capture_and_detect_objects()
                                if detected_image_bytes:
                                    message_queues[s].put(detected_image_bytes)
                        else:
                            logging.info(f"Client disconnected: {s.getpeername()}")
                            if s in outputs:
                                outputs.remove(s)
                            inputs.remove(s)
                            s.close()
                            del message_queues[s]
                    except Exception as e:
                        logging.error(f"Error handling client data: {e}")
                        if s in outputs:
                            outputs.remove(s)
                        inputs.remove(s)
                        s.close()
                        del message_queues[s]

            for s in writable:
                try:
                    next_msg = message_queues[s].get_nowait()
                except queue.Empty:
                    outputs.remove(s)
                else:
                    try:
                        s.sendall(next_msg)
                        logging.debug(f"Sent data to {s.getpeername()}")
                    except Exception as e:
                        logging.error(f"Send error: {e}")
                        if s in outputs:
                            outputs.remove(s)
                        inputs.remove(s)
                        s.close()
                        del message_queues[s]

            for s in exceptional:
                logging.error(f"Exception on {s.getpeername()}")
                inputs.remove(s)
                if s in outputs:
                    outputs.remove(s)
                s.close()
                del message_queues[s]

        self.cleanup()

# Main program logic follows:
if __name__ == "__main__":
    logging.info("Program is starting...")
    camera_system = CameraSystem()
    print("Program is starting ... ")
    try:
        camera_system.run()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt caught, exiting program")
        camera_system.cleanup()
