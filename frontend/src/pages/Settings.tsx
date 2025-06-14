import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Grid,
  Switch,
  FormControlLabel,
  Divider,
} from '@mui/material';
import { toast } from 'react-toastify';

interface Settings {
  openaiApiKey: string;
  twilioAccountSid: string;
  twilioAuthToken: string;
  twilioPhoneNumber: string;
  hubspotApiKey: string;
  enableCallRecording: boolean;
  enableAutoDialing: boolean;
  maxConcurrentCalls: number;
}

const initialSettings: Settings = {
  openaiApiKey: '',
  twilioAccountSid: '',
  twilioAuthToken: '',
  twilioPhoneNumber: '',
  hubspotApiKey: '',
  enableCallRecording: true,
  enableAutoDialing: false,
  maxConcurrentCalls: 5,
};

export default function Settings() {
  const [settings, setSettings] = useState<Settings>(initialSettings);
  const [isLoading, setIsLoading] = useState(false);

  const handleSaveSettings = async () => {
    setIsLoading(true);
    try {
      // TODO: Implement actual settings save logic
      await new Promise((resolve) => setTimeout(resolve, 1000)); // Simulate API call
      toast.success('Settings saved successfully');
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (field: keyof Settings) => (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const value =
      event.target.type === 'checkbox'
        ? event.target.checked
        : event.target.type === 'number'
        ? parseInt(event.target.value)
        : event.target.value;
    setSettings((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            API Configuration
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="OpenAI API Key"
                type="password"
                value={settings.openaiApiKey}
                onChange={handleChange('openaiApiKey')}
                margin="normal"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Twilio Account SID"
                value={settings.twilioAccountSid}
                onChange={handleChange('twilioAccountSid')}
                margin="normal"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Twilio Auth Token"
                type="password"
                value={settings.twilioAuthToken}
                onChange={handleChange('twilioAuthToken')}
                margin="normal"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Twilio Phone Number"
                value={settings.twilioPhoneNumber}
                onChange={handleChange('twilioPhoneNumber')}
                margin="normal"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="HubSpot API Key"
                type="password"
                value={settings.hubspotApiKey}
                onChange={handleChange('hubspotApiKey')}
                margin="normal"
              />
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          <Typography variant="h6" gutterBottom>
            Call Settings
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.enableCallRecording}
                    onChange={handleChange('enableCallRecording')}
                  />
                }
                label="Enable Call Recording"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.enableAutoDialing}
                    onChange={handleChange('enableAutoDialing')}
                  />
                }
                label="Enable Auto Dialing"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Max Concurrent Calls"
                type="number"
                value={settings.maxConcurrentCalls}
                onChange={handleChange('maxConcurrentCalls')}
                margin="normal"
                inputProps={{ min: 1, max: 10 }}
              />
            </Grid>
          </Grid>

          <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="contained"
              onClick={handleSaveSettings}
              disabled={isLoading}
            >
              Save Settings
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
} 