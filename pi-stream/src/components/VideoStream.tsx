import React, { useEffect, useRef, useState } from 'react';
import styled from '@emotion/styled';

const VideoContainer = styled.div`
  margin: 20px auto;
  width: fit-content;
`;

const Canvas = styled.canvas`
  position: absolute;
  top: 0;
  left: 0;
  border: 2px solid #333;
  border-radius: 4px;
`;

interface VideoStreamProps {
  isStreaming: boolean;
  serverUrl: string;
  onPersonDetected: (notification: Notification) => void;
}

interface Notification {
  id: number;
  type: string;
  time: string;
  message: string;
  date: string;
}

export const VideoStream: React.FC<VideoStreamProps> = ({ isStreaming, serverUrl, onPersonDetected }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const frameCounterRef = useRef(0);
  const lastClassificationTimeRef = useRef<number>(0);
  const [isModelLoaded, setIsModelLoaded] = useState(false);
  const workerRef = useRef<Worker | null>(null);

  useEffect(() => {
    workerRef.current = new Worker(new URL('../workers/classificationWorker.js', import.meta.url), { type: 'module' });
    workerRef.current.postMessage({ type: 'loadModel' });

    workerRef.current.onmessage = (event) => {
      const { type, predictions } = event.data;

      if (type === 'modelLoaded') {
        setIsModelLoaded(true);
        console.log('Model loaded in worker');
      }

      if (type === 'classificationResult' && predictions) {
        handleClassificationResult(predictions);
      }
    };

    return () => {
      workerRef.current?.terminate();
    };
  }, []);

  useEffect(() => {
    if (isStreaming && isModelLoaded) {
      console.log('Starting WebSocket connection...');
      wsRef.current = new WebSocket(`ws://${serverUrl}:5001/video`);

      wsRef.current.onopen = () => {
        console.log('Video WebSocket connection established');
      };

      wsRef.current.onerror = (error) => {
        console.error('Video WebSocket error:', error);
      };

      wsRef.current.onclose = () => {
        console.log('Video WebSocket connection closed');
      };

      wsRef.current.onmessage = async (event) => {
        try {
          const blob = new Blob([event.data], { type: 'image/jpeg' });
          const imageBitmap = await createImageBitmap(blob);
          const canvasCtx = canvasRef.current!.getContext('2d');
          if (canvasCtx) {
            canvasCtx.drawImage(imageBitmap, 0, 0, canvasRef.current!.width, canvasRef.current!.height);
          }

          // Throttle classification by checking the timestamp
          const now = Date.now();
          const classificationInterval = 2000; // Classify every 2 seconds

          if (now - lastClassificationTimeRef.current > classificationInterval) {
            lastClassificationTimeRef.current = now;

            // Send image data to the worker
            const canvasCtx = canvasRef.current!.getContext('2d');
            if (canvasCtx) {
              const imageData = canvasCtx.getImageData(0, 0, canvasRef.current!.width, canvasRef.current!.height);
              workerRef.current?.postMessage({ type: 'classify', imageData });
            }
          }
        } catch (error) {
          console.error('Error displaying frame:', error);
        }
      };
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [isStreaming, serverUrl, isModelLoaded]);

  const handleClassificationResult = (predictions) => {
    const personKeywords = [
      'person', 'human', 'man', 'woman', 'boy', 'girl', 'adult', 
      'child', 'kid', 'people', 'gaskmask', 'mask', 'gas helmet', 
      'sweatshirt', 'pants', 'shirt', 'sunglasses', 'dark glasses', 
      'shades', 'wig'
    ];

    const personDetected = predictions.some(prediction => 
      personKeywords.some(keyword => prediction.className.toLowerCase().includes(keyword))
    );

    if (personDetected) {
      const notification: Notification = {
        id: Date.now(),
        type: 'person-detected',
        time: new Date().toLocaleTimeString(),
        message: 'Person detected in video footage',
        date: new Date().toLocaleDateString(),
      };
      onPersonDetected(notification);
    }
  };

  if (!isStreaming) return null;

  return (
    <VideoContainer>
      <Canvas
        ref={canvasRef}
        width="640"
        height="480"
      />
    </VideoContainer>
  );
};
