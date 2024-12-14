import React, { useEffect, useRef, useState, useCallback } from 'react';
import styled from '@emotion/styled';
import * as mobilenet from '@tensorflow-models/mobilenet';
import * as tf from '@tensorflow/tfjs';
import '@tensorflow/tfjs-backend-wasm';

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
    onPersonDetected: (notification: Notification) => void; // Callback to notify other components
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
    const modelRef = useRef<any>(null);
    const frameCounterRef = useRef(0);
    const lastPredictionTimeRef = useRef(Date.now());
    const [isModelLoaded, setIsModelLoaded] = useState(false);

    useEffect(() => {
        const initializeModels = async () => {
            try {
                await tf.setBackend('webgl');
                await tf.ready();
            } catch (error) {
                try {
                    console.warn('WebGL not available, trying WASM backend', error);
                    await tf.setBackend('wasm');
                    await tf.ready();
                } catch (error) {
                    console.warn('WASM backend not available, trying CPU backend', error);
                    await tf.setBackend('cpu');
                    await tf.ready();
                }
            }

            console.log('Loading MobileNet model...');
            modelRef.current = await mobilenet.load();
            setIsModelLoaded(true);
            console.log('MobileNet model loaded successfully');
        };

        initializeModels(); // Ensure model is initialized as soon as component mounts

        return () => {
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
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
                    console.log('Frame received from WebSocket');
                    const blob = new Blob([event.data], { type: 'image/jpeg' });
                    const imageBitmap = await createImageBitmap(blob);
                    const canvasCtx = canvasRef.current!.getContext('2d');
                    if (canvasCtx) {
                        canvasCtx.drawImage(imageBitmap, 0, 0, canvasRef.current!.width, canvasRef.current!.height);
                    }

                    frameCounterRef.current++;
                    const currentTime = Date.now();

                    if (frameCounterRef.current % 10 === 0 && isModelLoaded && currentTime - lastPredictionTimeRef.current > 5000) {
                        console.log('Running image classification...');
                        lastPredictionTimeRef.current = currentTime;
                        await classifyImage(imageBitmap);
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

    const classifyImage = useCallback(async (imageBitmap) => {
        if (!modelRef.current) {
            console.warn('Model is not loaded yet.');
            return;
        }

        try {
            const imgTensor = tf.browser.fromPixels(imageBitmap).resizeNearestNeighbor([224, 224]).toFloat().expandDims();
            console.log('Running prediction on image...');
            const predictions = await modelRef.current.classify(imgTensor);
            console.log('Predictions: ', predictions);

            const personKeywords = ['person', 'human', 'man', 'woman', 'boy', 'girl', 'adult', 'child', 'kid', 'people', 'gaskmask', 'mask', 'gas helmet', 'sweatshirt','pants', 'shirt'];
            const personDetected = predictions.some(prediction => 
                personKeywords.some(keyword => prediction.className.toLowerCase().includes(keyword))
            );

            if (personDetected) {
                console.log('Person detected!');
                const notification: Notification = {
                    id: Date.now(),
                    type: 'person-detected',
                    time: new Date().toLocaleTimeString(),
                    message: 'Person detected in video footage',
                    date: new Date().toLocaleDateString(),
                };
                console.log('Notification created: ', notification);
                onPersonDetected(notification);
            }

            imgTensor.dispose(); // Clean up the tensor to free memory
        } catch (error) {
            console.error('Error during image classification:', error);
        }
    }, [onPersonDetected]);

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
