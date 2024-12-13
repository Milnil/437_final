import React, { useEffect, useRef } from 'react';
import styled from '@emotion/styled';

const VideoContainer = styled.div`
  margin: 20px auto;
  width: fit-content;
`;

const Video = styled.video`
  border: 2px solid #333;
  border-radius: 4px;
`;

interface VideoStreamProps {
    isStreaming: boolean;
    serverUrl: string;
}

export const VideoStream: React.FC<VideoStreamProps> = ({ isStreaming, serverUrl }) => {
    const videoRef = useRef<HTMLVideoElement>(null);

    useEffect(() => {
        if (isStreaming && videoRef.current) {
            const ws = new WebSocket(`${serverUrl.replace('http://', 'ws://')}:5002/video`);

            ws.onmessage = async (event) => {
                try {
                    const blob = new Blob([event.data], { type: 'video/webm' });
                    if (videoRef.current) {
                        videoRef.current.src = URL.createObjectURL(blob);
                        await videoRef.current.play();
                    }
                } catch (error) {
                    console.error('Error playing video:', error);
                }
            };

            return () => ws.close();
        }
    }, [isStreaming, serverUrl]);

    if (!isStreaming) return null;

    return (
        <VideoContainer>
            <Video
                ref={videoRef}
                width="640"
                height="480"
                autoPlay
                playsInline
            />
        </VideoContainer>
    );
};