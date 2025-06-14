import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import CallLogs from './pages/CallLogs';
import Contacts from './pages/Contacts';
import { CallProvider } from './context/CallContext';

function App() {
  return (
    <CallProvider>
      <Router>
        <div className="min-h-screen bg-gray-100">
          <Navbar />
          <main className="container mx-auto px-4 py-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/logs" element={<CallLogs />} />
              <Route path="/contacts" element={<Contacts />} />
            </Routes>
          </main>
        </div>
      </Router>
    </CallProvider>
  );
}

export default App; 