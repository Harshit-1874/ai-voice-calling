import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  Add as AddIcon,
  Phone as PhoneIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { toast } from 'react-toastify';

// Mock data - replace with actual data from your backend
const initialContacts = [
  {
    id: 1,
    name: 'John Doe',
    phone: '+1 (555) 123-4567',
    email: 'john@example.com',
    lastCall: '2024-02-20 14:30',
    status: 'Active',
  },
  {
    id: 2,
    name: 'Jane Smith',
    phone: '+1 (555) 987-6543',
    email: 'jane@example.com',
    lastCall: '2024-02-20 13:45',
    status: 'Active',
  },
];

interface Contact {
  id: number;
  name: string;
  phone: string;
  email: string;
  lastCall: string;
  status: string;
}

export default function Contacts() {
  const [contacts, setContacts] = useState<Contact[]>(initialContacts);
  const [openDialog, setOpenDialog] = useState(false);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
  });

  const handleOpenDialog = (contact?: Contact) => {
    if (contact) {
      setSelectedContact(contact);
      setFormData({
        name: contact.name,
        phone: contact.phone,
        email: contact.email,
      });
    } else {
      setSelectedContact(null);
      setFormData({
        name: '',
        phone: '',
        email: '',
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setSelectedContact(null);
    setFormData({
      name: '',
      phone: '',
      email: '',
    });
  };

  const handleSaveContact = () => {
    if (!formData.name || !formData.phone) {
      toast.error('Name and phone number are required');
      return;
    }

    if (selectedContact) {
      // Update existing contact
      setContacts((prev) =>
        prev.map((contact) =>
          contact.id === selectedContact.id
            ? { ...contact, ...formData }
            : contact
        )
      );
      toast.success('Contact updated successfully');
    } else {
      // Add new contact
      const newContact: Contact = {
        id: Math.max(...contacts.map((c) => c.id)) + 1,
        ...formData,
        lastCall: 'Never',
        status: 'Active',
      };
      setContacts((prev) => [...prev, newContact]);
      toast.success('Contact added successfully');
    }
    handleCloseDialog();
  };

  const handleDeleteContact = (id: number) => {
    setContacts((prev) => prev.filter((contact) => contact.id !== id));
    toast.success('Contact deleted successfully');
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4">Contacts</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          Add Contact
        </Button>
      </Box>

      <Card>
        <CardContent>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Phone</TableCell>
                  <TableCell>Email</TableCell>
                  <TableCell>Last Call</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {contacts.map((contact) => (
                  <TableRow key={contact.id}>
                    <TableCell>{contact.name}</TableCell>
                    <TableCell>{contact.phone}</TableCell>
                    <TableCell>{contact.email}</TableCell>
                    <TableCell>{contact.lastCall}</TableCell>
                    <TableCell>{contact.status}</TableCell>
                    <TableCell>
                      <IconButton
                        color="primary"
                        onClick={() => handleOpenDialog(contact)}
                      >
                        <EditIcon />
                      </IconButton>
                      <IconButton
                        color="error"
                        onClick={() => handleDeleteContact(contact.id)}
                      >
                        <DeleteIcon />
                      </IconButton>
                      <IconButton color="success">
                        <PhoneIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      <Dialog open={openDialog} onClose={handleCloseDialog}>
        <DialogTitle>
          {selectedContact ? 'Edit Contact' : 'Add New Contact'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              label="Name"
              value={formData.name}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, name: e.target.value }))
              }
              margin="normal"
            />
            <TextField
              fullWidth
              label="Phone"
              value={formData.phone}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, phone: e.target.value }))
              }
              margin="normal"
            />
            <TextField
              fullWidth
              label="Email"
              value={formData.email}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, email: e.target.value }))
              }
              margin="normal"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSaveContact} variant="contained">
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
} 