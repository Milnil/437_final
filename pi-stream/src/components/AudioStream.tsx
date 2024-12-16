import React, { useEffect, useRef } from 'react';

interface AudioStreamProps {
    isStreaming: boolean;
    isMuted: boolean;
    serverUrl: string;
}

export const AudioStream: React.FC<AudioStreamProps> = ({ isStreaming, isMuted, serverUrl }) => {
    const audioContextRef = useRef<AudioContext | null>(null);
    const websocketRef = useRef<WebSocket | null>(null);
    const bufferSourceRef = useRef<AudioBufferSourceNode | null>(null);
    const sampleRateRef = useRef<number>(44100);

    useEffect(() => {
        if (isStreaming) {
            try {
                const wsUrl = `ws://${serverUrl}:5002/audio`;
                console.log('Attempting to connect to:', wsUrl);
                websocketRef.current = new WebSocket(wsUrl);
                websocketRef.current.binaryType = 'arraybuffer';

                let firstMessage = true;

                websocketRef.current.onopen = () => {
                    console.log('Audio WebSocket connection established');
                };

                websocketRef.current.onerror = (error) => {
                    console.error('Audio WebSocket error:', error);
                };

                websocketRef.current.onclose = () => {
                    console.log('Audio WebSocket connection closed');
                };

                websocketRef.current.onmessage = async (event) => {
                    if (isMuted) return;

                    if (firstMessage) {
                        sampleRateRef.current = parseInt(new TextDecoder().decode(event.data));
                        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({
                            sampleRate: sampleRateRef.current,
                        });
                        console.log(`Audio initialized with sample rate: ${sampleRateRef.current}Hz`);
                        firstMessage = false;
                        return;
                    }

                    if (!audioContextRef.current) return;

                    try {
                        const audioData = new Int16Array(event.data);
                        const floatData = new Float32Array(audioData.length);
                        
                        for (let i = 0; i < audioData.length; i++) {
                            floatData[i] = audioData[i] / 32768.0;
                        }

                        const buffer = audioContextRef.current.createBuffer(
                            1,
                            floatData.length,
                            sampleRateRef.current
                        );
                        buffer.getChannelData(0).set(floatData);

                        if (bufferSourceRef.current) {
                            bufferSourceRef.current.stop();
                        }

                        bufferSourceRef.current = audioContextRef.current.createBufferSource();
                        bufferSourceRef.current.buffer = buffer;
                        bufferSourceRef.current.connect(audioContextRef.current.destination);
                        bufferSourceRef.current.start();
                    } catch (error) {
                        console.error('Error processing audio:', error);
                    }
                };
            } catch (error) {
                console.error('Error initializing audio:', error);
            }
        }

        return () => {
            if (bufferSourceRef.current) {
                bufferSourceRef.current.stop();
                bufferSourceRef.current = null;
            }
            if (websocketRef.current) {
                console.log('Closing audio WebSocket connection');
                websocketRef.current.close();
                websocketRef.current = null;
            }
            if (audioContextRef.current) {
                audioContextRef.current.close();
                audioContextRef.current = null;
            }
        };
    }, [isStreaming, serverUrl, isMuted]);

    return null;
};