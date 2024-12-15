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
                mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                
                const ws = new WebSocket(`ws://${serverUrl}:5003/mic`);
                websocketRef.current = ws;

                ws.onopen = () => {
                    console.log('Microphone WebSocket connected');
                    
                    audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({
                        sampleRate: 44100,
                    });

                    streamNodeRef.current = audioContextRef.current.createMediaStreamSource(mediaStream!);
                    
                    processorNodeRef.current = audioContextRef.current.createScriptProcessor(4096, 1, 1);
                    
                    processorNodeRef.current.onaudioprocess = (e) => {
                        if (ws.readyState === WebSocket.OPEN && isStreaming && isMicEnabled) {
                            const inputData = e.inputBuffer.getChannelData(0);
                            const int16Data = new Int16Array(inputData.length);
                            
                            for (let i = 0; i < inputData.length; i++) {
                                const s = Math.max(-1, Math.min(1, inputData[i]));
                                int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                            }
                            
                            ws.send(int16Data.buffer);
                        }
                    };

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
            if (mediaStream) {
                mediaStream.getTracks().forEach(track => {
                    track.stop();
                    console.log('Stopping media track:', track.kind);
                });
                mediaStream = null;
            }

            if (processorNodeRef.current) {
                processorNodeRef.current.disconnect();
                processorNodeRef.current = null;
            }

            if (streamNodeRef.current) {
                streamNodeRef.current.disconnect();
                streamNodeRef.current = null;
            }

            if (websocketRef.current) {
                if (websocketRef.current.readyState === WebSocket.OPEN) {
                    websocketRef.current.close(1000, "Microphone disabled");
                }
                websocketRef.current = null;
            }

            if (audioContextRef.current) {
                audioContextRef.current.close().catch(console.error);
                audioContextRef.current = null;
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