import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings' // Import the Settings component
import './App.css'

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleLogin = (e) => {
    e.preventDefault()
    if (email === 'admin@gmail.com' && password === 'admin@123') {
      setIsLoggedIn(true)
      setError('')
    } else {
      setError('Invalid credentials')
    }
  }

  // Login component
  const LoginComponent = () => (
    <div className="flex items-center justify-center min-h-screen w-[90vw] min-w-screen bg-gradient-to-br from-gray-900 via-gray-950 to-gray-900">
      <form
        onSubmit={handleLogin}
        className="bg-gray-900 p-8 rounded-2xl shadow-2xl w-full max-w-sm flex flex-col gap-6 border border-gray-800"
      >
        <div className="flex flex-col items-center mb-2">
          <div className="w-16 h-16 rounded-full bg-blue-700 flex items-center justify-center mb-2">
            <span className="text-white text-2xl font-bold">A</span>
          </div>
          <h2 className="text-2xl font-bold text-white text-center">Admin Login</h2>
          <p className="text-gray-400 text-sm mt-1 text-center">Sign in to access the dashboard</p>
        </div>
        <input
          type="email"
          placeholder="Email"
          className="px-4 py-2 rounded-lg bg-gray-800 text-gray-100 border border-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-700 transition"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          className="px-4 py-2 rounded-lg bg-gray-800 text-gray-100 border border-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-700 transition"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
        />
        {error && <div className="text-red-400 text-sm text-center">{error}</div>}
        <button
          type="submit"
          className="bg-blue-700 hover:bg-blue-800 text-white font-semibold py-2 rounded-lg transition"
        >
          Login
        </button>
      </form>
    </div>
  )

  // Protected Route component
  const ProtectedRoute = ({ children }) => {
    return isLoggedIn ? children : <LoginComponent />
  }

  return (
    <Router>
      <Routes>
        <Route 
          path="/" 
          element={
            <ProtectedRoute>
              <>
                <Navbar />
                <Dashboard />
              </>
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/settings" 
          element={
            <ProtectedRoute>
              <>
                <Navbar />
                <Settings />
              </>
            </ProtectedRoute>
          } 
        />
        {/* Redirect any unknown routes to home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  )
}

export default App