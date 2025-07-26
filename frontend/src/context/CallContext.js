import React, { createContext, useContext, useState, useEffect } from 'react';

const CallContext = createContext();

export function useCall() {
  return useContext(CallContext);
}

export function CallProvider({ children }) {
  const [calls, setCalls] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchCalls = async () => {
    try {
      setLoading(true);
      const response = await fetch('https://ai-voice-calling-8f7t.onrender.com/call-status');
      const data = await response.json();
      setCalls(prevCalls => [...prevCalls, data]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchContacts = async () => {
    try {
      setLoading(true);
      const response = await fetch('https://ai-voice-calling-8f7t.onrender.com/contacts');
      if (!response.ok) {
        throw new Error('Failed to fetch contacts');
      }
      const data = await response.json();
      setContacts(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Error fetching contacts:', err);
      setError(err.message);
      setContacts([]);
    } finally {
      setLoading(false);
    }
  };

  const makeCall = async (phoneNumber) => {
    try {
      setLoading(true);
      const response = await fetch(`https://ai-voice-calling-8f7t.onrender.com/call/${phoneNumber}`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to make call');
      }
      const data = await response.json();
      setCalls(prevCalls => [...prevCalls, data]);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContacts();
  }, []);

  const value = {
    calls,
    contacts,
    loading,
    error,
    makeCall,
    fetchCalls,
    fetchContacts,
  };

  return <CallContext.Provider value={value}>{children}</CallContext.Provider>;
} 