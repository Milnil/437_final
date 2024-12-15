import React, { useState, useEffect, useCallback } from 'react';
import { Bell, Camera, Video, VideoOff, Mic, MicOff, Volume2, VolumeX, MoreVertical, History, Bug, Circle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { VideoStream } from './components/VideoStream';
import { AudioStream } from './components/AudioStream';
import { MicrophoneStream } from './components/MicrophoneStream';
import { Dialog, DialogContent } from "@/components/ui/dialog";
import clsx from 'clsx';
import axios from 'axios'
import Modal from './components/Modal';

const VideoPlayerModal = ({ notification, recording, isOpen, onClose }) => {
  if (!recording) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-h-[90vh] overflow-y-auto p-6">
        <div className="w-full space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-semibold">{notification.message}</h3>
              <p className="text-sm text-gray-500">
                {notification.date} at {recording.time} ({recording.duration})
              </p>
            </div>
          </div>

          <div className="w-full rounded-lg overflow-hidden bg-black">
            <div className="aspect-video relative">
              <video
                className="absolute inset-0 w-full h-full object-contain"
                controls
                autoPlay
                src={recording.videoUrl}
              />
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};


const App = () => {
  const [serverUrl, setServerUrl] = useState('192.168.10.59');
  // const [serverUrl, setServerUrl] = useState('localhost');
  const [isStreaming, setIsStreaming] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoEnabled, setIsVideoEnabled] = useState(true);
  const [isMicEnabled, setIsMicEnabled] = useState(true);
  const [showModal, setShowModal] = useState(false); // Controls visibility of the modal
  const [selectedRecordingUrl, setSelectedRecordingUrl] = useState(''); // Stores the URL of the recording to be played
  const [isLoading, setIsLoading] = useState<boolean>(true);



  const handleNotificationClick = (associatedRecording: Recording | undefined) => {
    if (associatedRecording) {
      const recordingUrl = `http://${serverUrl}:5004/videos/${associatedRecording.filename}`;
      console.log('Requesting video from URL:', recordingUrl);
      setSelectedRecordingUrl(recordingUrl); // Set the video URL
      setShowModal(true); // Open the modal
    }
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedRecordingUrl('');
  };

  const [notifications, setNotifications] = useState(() => {
    const saved = localStorage.getItem('doorbell-notifications');
    if (saved) return JSON.parse(saved);

    // Placeholder notifications
    return [
      {
        id: 1,
        type: 'motion',
        time: '10:30',
        message: 'Motion detected',
        date: new Date().toLocaleDateString(),
      },
      {
        id: 2,
        type: 'doorbell',
        time: '09:15',
        message: 'Doorbell pressed',
        date: new Date().toLocaleDateString(),
      },
    ];
  });

  const [recordings, setRecordings] = useState(() => {
    const saved = localStorage.getItem('doorbell-recordings');
    if (saved) return JSON.parse(saved);

    // Placeholder recordings
    return [
      {
        id: 1,
        notificationId: 1,
        date: new Date().toLocaleDateString(),
        time: '10:30',
        duration: '0:15',
        type: 'motion',
        videoUrl: 'https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4' // placeholder video
      }
    ];
  });


  const fetchRecordings = useCallback(async () => {
    try {
      console.log('Fetching recordings from backend...');
      const response = await fetch(`http://${serverUrl}:5004/recordings`);
      if (!response.ok) throw new Error('Failed to fetch recordings');
      
      const data = await response.json();
      console.log('Recordings fetched successfully:', data);
      // Only update recordings if they have changed
      if (JSON.stringify(data.recordings) !== JSON.stringify(recordings)) {
        setRecordings(data.recordings);
      }
    } catch (error) {
      console.error('Error fetching recordings:', error);
    }
  }, [serverUrl, recordings]);

  useEffect(() => {
    fetchRecordings(); // Fetch immediately on component mount
    const intervalId = setInterval(fetchRecordings, 30000); // Poll every 30 seconds

    return () => clearInterval(intervalId); // Cleanup on unmount
  }, [fetchRecordings]);

  const updateNotificationRecordings = useCallback(() => {
    setNotifications((prevNotifications) => 
      prevNotifications.map((notification) => {
        const associatedRecording = recordings.find(
          (recording) => recording.filename.includes(notification.id)
        );
        if (associatedRecording) {
          return {
            ...notification,
            clipUrl: `http://${serverUrl}:5004/videos/${associatedRecording.filename}`
          };
        }
        return notification;
      })
    );
  }, [recordings, serverUrl]);


  useEffect(() => {
    if (recordings.length > 0) {
      console.log('Recordings have changed, updating notification recordings.');
      updateNotificationRecordings();
    } else {
      console.log('No recordings available to update notifications.');
    }
  }, [recordings, updateNotificationRecordings]);



  const [selectedNotification, setSelectedNotification] = useState(null);

  const selectedRecording = selectedNotification
    ? recordings.find(r => r.notificationId === selectedNotification.id)
    : null;

  const handleStreamToggle = () => {
    setIsStreaming(!isStreaming);
  };

  const handlePersonDetected = async (notification) => {
    // Get the current time
    const currentTime = Date.now();

    // Get the timestamp of the last execution from localStorage
    const lastExecutionTime = localStorage.getItem('lastPersonDetectedTime');

    // Check if the function was called in the last 5 minutes (300,000 milliseconds)
    if (lastExecutionTime && currentTime - parseInt(lastExecutionTime, 10) < 0) {
      console.log('handlePersonDetected was called recently. Skipping execution.');
      return; // Exit early if called within the last 5 minutes
    }

    // Store the current time as the last execution time
    localStorage.setItem('lastPersonDetectedTime', currentTime.toString());

    // Update local notifications
    setNotifications(prev => {
      const updated = [notification, ...prev];
      localStorage.setItem('doorbell-notifications', JSON.stringify(updated));
      console.log('Person detected notification added:', notification);
      return updated;
    });

    try {
      const response = await axios.post(`http://${serverUrl}:5005/save-video/${notification.id}`);
    } catch (error) {
      console.error('Error saving video:', error);
    }
  };




  const handleRemoveNotification = (id) => {
      setNotifications(prev => {
          const updated = prev.filter(notification => notification.id !== id);
          localStorage.setItem('doorbell-notifications', JSON.stringify(updated));

          const fileName = `notification_${id}.mp4`;
          fetch(`http://${serverUrl}:5004/videos/${encodeURIComponent(fileName)}`, {
              method: 'DELETE',
          })
          .then(response => {
              if (!response.ok) {
                  throw new Error('Failed to delete the file from the server');
              }
              return response.json();
          })
          .then(data => {
              console.log('File deleted successfully:', data);
          })
          .catch(error => {
              console.error('Error deleting file:', error);
          });

          return updated;
      });
  };



  const handleMotionDetection = () => {
    // Create new notification
    const newNotification = {
      id: Date.now(),
      type: 'motion',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      message: 'Motion detected',
      date: new Date().toLocaleDateString(),
    };

    // Start recording automatically
    handleRecordVideo('motion', newNotification.id);

    // Update notifications
    setNotifications(prev => {
      const updated = [newNotification, ...prev];
      localStorage.setItem('doorbell-notifications', JSON.stringify(updated));
      return updated;
    });
  };

  const [isRecording, setIsRecording] = useState(false);
  const [recordingStartTime, setRecordingStartTime] = useState(null);

  const handleRecordVideo = (type = 'manual', notificationId = null) => {
    if (!isRecording && isStreaming && isVideoEnabled) {
      setIsRecording(true);
      setRecordingStartTime(new Date());

      // Set timeout based on recording type
      const recordingDuration = type === 'motion' ? 15000 : 30000; // 15 seconds for motion, 30 for manual
      setTimeout(() => {
        stopRecording(type, notificationId);
      }, recordingDuration);
    }
  };

  const stopRecording = (type: string, notificationId: number | null = null) => {
    if (isRecording && recordingStartTime) {
      const endTime = new Date();
      const duration = Math.round((endTime.getTime() - recordingStartTime.getTime()) / 1000);

      const newRecording = {
        id: Date.now(),
        notificationId, // Link recording to notification
        date: recordingStartTime.toLocaleDateString(),
        time: recordingStartTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        duration: `${Math.floor(duration / 60)}:${(duration % 60).toString().padStart(2, '0')}`,
        type: type
      };

      setRecordings(prevRecordings => {
        const updatedRecordings = [newRecording, ...prevRecordings];
        localStorage.setItem('doorbell-recordings', JSON.stringify(updatedRecordings));
        return updatedRecordings;
      });

      setIsRecording(false);
      setRecordingStartTime(null);
    }
  };

  const handleDoorbellPress = () => {
    const newNotification = {
      id: Date.now(),
      type: 'doorbell',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      message: 'Doorbell pressed',
      date: new Date().toLocaleDateString(),
    };

    setNotifications(prev => {
      const updated = [newNotification, ...prev];
      localStorage.setItem('doorbell-notifications', JSON.stringify(updated));
      return updated;
    });
  };

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900 p-4 sm:p-6">
      <div className="max-w-7xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex justify-between items-center mb-4">
          <div>
            <h1 className="text-2xl font-bold">Smart Doorbell</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">Security Dashboard</p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="flex items-center gap-2">
                <Badge variant={isStreaming ? "success" : "secondary"} className="h-5">
                  {isStreaming ? "Connected" : "Disconnected"}
                </Badge>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56">
              <div className="p-2">
                <div className="flex gap-2 mb-2">
                  <Input
                    placeholder="Enter Raspberry Pi IP"
                    value={serverUrl}
                    onChange={(e) => setServerUrl(e.target.value)}
                    className="h-8 text-sm"
                  />
                  <Button
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setServerUrl('localhost')}
                    title="Connect to localhost"
                  >
                    <Bug className="h-4 w-4" />
                  </Button>
                </div>
                <Button
                  className="w-full h-8 text-sm"
                  onClick={handleStreamToggle}
                >
                  {isStreaming ? "Disconnect" : "Connect"}
                </Button>
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
          {/* Activity Panel */}
          <div className="lg:col-span-3">
            <Card className="h-full border-0 shadow-md">
              <CardHeader className="pb-3">
                <div className="flex justify-between items-center">
                  <CardTitle className="text-lg">Activity</CardTitle>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button size="icon" className="h-8 w-8">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem>Clear All</DropdownMenuItem>
                      <DropdownMenuItem>Export Log</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[calc(100vh-220px)]">
