import React, { useEffect, useRef, useState } from 'react';
import styled from '@emotion/styled';

const TalkButton = styled.button<{ $isActive: boolean }>`
  padding: 15px 30px;
  border-radius: 50px;
  border: none;
  background-color: ${props => props.$isActive ? '#ff4444' : '#4CAF50'};
  color: white;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
  margin: 20px;
  
  &:hover {
    transform: scale(1.05);
  }
  
  &:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
  }
`;

const StatusText = styled.div`
  margin-top: 10px;
  color: #666;
`;

interface PushToTalkProps {
    isEnabled: boolean;
    serverUrl: string;
}

export const PushToTalk: React.FC<PushToTalkProps> = ({ isEnabled, serverUrl }) => {
    const [isTransmitting, setIsTransmitting] = useState(false);
    const [status, setStatus] = useState('Ready');
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const websocketRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        if (!isEnabled) {
            stopTransmitting();
        }
        return () => stopTransmitting();
    }, [isEnabled]);

    const startTransmitting = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;

            // Setup WebSocket connection
            const ws = new WebSocket(`ws://${serverUrl}:5003/mic`);
            websocketRef.current = ws;

            ws.onopen = () => {
                console.log('Microphone WebSocket connected');
                setStatus('Connected');
            };

            ws.onerror = (error) => {
                console.error('Microphone WebSocket error:', error);
                setStatus('Connection Error');
                stopTransmitting();
            };

            ws.onclose = () => {
                console.log('Microphone WebSocket closed');
                setStatus('Disconnected');
                stopTransmitting();
            };

            // Send audio data when available
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && ws.readyState === WebSocket.OPEN) {
                    ws.send(event.data);
                }
            };

            mediaRecorder.start(100); // Capture in 100ms chunks
            setIsTransmitting(true);
            setStatus('Transmitting');

        } catch (error) {
            console.error('Error accessing microphone:', error);
            setStatus('Microphone Error');
        }
    };

    const stopTransmitting = () => {
        if (mediaRecorderRef.current) {
            mediaRecorderRef.current.stop();
            mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
            mediaRecorderRef.current = null;
        }

        if (websocketRef.current) {
            websocketRef.current.close();
            websocketRef.current = null;
        }

        setIsTransmitting(false);
        setStatus('Ready');
    };

    const handleButtonClick = () => {
        if (!isTransmitting) {
            startTransmitting();
        } else {
            stopTransmitting();
        }
    };

    return (
        <div>
            <TalkButton
                onClick={handleButtonClick}
                disabled={!isEnabled}
                $isActive={isTransmitting}
            >
                {isTransmitting ? 'Release to Stop' : 'Push to Talk'}
            </TalkButton>
            <StatusText>{status}</StatusText>
        </div>
    );
}; 