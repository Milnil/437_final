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
                const wsUrl = `${serverUrl.replace('http://', 'ws://')}:6002/audio`;
                websocketRef.current = new WebSocket(wsUrl);
                websocketRef.current.binaryType = 'arraybuffer';

                let firstMessage = true;

                websocketRef.current.onmessage = async (event) => {
                    if (isMuted) return;

                    // First message contains the sample rate
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

                        // Convert Int16 to normalized Float32
                        for (let i = 0; i < audioData.length; i++) {
                            floatData[i] = audioData[i] / 32768.0;
                        }

                        const buffer = audioContextRef.current.createBuffer(
                            1, // mono
                            floatData.length,
                            sampleRateRef.current
                        );
                        buffer.getChannelData(0).set(floatData);

                        // Stop previous source if it exists
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

                websocketRef.current.onerror = (error) => {
                    console.error('WebSocket error:', error);
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
                websocketRef.current.close();
                websocketRef.current = null;
            }
            if (audioContextRef.current) {
                audioContextRef.current.close();
                audioContextRef.current = null;
            }
        };
    }, [isStreaming, serverUrl]);

    // Handle mute/unmute
    useEffect(() => {
        if (audioContextRef.current) {
            audioContextRef.current.resume();
        }
    }, [isMuted]);

    return null;
};