import React, { useState } from 'react';
import styled from '@emotion/styled';
import { VideoStream } from './components/VideoStream';
import { AudioStream } from './components/AudioStream';
import { Controls } from './components/Controls';

const AppContainer = styled.div`
  font-family: sans-serif;
  text-align: center;
  background: #f0f0f0;
  min-height: 100vh;
  margin: 0;
  padding: 0;
`;

const Header = styled.header`
  background: #333;
  color: #fff;
  padding: 10px;
`;

const Instructions = styled.div`
  max-width: 600px;
  margin: 40px auto;
  text-align: left;
  background: #fff;
  padding: 20px;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
`;

const App: React.FC = () => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [isMuted, setIsMuted] = useState(false);

  // Update this with your Raspberry Pi's IP address
  const serverUrl = 'http://localhost';

  return (
    <AppContainer>
      <Header>
        <h2>Raspberry Pi Streaming</h2>
      </Header>

      <Controls
        isStreaming={isStreaming}
        isMuted={isMuted}
        onStreamToggle={() => setIsStreaming(!isStreaming)}
        onMuteToggle={() => setIsMuted(!isMuted)}
      />

      <VideoStream
        isStreaming={isStreaming}
        serverUrl={serverUrl}
      />

      <AudioStream
        isStreaming={isStreaming}
        isMuted={isMuted}
        serverUrl={serverUrl}
      />

      <Instructions>
        <h2>Instructions:</h2>
        <ol>
          <li>Click "Start Stream" to begin both video and audio streams</li>
          <li>Use "Mute Audio" to toggle audio on/off</li>
          <li>Check browser console for detailed stream information</li>
        </ol>
        <p><strong>Note:</strong> Audio playback requires user interaction due to browser policies.</p>
      </Instructions>
    </AppContainer>
  );
};

export default App;