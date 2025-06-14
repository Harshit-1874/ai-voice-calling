import { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Grid,
  TextField,
  CircularProgress,
  Paper,
} from '@mui/material';
import {
  Phone as PhoneIcon,
  PhoneDisabled as PhoneDisabledIcon,
  Mic as MicIcon,
  MicOff as MicOffIcon,
} from '@mui/icons-material';
import { toast } from 'react-toastify';

interface CallStatus {
  isCallActive: boolean;
  isMuted: boolean;
  callDuration: number;
  currentContact: string | null;
}

export default function CallCenter() {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [callStatus, setCallStatus] = useState<CallStatus>({
    isCallActive: false,
    isMuted: false,
    callDuration: 0,
    currentContact: null,
  });
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (callStatus.isCallActive) {
      timer = setInterval(() => {
        setCallStatus((prev) => ({
          ...prev,
          callDuration: prev.callDuration + 1,
        }));
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [callStatus.isCallActive]);

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleMakeCall = async () => {
    if (!phoneNumber) {
      toast.error('Please enter a phone number');
      return;
    }

    setIsLoading(true);
    try {
      // TODO: Implement actual call logic
      setCallStatus({
        isCallActive: true,
        isMuted: false,
        callDuration: 0,
        currentContact: phoneNumber,
      });
      toast.success('Call initiated');
    } catch (error) {
      toast.error('Failed to initiate call');
    } finally {
      setIsLoading(false);
    }
  };

  const handleEndCall = async () => {
    try {
      // TODO: Implement call end logic
      setCallStatus({
        isCallActive: false,
        isMuted: false,
        callDuration: 0,
        currentContact: null,
      });
      toast.success('Call ended');
    } catch (error) {
      toast.error('Failed to end call');
    }
  };

  const handleToggleMute = () => {
    setCallStatus((prev) => ({
      ...prev,
      isMuted: !prev.isMuted,
    }));
    toast.info(callStatus.isMuted ? 'Microphone unmuted' : 'Microphone muted');
  };

  return (
    <Box>
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h5" gutterBottom>
                Make a Call
              </Typography>
              <Box sx={{ mb: 2 }}>
                <TextField
                  fullWidth
                  label="Phone Number"
                  variant="outlined"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  disabled={callStatus.isCallActive}
                />
              </Box>
              <Button
                variant="contained"
                color="primary"
                startIcon={callStatus.isCallActive ? <PhoneDisabledIcon /> : <PhoneIcon />}
                onClick={callStatus.isCallActive ? handleEndCall : handleMakeCall}
                disabled={isLoading}
                fullWidth
              >
                {isLoading ? (
                  <CircularProgress size={24} color="inherit" />
                ) : callStatus.isCallActive ? (
                  'End Call'
                ) : (
                  'Make Call'
                )}
              </Button>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h5" gutterBottom>
                Call Status
              </Typography>
              {callStatus.isCallActive ? (
                <>
                  <Paper
                    elevation={0}
                    sx={{
                      p: 2,
                      mb: 2,
                      bgcolor: 'background.default',
                      borderRadius: 1,
                    }}
                  >
                    <Typography variant="body1">
                      Current Contact: {callStatus.currentContact}
                    </Typography>
                    <Typography variant="h4" sx={{ my: 2 }}>
                      {formatDuration(callStatus.callDuration)}
                    </Typography>
                  </Paper>
                  <Button
                    variant="outlined"
                    color={callStatus.isMuted ? 'error' : 'primary'}
                    startIcon={callStatus.isMuted ? <MicOffIcon /> : <MicIcon />}
                    onClick={handleToggleMute}
                    fullWidth
                  >
                    {callStatus.isMuted ? 'Unmute' : 'Mute'}
                  </Button>
                </>
              ) : (
                <Typography variant="body1" color="text.secondary">
                  No active call
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
} 