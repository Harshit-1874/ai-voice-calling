import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
} from '@mui/material';
import {
  Phone as PhoneIcon,
  People as PeopleIcon,
  Timer as TimerIcon,
  TrendingUp as TrendingUpIcon,
} from '@mui/icons-material';

// Mock data - replace with actual data from your backend
const stats = [
  { title: 'Total Calls', value: '156', icon: <PhoneIcon /> },
  { title: 'Active Contacts', value: '89', icon: <PeopleIcon /> },
  { title: 'Avg. Call Duration', value: '4m 32s', icon: <TimerIcon /> },
  { title: 'Success Rate', value: '78%', icon: <TrendingUpIcon /> },
];

const recentCalls = [
  {
    id: 1,
    contact: '+1 (555) 123-4567',
    duration: '3m 45s',
    status: 'Completed',
    timestamp: '2024-02-20 14:30',
  },
  {
    id: 2,
    contact: '+1 (555) 987-6543',
    duration: '2m 15s',
    status: 'Completed',
    timestamp: '2024-02-20 13:45',
  },
  {
    id: 3,
    contact: '+1 (555) 456-7890',
    duration: '0m 30s',
    status: 'Missed',
    timestamp: '2024-02-20 12:15',
  },
];

export default function Dashboard() {
  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>

      <Grid container spacing={3}>
        {/* Statistics Cards */}
        {stats.map((stat) => (
          <Grid item xs={12} sm={6} md={3} key={stat.title}>
            <Card>
              <CardContent>
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    mb: 2,
                  }}
                >
                  <Box
                    sx={{
                      backgroundColor: 'primary.main',
                      borderRadius: '50%',
                      p: 1,
                      mr: 2,
                      color: 'white',
                    }}
                  >
                    {stat.icon}
                  </Box>
                  <Typography variant="h6" component="div">
                    {stat.title}
                  </Typography>
                </Box>
                <Typography variant="h4">{stat.value}</Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}

        {/* Recent Calls */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Calls
              </Typography>
              <List>
                {recentCalls.map((call, index) => (
                  <Box key={call.id}>
                    <ListItem>
                      <ListItemIcon>
                        <PhoneIcon color={call.status === 'Completed' ? 'success' : 'error'} />
                      </ListItemIcon>
                      <ListItemText
                        primary={call.contact}
                        secondary={`${call.duration} • ${call.status} • ${call.timestamp}`}
                      />
                    </ListItem>
                    {index < recentCalls.length - 1 && <Divider />}
                  </Box>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
} 