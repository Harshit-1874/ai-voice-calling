import React, { useState } from 'react';
import { useCall } from '../context/CallContext';

function Dashboard() {
  const { calls, contacts, loading, error, makeCall } = useCall();
  const [phoneNumber, setPhoneNumber] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await makeCall(phoneNumber);
      setPhoneNumber('');
    } catch (err) {
      console.error('Error making call:', err);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold mb-4">Make a Call</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="phone" className="block text-sm font-medium text-gray-700">
              Phone Number
            </label>
            <input
              type="tel"
              id="phone"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              placeholder="+1234567890"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          >
            {loading ? 'Making Call...' : 'Make Call'}
          </button>
        </form>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-2xl font-bold mb-4">Recent Calls</h2>
          {error && <p className="text-red-500 mb-4">{error}</p>}
          <div className="space-y-4">
            {calls.map((call, index) => (
              <div key={index} className="border-b pb-4">
                <p className="font-medium">Call SID: {call.call_sid}</p>
                <p>Status: {call.status}</p>
                <p>To: {call.to}</p>
                <p>From: {call.from}</p>
              </div>
            ))}
            {calls.length === 0 && <p className="text-gray-500">No recent calls</p>}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-2xl font-bold mb-4">Contacts</h2>
          <div className="space-y-4">
            {contacts.map((contact) => (
              <div key={contact.id} className="border-b pb-4">
                <p className="font-medium">{contact.name}</p>
                <p className="text-gray-600">{contact.phone}</p>
              </div>
            ))}
            {contacts.length === 0 && <p className="text-gray-500">No contacts</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard; 