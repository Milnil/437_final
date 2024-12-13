import React, { useEffect, useRef } from 'react';

interface MicrophoneStreamProps {
    isStreaming: boolean;
    isMicEnabled: boolean;
    serverUrl: string;
}

export const MicrophoneStream: React.FC<MicrophoneStreamProps> = ({ 
    isStreaming, 
    isMicEnabled, 
    serverUrl 
}) => {
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const websocketRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        let mediaStream: MediaStream | null = null;

        const startMicrophone = async () => {
            try {
                // Get microphone access
                mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                
                // Setup WebSocket connection
                const ws = new WebSocket(`ws://${serverUrl}:5003/mic`);
                websocketRef.current = ws;

                ws.onopen = () => {
                    console.log('Microphone WebSocket connected');
                    
                    // Start recording only after WebSocket is connected
                    const mediaRecorder = new MediaRecorder(mediaStream!, {
                        mimeType: 'audio/webm;codecs=opus'
                    });
                    mediaRecorderRef.current = mediaRecorder;

                    // Send audio data when available
                    mediaRecorder.ondataavailable = (event) => {
                        if (event.data.size > 0 && ws.readyState === WebSocket.OPEN) {
                            ws.send(event.data);
                        }
                    };

                    mediaRecorder.start(100); // Capture in 100ms chunks
                    console.log('Started recording microphone');
                };

                ws.onerror = (error) => {
                    console.error('Microphone WebSocket error:', error);
                };

                ws.onclose = () => {
                    console.log('Microphone WebSocket closed');
                    stopMicrophone();
                };

            } catch (error) {
                console.error('Error accessing microphone:', error);
            }
        };

        const stopMicrophone = () => {
            if (mediaRecorderRef.current) {
                mediaRecorderRef.current.stop();
                mediaRecorderRef.current = null;
            }

            if (websocketRef.current) {
                websocketRef.current.close();
                websocketRef.current = null;
            }

            if (mediaStream) {
                mediaStream.getTracks().forEach(track => track.stop());
                mediaStream = null;
            }
        };

        // Start/stop based on props
        if (isStreaming && isMicEnabled) {
            startMicrophone();
        } else {
            stopMicrophone();
        }

        // Cleanup on unmount
        return () => {
            stopMicrophone();
        };
    }, [isStreaming, isMicEnabled, serverUrl]);

    return null; // This component doesn't render anything
}; 