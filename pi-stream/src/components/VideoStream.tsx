import React from 'react';
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
    if (!isStreaming) return null;

    return (
        <VideoContainer>
            <Video
                src={`${serverUrl}/video`}
                alt="Video Stream"
                width="320"
                height="240"
            />
        </VideoContainer>
    );
};