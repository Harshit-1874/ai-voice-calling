import React, { useEffect, useState } from 'react';

interface Stat {
  label: string;
  value: string | number;
  change?: string;
  color?: string;
  icon?: string;
}

interface Agent {
  name: string;
  calls: number;
  rating: number;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stat[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // For call any number
  const [phoneNumber, setPhoneNumber] = useState('');
  const [calling, setCalling] = useState(false);
  const [callResult, setCallResult] = useState<string | null>(null);

  // For call logs
  const [callLogs, setCallLogs] = useState<any[]>([]);
  const [logsLoading, setLogsLoading] = useState(true);
  const [logsError, setLogsError] = useState<string | null>(null);

  // For HubSpot contacts (live, not DB)
  const [hubspotContacts, setHubspotContacts] = useState<any[]>([]);
  const [hubspotLoading, setHubspotLoading] = useState(true);
  const [hubspotError, setHubspotError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch('http://localhost:8000/call-logs');
        if (!res.ok) throw new Error('Failed to fetch dashboard data');
        const data = await res.json();
        // Stats
        const statsArr: Stat[] = [
          { label: 'Total Calls', value: data.statistics?.total_calls ?? '-', icon: '📞', color: 'bg-blue-900 text-blue-200' },
          { label: 'Answered Calls', value: data.statistics?.answered_calls ?? '-', icon: '✅', color: 'bg-green-900 text-green-200' },
          { label: 'Missed Calls', value: data.statistics?.missed_calls ?? '-', icon: '❌', color: 'bg-red-900 text-red-200' },
          { label: 'Average Duration', value: data.statistics?.average_duration ?? '-', icon: '⏱️', color: 'bg-purple-900 text-purple-200' },
        ];
        setStats(statsArr);
        // Agents
        const agentMap: Record<string, { name: string; calls: number; rating: number }> = {};
        (data.call_logs || []).forEach((log: any) => {
          if (log.contact && log.contact.name) {
            if (!agentMap[log.contact.name]) {
              agentMap[log.contact.name] = { name: log.contact.name, calls: 0, rating: 5 };
            }
            agentMap[log.contact.name].calls += 1;
          }
        });
        setAgents(Object.values(agentMap));
        // Call logs
        setCallLogs(data.call_logs || []);
      } catch (e: any) {
        setError(e.message || 'Unknown error');
      } finally {
        setLoading(false);
        setLogsLoading(false);
      }
    };
    fetchData();
  }, []);

  useEffect(() => {
    const fetchHubspotContacts = async () => {
      setHubspotLoading(true);
      setHubspotError(null);
      try {
        const res = await fetch('http://localhost:8000/hubspot/contacts');
        if (!res.ok) throw new Error('Failed to fetch HubSpot contacts');
        const data = await res.json();
        setHubspotContacts(data.contacts || []);
      } catch (e: any) {
        setHubspotError(e.message || 'Unknown error');
      } finally {
        setHubspotLoading(false);
      }
    };
    fetchHubspotContacts();
  }, []);

  const handleCall = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phoneNumber) return;
    setCalling(true);
    setCallResult(null);
    try {
      const res = await fetch(`http://localhost:8000/call/${encodeURIComponent(phoneNumber)}`, { 
        headers:{'Authorization': `Bearer ${localStorage.getItem("token")}`},method: 'POST' });
      if (!res.ok) throw new Error('Failed to initiate call');
      const data = await res.json();
      setCallResult('Call initiated!');
    } catch (e: any) {
      setCallResult(e.message || 'Unknown error');
    } finally {
      setCalling(false);
    }
  };
  
  const navigateToSettings = () => {
    window.location.href = '/settings';
  };

  // Add this function to refresh call logs
  const refreshCallLogs = async () => {
    setLogsLoading(true);
    setLogsError(null);
    try {
      const res = await fetch('http://localhost:8000/call-logs');
      if (!res.ok) throw new Error('Failed to fetch call logs');
      const data = await res.json();
      setCallLogs(data.call_logs || []);
    } catch (e: any) {
      setLogsError(e.message || 'Unknown error');
    } finally {
      setLogsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 flex h-screen w-screen bg-gray-950 text-gray-100 dark bg-dark">
      {/* Sidebar */}
      {/* <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-full">
        {/* <div className="h-20 flex items-center justify-center border-b border-gray-800">
          <span className="font-bold text-xl tracking-wide text-white">Cairo</span>
        </div> */}
        { /* <nav className="flex-1 px-4 py-6 space-y-2">
          <a href="#" className="flex items-center px-3 py-2 rounded-lg bg-blue-900 text-blue-200 font-semibold">
            <span className="mr-3">📈</span> Overview
          </a>
          <a href="#" className="flex items-center px-3 py-2 rounded-lg hover:bg-gray-800">
            <span className="mr-3">📊</span> Call Analytics
          </a>
          <a href="#" className="flex items-center px-3 py-2 rounded-lg hover:bg-gray-800">
            <span className="mr-3">📄</span> Reports
          </a>
          <a href="#" className="flex items-center px-3 py-2 rounded-lg hover:bg-gray-800">
            <span className="mr-3">👥</span> Contacts
          </a>
          <a href="#" className="flex items-center px-3 py-2 rounded-lg hover:bg-gray-800">
            <span className="mr-3">🏢</span> Companies
          </a>
          <a href="#" className="flex items-center px-3 py-2 rounded-lg hover:bg-gray-800">
            <span className="mr-3">🛠️</span> Support
          </a>
          <a href="#" className="flex items-center px-3 py-2 rounded-lg hover:bg-gray-800">
            <span className="mr-3">⚙️</span> Settings
          </a>
        </nav>
        <div className="p-4 border-t border-gray-800 flex items-center">
          <img src="https://randomuser.me/api/portraits/men/31.jpg" alt="User" className="w-10 h-10 rounded-full mr-3" />
          <div>
            <div className="font-semibold text-white">John Doe</div>
            <div className="text-xs text-gray-400">Admin</div>
          </div>
        </div>
      </aside> */}
      {/* Main Content */}
      <main className="flex-1 p-8 overflow-y-auto h-full bg-gray-950 text-gray-100">
        {/* Top bar */}
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Dashboard <span className="ml-1">👋</span></h1>
          <div className="flex items-center space-x-4">
            <input type="text" placeholder="Search..." className="px-3 py-2 border border-gray-700 rounded-lg focus:outline-none focus:ring w-64 bg-gray-900 text-gray-100" />
            <button
              onClick={navigateToSettings}
              className="p-2 rounded-lg hover:bg-gray-800 transition-colors duration-200"
              title="Settings"
            >
              <svg className="w-6 h-6 text-gray-400 hover:text-gray-200" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
            <img src="https://randomuser.me/api/portraits/men/31.jpg" alt="User" className="w-10 h-10 rounded-full" />
          </div>
        </div>

        {/* Call Any Number */}
        <section className="mb-8">
          <form onSubmit={handleCall} className="flex items-center gap-4 mb-2">
            <input
              type="text"
              placeholder="Enter phone number (e.g. +1234567890)"
              value={phoneNumber}
              onChange={e => setPhoneNumber(e.target.value)}
              className="px-3 py-2 border border-gray-700 rounded-lg bg-gray-900 text-gray-100 w-64"
              disabled={calling}
            />
            <button
              type="submit"
              className="px-4 py-2 bg-blue-700 hover:bg-blue-800 rounded text-white font-semibold"
              disabled={calling || !phoneNumber}
            >
              {calling ? 'Calling...' : 'Call'}
            </button>
            {callResult && <span className="ml-4 text-green-400">{callResult}</span>}
          </form>
        </section>

        {/* Stat Cards */}
        {loading ? (
          <div className="text-center py-10">Loading dashboard data...</div>
        ) : error ? (
          <div className="text-center text-red-400 py-10">{error}</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {stats.map((stat) => (
              <div key={stat.label} className={`p-6 rounded-xl shadow-sm flex items-center ${stat.color}`}>
                <div className="text-3xl mr-4">{stat.icon}</div>
                <div>
                  <div className="text-lg font-semibold">{stat.label}</div>
                  <div className="text-2xl font-bold">{stat.value}</div>
                  {stat.change && <div className="text-xs font-medium text-green-400">{stat.change}</div>}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Call Logs Table */}
        <section className="mb-8">
          <div className="flex items-center mb-2">
            <h2 className="text-xl font-bold mr-2">Call Logs</h2>
            <button
              onClick={refreshCallLogs}
              className="px-3 py-1 bg-gray-800 hover:bg-gray-700 rounded text-sm text-gray-200 flex items-center"
              title="Refresh"
              type="button"
              disabled={logsLoading}
            >
              <svg className={`w-4 h-4 mr-1 ${logsLoading ? "animate-spin" : ""}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582M20 20v-5h-.581M5.635 19A9 9 0 1 1 19 5.635" />
              </svg>
              {logsLoading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
          {logsLoading ? (
            <div>Loading call logs...</div>
          ) : logsError ? (
            <div className="text-red-400">{logsError}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm bg-gray-900 rounded-xl">
                <thead>
                  <tr className="text-left text-gray-400">
                    <th className="py-2 px-4">From</th>
                    <th className="py-2 px-4">To</th>
                    <th className="py-2 px-4">Status</th>
                    <th className="py-2 px-4">Start Time</th>
                    <th className="py-2 px-4">End Time</th>
                    <th className="py-2 px-4">Duration (s)</th>
                  </tr>
                </thead>
                <tbody>
                  {callLogs.map((log, idx) => (
                    <tr key={log.id || idx} className="border-t border-gray-800">
                      <td className="py-2 px-4">{log.from_number}</td>
                      <td className="py-2 px-4">{log.to_number}</td>
                      <td className="py-2 px-4">{log.status}</td>
                      <td className="py-2 px-4">{log.start_time}</td>
                      <td className="py-2 px-4">{log.end_time || '-'}</td>
                      <td className="py-2 px-4">{log.duration ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* HubSpot Synced Data (Live) */}
        <section className="mb-8">
          <h2 className="text-xl font-bold mb-2">HubSpot Synced Data <span className="text-xs text-gray-400">(Live from HubSpot API, not DB)</span></h2>
          {hubspotLoading ? (
            <div>Loading HubSpot contacts...</div>
          ) : hubspotError ? (
            <div className="text-red-400">{hubspotError}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm bg-gray-900 rounded-xl">
                <thead>
                  <tr className="text-left text-gray-400">
                    <th className="py-2 px-4">First Name</th>
                    <th className="py-2 px-4">Last Name</th>
                    <th className="py-2 px-4">Email</th>
                    <th className="py-2 px-4">Phone</th>
                    <th className="py-2 px-4">Lead Status</th>
                  </tr>
                </thead>
                <tbody>
                  {hubspotContacts.map((contact, idx) => (
                    <tr key={contact.id || idx} className="border-t border-gray-800">
                      <td className="py-2 px-4">{contact.properties?.firstname || '-'}</td>
                      <td className="py-2 px-4">{contact.properties?.lastname || '-'}</td>
                      <td className="py-2 px-4">{contact.properties?.email || '-'}</td>
                      <td className="py-2 px-4">{contact.properties?.phone || '-'}</td>
                      <td className="py-2 px-4">{contact.properties?.hs_lead_status || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Line Chart Placeholder */}
          {/* <div className="col-span-2 bg-gray-900 rounded-xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="font-semibold text-lg">Overall Call Volume</div>
              <div className="text-xs text-gray-400">This Month</div>
            </div>
            <div className="h-48 flex items-center justify-center text-gray-400">
              {/* Replace with chart.js or similar for real data */}
              { /* <span>Line Chart Placeholder</span>
            </div>
          </div> */}
          {/* Calls Geography Placeholder */}
          {/* <div className="bg-gray-900 rounded-xl shadow-sm p-6">
            <div className="font-semibold text-lg mb-4">Calls Geography</div>
            <div className="h-48 flex items-center justify-center text-gray-400">
              {/* Replace with a map component for real data */}
              { /* <span>Map Placeholder</span>
            </div>
          </div> */}
        </div>
        {/* Best Agents Table */}
        {/* <div className="mt-8 bg-gray-900 rounded-xl shadow-sm p-6">
          <div className="font-semibold text-lg mb-4">Best Agents This Week</div>
          <div className="overflow-x-auto">
            {loading ? (
              <div className="text-center py-4">Loading agents...</div>
            ) : agents.length === 0 ? (
              <div className="text-center py-4 text-gray-400">No agent data available.</div>
            ) : (
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-400">
                    <th className="py-2 px-4">Agent</th>
                    <th className="py-2 px-4">Calls</th>
                    <th className="py-2 px-4">Rating</th>
                  </tr>
                </thead>
                <tbody>
                  {agents.map((agent) => (
                    <tr key={agent.name} className="border-t border-gray-800">
                      <td className="py-2 px-4 font-medium">{agent.name}</td>
                      <td className="py-2 px-4">{agent.calls}</td>
                      <td className="py-2 px-4">{agent.rating}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div> */}
      </main>
    </div>
  );
}