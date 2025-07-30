import React, { useState, useEffect } from 'react';
import { Box, Button, TextField, Typography, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper } from '@mui/material';

export default function CallCenter() {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [callStatus, setCallStatus] = useState<any>(null);
  const [hubspotTemp, setHubspotTemp] = useState<any[]>([]);
  const [calling, setCalling] = useState(false);

  // Live status update
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('https://ai-voice-calling-3.onrender.com/call-status');
        const data = await res.json();
        setCallStatus(data);
      } catch {}
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  // Fetch HubspotTempData
  useEffect(() => {
    const fetchTemp = async () => {
      try {
        const res = await fetch('https://ai-voice-calling-3.onrender.com/hubspot-temp');
        const data = await res.json();
        setHubspotTemp(Array.isArray(data) ? data : []);
      } catch {}
    };
    fetchTemp();
    const interval = setInterval(fetchTemp, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleCall = async () => {
    if (!phoneNumber) return;
    setCalling(true);
    try {
      await fetch(`https://ai-voice-calling-3.onrender.com/call/${phoneNumber}`);
    } catch {}
    setCalling(false);
  };

  return (
    <Box sx={{ maxWidth: 600, mx: 'auto', mt: 4 }}>
      <Typography variant="h4" gutterBottom>Call</Typography>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField
          label="Phone Number"
          value={phoneNumber}
          onChange={e => setPhoneNumber(e.target.value)}
          fullWidth
        />
        <Button variant="contained" onClick={handleCall} disabled={calling || !phoneNumber}>
          Call
        </Button>
      </Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6">Live Status</Typography>
        <Paper sx={{ p: 2, minHeight: 60 }}>
          <pre style={{ margin: 0, fontSize: 14 }}>{callStatus ? JSON.stringify(callStatus, null, 2) : 'No status'}</pre>
        </Paper>
      </Box>
      <Typography variant="h6" gutterBottom>Hubspot Temp Table</Typography>
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Hubspot ID</TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Phone</TableCell>
              <TableCell>First Name</TableCell>
              <TableCell>Last Name</TableCell>
              <TableCell>Lead Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {hubspotTemp.map((row, idx) => (
              <TableRow key={row.hubspotId || idx}>
                <TableCell>{row.hubspotId}</TableCell>
                <TableCell>{row.email}</TableCell>
                <TableCell>{row.phone}</TableCell>
                <TableCell>{row.firstName}</TableCell>
                <TableCell>{row.lastName}</TableCell>
                <TableCell>{row.hsLeadStatus}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
} 