<div>
      <div className="space-y-2">
        {notifications.map((notification) => {
          const associatedRecording = recordings.find(
            r => r.notificationId === notification.id || r.filename.includes(notification.id)
          );

          return (
            <div
              key={notification.id}
              className={`flex items-center gap-2 p-2 rounded-lg bg-gray-50/50 dark:bg-gray-800/50 border border-gray-100 dark:border-gray-700 
                ${associatedRecording ? 'cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700/70' : ''}`}
              onClick={() => handleNotificationClick(associatedRecording)}
            >
              {notification.type === 'motion' ? (
                <Camera className="h-4 w-4" />
              ) : (
                <Bell className="h-4 w-4" />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{notification.message}</p>
                <p className="text-xs text-gray-500">{notification.time}</p>
                {associatedRecording && (
                  <Badge variant="secondary" className="mt-1 text-xs">
                    Recording Available
                  </Badge>
                )}
              </div>
              <button 
                            className="text-red-500 text-xs font-bold px-1 py-0.5" 
                            onClick={(e) => {
                              e.stopPropagation(); // Prevent triggering the onClick for the parent div
                              handleRemoveNotification(notification.id);
                            }}
                          >
                            ✕
                          </button>
            </div>
          );
        })}
      </div>

      {showModal && (
        <Modal onClose={closeModal}>
<video 
  key={selectedRecordingUrl} 
  src={selectedRecordingUrl} 
  controls 
  autoPlay 
  onLoadedData={() => setIsLoading(false)} 
  onError={() => console.error('Error loading video')}
  width="100%"
/>
{isLoading && <p>Loading...</p>}

        </Modal>
      )}
    </div>

                </ScrollArea>
              </CardContent>
            </Card>
          </div>

          {/* Video Feed */}
          <div className="w-[690px] h-[600px]">

            <Card className="border-0 shadow-md">
              <CardHeader className="pb-3">
                <div className="flex justify-between items-center">
                  <CardTitle className="text-lg">Live Feed</CardTitle>
                  <div className="flex gap-1">
                    <Button
                      size="icon"
                      variant={isMicEnabled ? "default" : "outline"}
                      className="h-8 w-8"
                      onClick={() => setIsMicEnabled(!isMicEnabled)}
                    >
                      {isMicEnabled ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
                    </Button>
                    <Button
                      size="icon"
                      variant={isVideoEnabled ? "default" : "outline"}
                      className="h-8 w-8"
                      onClick={() => setIsVideoEnabled(!isVideoEnabled)}
                    >
                      {isVideoEnabled ? <Video className="h-4 w-4" /> : <VideoOff className="h-4 w-4" />}
                    </Button>
                    <Button
                      size="icon"
                      variant={!isMuted ? "default" : "outline"}
                      className="h-8 w-8"
                      onClick={() => setIsMuted(!isMuted)}
                    >
                      {!isMuted ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="w-[640px] h-[480px] relative bg-gray-900 rounded-b-lg overflow-hidden">
                  <div className="aspect-video">
                    {isStreaming && isVideoEnabled && (
                      <Button
                        size="icon"
                        className={`absolute top-2 left-2 z-10 bg-black/30 hover:bg-black/40 h-8 w-8 ${isRecording ? 'text-red-500' : 'text-white/70'
                          }`}
                        onClick={() => isRecording ? stopRecording('manual') : handleRecordVideo('manual')}
                      >
                        <Circle className={`h-4 w-4 ${isRecording ? 'fill-red-500' : ''}`} />
                      </Button>
                    )}

                    {isStreaming ? (
                      isVideoEnabled ? (
                        <>
                          <VideoStream
                            isStreaming={isStreaming && isVideoEnabled}
                            serverUrl={serverUrl}
                            onPersonDetected={handlePersonDetected}
                            className="w-full h-full object-contain"
                          />
                          <AudioStream
                            isStreaming={isStreaming && !isMuted}
                            serverUrl={serverUrl}
                          />
                          <MicrophoneStream
                            isStreaming={isStreaming && isMicEnabled}
                            serverUrl={serverUrl}
                          />
                        </>
                      ) : (
                        <div className="flex items-center justify-center h-full">
                          <VideoOff className="h-12 w-12 text-gray-400" />
                          <p className="text-gray-400 ml-2">Video Disabled</p>
                        </div>
                      )
                    ) : (
                      <div className="flex items-center justify-center h-full">
                        <p className="text-gray-400">Not Connected</p>
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      <VideoPlayerModal
        notification={selectedNotification}
        recording={selectedRecording}
        isOpen={!!selectedNotification}
        onClose={() => setSelectedNotification(null)}
      />
    </div>
  );
};

export default App;