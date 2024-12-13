import React, { useEffect, useRef } from 'react';

interface AudioStreamProps {
    isStreaming: boolean;
    isMuted: boolean;
    serverUrl: string;
}

export const AudioStream: React.FC<AudioStreamProps> = ({ isStreaming, isMuted, serverUrl }) => {
    const audioContextRef = useRef<AudioContext | null>(null);
    const websocketRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        if (isStreaming && !audioContextRef.current) {
            try {
                audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
                const wsUrl = `${serverUrl.replace('http://', 'ws://')}:501/audio`;
                websocketRef.current = new WebSocket(wsUrl);

                websocketRef.current.onopen = () => {
                    console.log('Audio WebSocket connection established');
                };

                websocketRef.current.onerror = (error) => {
                    console.error('Audio WebSocket error:', error);
                };

                websocketRef.current.binaryType = 'arraybuffer';

                websocketRef.current.onmessage = async (event) => {
                    if (isMuted || !audioContextRef.current) return;

                    try {
                        const audioBuffer = await audioContextRef.current.decodeAudioData(event.data);
                        const source = audioContextRef.current.createBufferSource();
                        source.buffer = audioBuffer;
                        source.connect(audioContextRef.current.destination);
                        source.start();
                    } catch (error) {
                        console.error('Error playing audio:', error);
                    }
                };
            } catch (error) {
                console.error('Error initializing audio context:', error);
            }
        }

        return () => {
            if (websocketRef.current) {
                websocketRef.current.close();
                websocketRef.current = null;
            }
            if (audioContextRef.current) {
                audioContextRef.current.close();
                audioContextRef.current = null;
            }
        };
    }, [isStreaming, isMuted, serverUrl]);

    return null;
};