import React from 'react';
import styled from '@emotion/styled';

const ControlsContainer = styled.div`
  margin: 20px;
  padding: 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  text-align: center;
`;

const Button = styled.button`
  padding: 10px 20px;
  font-size: 16px;
  cursor: pointer;
  margin: 0 10px;
  border: none;
  border-radius: 4px;
  transition: background-color 0.3s;
  color: white;

  &.start {
    background-color: ${props => props.disabled ? '#45a049' : '#4CAF50'};
  }

  &.mute {
    background-color: ${props => props.disabled ? '#da190b' : '#f44336'};
  }
`;

const Status = styled.div<{ isConnected?: boolean }>`
  margin: 10px 0;
  padding: 10px;
  border-radius: 4px;
  background-color: ${props => props.isConnected ? '#dff0d8' : '#f2dede'};
  color: ${props => props.isConnected ? '#3c763d' : '#a94442'};
`;

interface ControlsProps {
    isStreaming: boolean;
    isMuted: boolean;
    onStreamToggle: () => void;
    onMuteToggle: () => void;
}

export const Controls: React.FC<ControlsProps> = ({
    isStreaming,
    isMuted,
    onStreamToggle,
    onMuteToggle,
}) => {
    return (
        <ControlsContainer>
            <h3>Stream Controls</h3>
            <Button className="start" onClick={onStreamToggle}>
                {isStreaming ? 'Stop Stream' : 'Start Stream'}
            </Button>
            <Button className="mute" onClick={onMuteToggle} disabled={!isStreaming}>
                {isMuted ? 'Unmute Audio' : 'Mute Audio'}
            </Button>
            <Status isConnected={isStreaming}>
                {isStreaming ? 'Connected: Streaming audio and video' : 'Stream stopped'}
            </Status>
        </ControlsContainer>
    );
};