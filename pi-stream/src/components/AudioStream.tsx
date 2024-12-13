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
            // Initialize audio context
            audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();

            // Connect WebSocket
            const wsUrl = serverUrl.replace('http://', 'ws://').replace(':8000', ':8001');
            websocketRef.current = new WebSocket(`${wsUrl}/audio`);
            websocketRef.current.binaryType = 'arraybuffer';

            websocketRef.current.onmessage = (event) => {
                if (isMuted || !audioContextRef.current) return;

                const audioData = new Float32Array(event.data);
                const buffer = audioContextRef.current.createBuffer(1, audioData.length, 44100);
                buffer.getChannelData(0).set(audioData);

                const source = audioContextRef.current.createBufferSource();
                source.buffer = buffer;
                source.connect(audioContextRef.current.destination);
                source.start();
            };
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
    }, [isStreaming, serverUrl]);

    return null; // Audio stream doesn't need visual representation
};