import React, { useEffect, useRef } from 'react';
import styled from '@emotion/styled';

const VideoContainer = styled.div`
  margin: 20px auto;
  width: fit-content;
`;

const Video = styled.img`
  border: 2px solid #333;
  border-radius: 4px;
`;

interface VideoStreamProps {
    isStreaming: boolean;
    serverUrl: string;
}

export const VideoStream: React.FC<VideoStreamProps> = ({ isStreaming, serverUrl }) => {
    const imgRef = useRef<HTMLImageElement>(null);
    const currentBlobUrl = useRef<string | null>(null);
    const wsRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        if (isStreaming) {
            console.log('Attempting to connect to:', `ws://${serverUrl}:5001/video`);
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
                    if (currentBlobUrl.current) {
                        URL.revokeObjectURL(currentBlobUrl.current);
                    }
                    currentBlobUrl.current = URL.createObjectURL(blob);
                    if (imgRef.current) {
                        imgRef.current.src = currentBlobUrl.current;
                    }
                } catch (error) {
                    console.error('Error displaying frame:', error);
                }
            };
        }

        return () => {
            if (wsRef.current) {
                console.log('Closing video WebSocket connection');
                wsRef.current.close();
                wsRef.current = null;
            }
            if (currentBlobUrl.current) {
                URL.revokeObjectURL(currentBlobUrl.current);
                currentBlobUrl.current = null;
            }
        };
    }, [isStreaming, serverUrl]);

    if (!isStreaming) return null;

    return (
        <VideoContainer>
            <Video
                ref={imgRef}
                width="640"
                height="480"
                alt="Video Stream"
            />
        </VideoContainer>
    );
};