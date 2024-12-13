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
    const audioContextRef = useRef<AudioContext | null>(null);
    const streamNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
    const processorNodeRef = useRef<ScriptProcessorNode | null>(null);
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
                    
                    // Initialize audio processing
                    audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({
                        sampleRate: 44100,  // Match Pi's sample rate
                    });

                    // Create audio source from microphone
                    streamNodeRef.current = audioContextRef.current.createMediaStreamSource(mediaStream!);
                    
                    // Create script processor for raw audio access
                    processorNodeRef.current = audioContextRef.current.createScriptProcessor(1024, 1, 1);
                    
                    // Process audio data
                    processorNodeRef.current.onaudioprocess = (e) => {
                        if (ws.readyState === WebSocket.OPEN) {
                            const inputData = e.inputBuffer.getChannelData(0);
                            
                            // Convert Float32Array to Int16Array
                            const int16Data = new Int16Array(inputData.length);
                            for (let i = 0; i < inputData.length; i++) {
                                // Convert float to int16
                                const s = Math.max(-1, Math.min(1, inputData[i]));
                                int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                            }
                            
                            ws.send(int16Data.buffer);
                        }
                    };

                    // Connect the audio nodes
                    streamNodeRef.current.connect(processorNodeRef.current);
                    processorNodeRef.current.connect(audioContextRef.current.destination);
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
            if (processorNodeRef.current) {
                processorNodeRef.current.disconnect();
                processorNodeRef.current = null;
            }

            if (streamNodeRef.current) {
                streamNodeRef.current.disconnect();
                streamNodeRef.current = null;
            }

            if (audioContextRef.current) {
                audioContextRef.current.close();
                audioContextRef.current = null;
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

        if (isStreaming && isMicEnabled) {
            startMicrophone();
        } else {
            stopMicrophone();
        }

        return () => {
            stopMicrophone();
        };
    }, [isStreaming, isMicEnabled, serverUrl]);

    return null;
}; 