# object_detector.py
import time
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from picamera2 import Picamera2

import numpy as np


MARGIN = 10  # pixels
ROW_SIZE = 30  # pixels
FONT_SIZE = 1
FONT_THICKNESS = 1
TEXT_COLOR = (0, 0, 0)  # black


class ObjectDetector:
    def __init__(
        self,
        model_path="efficientdet_lite0.tflite",
        max_results=5,
        score_threshold=0.25,
        detection_confidence_threshold=0.5,
    ):
        # Initialize model parameters
        self.model_path = model_path
        self.max_results = max_results
        self.score_threshold = score_threshold
        self.detection_confidence_threshold = (
            detection_confidence_threshold  # Added parameter
        )
        # Initialize FPS calculation variables
        self.COUNTER = 0
        self.FPS = 0
        self.START_TIME = time.time()
        self.fps_avg_frame_count = 10

        # Initialize Picamera2
        self.picam2 = Picamera2()
        self.picam2.preview_configuration.main.size = (640, 480)
        self.picam2.preview_configuration.main.format = "RGB888"
        self.picam2.preview_configuration.align()
        self.picam2.configure("preview")
        self.picam2.start()

        # Initialize detection variables
        self.detection_result_list = []
        self.detected_objects = set()

        # Initialize the object detection model
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.ObjectDetectorOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            max_results=self.max_results,
            score_threshold=self.score_threshold,
            result_callback=self.save_result,
        )
        self.detector = vision.ObjectDetector.create_from_options(options)

    def save_result(
        self,
        result: vision.ObjectDetectorResult,
        unused_output_image: mp.Image,
        timestamp_ms: int,
    ):
        # Calculate the FPS
        if self.COUNTER % self.fps_avg_frame_count == 0:
            self.FPS = self.fps_avg_frame_count / (time.time() - self.START_TIME)
            self.START_TIME = time.time()

        self.detection_result_list.append(result)
        self.COUNTER += 1

    def detect_objects(self, duration_in_seconds):
        """Run object detection for a specified duration, looking for stop signs or traffic lights."""
        start_time = time.time()
        detection_frame = None

        while (time.time() - start_time) < duration_in_seconds:
            im = self.picam2.capture_array()
            image = cv2.resize(im, (640, 480))
            image = cv2.flip(image, -1)

            # Convert the image from BGR to RGB as required by the TFLite model.
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

            # Run object detection using the model.
            self.detector.detect_async(mp_image, time.time_ns() // 1_000_000)

            if self.detection_result_list:
                current_result = self.detection_result_list.pop(0)

                # Process detections to check for specific objects
                for detection in current_result.detections:
                    for category in detection.categories:
                        # Check if the detection confidence is above the threshold
                        if category.score >= self.detection_confidence_threshold:
                            if category.category_name in [
                                "stop sign",
                                "traffic light",
                                "person",
                            ]:
                                print(
                                    f"Detected {category.category_name} with confidence {category.score:.2f}"
                                )
                                self.detected_objects.add(category.category_name)
                        else:
                            # Optional: Print low-confidence detections for debugging
                            print(
                                f"Ignored {category.category_name} with low confidence {category.score:.2f}"
                            )

                # Optional: Visualize detections
                # Uncomment the following lines to display the detection window
                # current_frame = visualize(image, current_result)
                # cv2.imshow('object_detection', current_frame)
                # if cv2.waitKey(1) == 27:
                #     break

            # Short sleep to prevent excessive CPU usage
            time.sleep(0.01)

        # Clean up
        self.detector.close()
        # cv2.destroyAllWindows()

        # Return the detected objects
        return self.detected_objects

    def visualize(image, detection_result) -> np.ndarray:
        """Draws bounding boxes on the input image and return it.
        Args:
            image: The input RGB image.
            detection_result: The list of all "Detection" entities to be visualized.
        Returns:
            Image with bounding boxes.
        """
        for detection in detection_result.detections:
            # Draw bounding_box
            bbox = detection.bounding_box
            start_point = bbox.origin_x, bbox.origin_y
            end_point = bbox.origin_x + bbox.width, bbox.origin_y + bbox.height
            # Use the orange color for high visibility.
            cv2.rectangle(image, start_point, end_point, (255, 0, 255), 3)

            # Draw label and score
            category = detection.categories[0]
            category_name = category.category_name
            probability = round(category.score, 2)
            result_text = category_name + " (" + str(probability) + ")"
            text_location = (MARGIN + bbox.origin_x, MARGIN + ROW_SIZE + bbox.origin_y)
            cv2.putText(
                image,
                result_text,
                text_location,
                cv2.FONT_HERSHEY_DUPLEX,
                FONT_SIZE,
                TEXT_COLOR,
                FONT_THICKNESS,
                cv2.LINE_AA,
            )

        return image

    def close(self):
        """Release resources."""
        self.picam2.stop()
        # Any other cleanup actions


# Example usage:
if __name__ == "__main__":
    detector = ObjectDetector()
    detected = detector.detect_objects(5)  # Run detection for 5 seconds
    print("Detected objects:", detected)
    detector.close()
