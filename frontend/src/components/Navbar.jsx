import React from 'react';
import { Link, useLocation } from 'react-router-dom';

function Navbar() {
  const location = useLocation();

  const isActive = (path) => {
    return location.pathname === path ? 'bg-blue-700' : 'bg-blue-600';
  };

  return (
    <nav className="bg-blue-600 shadow-lg">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <Link to="/" className="text-white text-xl font-bold">
              AI Voice Calling
            </Link>
          </div>
          <div className="flex space-x-4">
            <Link
              to="/"
              className={`${isActive('/')} text-white px-3 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors`}
            >
              Dashboard
            </Link>
            <Link
              to="/logs"
              className={`${isActive('/logs')} text-white px-3 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors`}
            >
              Call Logs
            </Link>
            <Link
              to="/contacts"
              className={`${isActive('/contacts')} text-white px-3 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors`}
            >
              Contacts
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}

export default Navbar; 