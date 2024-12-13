import React, { useState } from 'react';
import {
  Box,
  Container,
  Paper,
  Typography,
  TextField,
  Switch,
  FormControlLabel,
  Stack,
  IconButton,
  Tooltip,
  Alert,
  ThemeProvider,
  createTheme,
  CssBaseline
} from '@mui/material';
import {
  Videocam,
  VideocamOff,
  Mic,
  MicOff,
  VolumeUp,
  VolumeOff
} from '@mui/icons-material';
import { VideoStream } from './components/VideoStream';
import { AudioStream } from './components/AudioStream';
import { MicrophoneStream } from './components/MicrophoneStream';

// Create a dark theme
const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9',
    },
    secondary: {
      main: '#f48fb1',
    },
  },
});

function App() {
  const [serverUrl, setServerUrl] = useState('192.168.10.59');
  const [isStreaming, setIsStreaming] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoEnabled, setIsVideoEnabled] = useState(true);
  const [isMicEnabled, setIsMicEnabled] = useState(true);

  const handleStreamToggle = () => {
    setIsStreaming(!isStreaming);
  };

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Container maxWidth="md" sx={{ py: 4 }}>
        <Stack spacing={3}>
          {/* Header */}
          <Typography variant="h4" component="h1" gutterBottom align="center">
            Raspberry Pi Stream
          </Typography>

          {/* Connection Settings */}
          <Paper sx={{ p: 3 }}>
            <Stack spacing={2}>
              <Typography variant="h6" component="h2">
                Connection Settings
              </Typography>
              <TextField
                label="Server URL"
                variant="outlined"
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                helperText="Enter the Raspberry Pi's IP address or hostname"
                fullWidth
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={isStreaming}
                    onChange={handleStreamToggle}
                    color="primary"
                  />
                }
                label={isStreaming ? "Stop Streaming" : "Start Streaming"}
              />
            </Stack>
          </Paper>

          {/* Stream Controls */}
          <Paper sx={{ p: 3 }}>
            <Stack spacing={2}>
              <Typography variant="h6" component="h2">
                Stream Controls
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
                <Tooltip title={isVideoEnabled ? "Disable Video" : "Enable Video"}>
                  <IconButton
                    onClick={() => setIsVideoEnabled(!isVideoEnabled)}
                    color={isVideoEnabled ? "primary" : "default"}
                    disabled={!isStreaming}
                  >
                    {isVideoEnabled ? <Videocam /> : <VideocamOff />}
                  </IconButton>
                </Tooltip>
                <Tooltip title={isMicEnabled ? "Disable Microphone" : "Enable Microphone"}>
                  <IconButton
                    onClick={() => setIsMicEnabled(!isMicEnabled)}
                    color={isMicEnabled ? "primary" : "default"}
                    disabled={!isStreaming}
                  >
                    {isMicEnabled ? <Mic /> : <MicOff />}
                  </IconButton>
                </Tooltip>
                <Tooltip title={isMuted ? "Unmute Audio" : "Mute Audio"}>
                  <IconButton
                    onClick={() => setIsMuted(!isMuted)}
                    color={isMuted ? "default" : "primary"}
                    disabled={!isStreaming}
                  >
                    {isMuted ? <VolumeOff /> : <VolumeUp />}
                  </IconButton>
                </Tooltip>
              </Box>
            </Stack>
          </Paper>

          {/* Add MicrophoneStream component */}
          <MicrophoneStream 
            isStreaming={isStreaming} 
            isMicEnabled={isMicEnabled} 
            serverUrl={serverUrl}
          />

          {/* Stream Display */}
          {isStreaming && (
            <Paper sx={{ p: 3 }}>
              <Stack spacing={2}>
                <Typography variant="h6" component="h2">
                  Live Stream
                </Typography>
                {isVideoEnabled && (
                  <Box sx={{ display: 'flex', justifyContent: 'center' }}>
                    <VideoStream 
                      isStreaming={isStreaming && isVideoEnabled} 
                      serverUrl={serverUrl} 
                    />
                  </Box>
                )}
                <AudioStream 
                  isStreaming={isStreaming} 
                  isMuted={isMuted} 
                  serverUrl={serverUrl}
                />
              </Stack>
            </Paper>
          )}

          {/* Status Messages */}
          {isStreaming && (
            <Alert severity="info">
              Connected to {serverUrl}
              {!isVideoEnabled && " - Video disabled"}
              {!isMicEnabled && " - Microphone disabled"}
              {isMuted && " - Audio muted"}
            </Alert>
          )}
        </Stack>
      </Container>
    </ThemeProvider>
  );
}

export default App;