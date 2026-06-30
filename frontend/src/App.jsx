import React from 'react'
import { Routes, Route, Link, Navigate } from 'react-router-dom'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import CloneEditor from './pages/CloneEditor.jsx'
import PublicClone from './pages/PublicClone.jsx'

function isLoggedIn() {
  return !!localStorage.getItem('token');
}

function PrivateRoute({ children }) {
  return isLoggedIn() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <>
      {!window.location.pathname.startsWith('/c/') && (
        <div className="container">
          <nav style={{ marginBottom: 16 }}>
            <Link to="/dashboard">Dashboard</Link>
            {!isLoggedIn() && <Link to="/login">Login / Sign up</Link>}
            {isLoggedIn() && (
              <a
                href="#"
                onClick={(e) => { e.preventDefault(); localStorage.removeItem('token'); window.location.href = '/login'; }}
              >
                Log out
              </a>
            )}
          </nav>
        </div>
      )}
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
        <Route path="/clones/:cloneId" element={<PrivateRoute><CloneEditor /></PrivateRoute>} />
        <Route path="/c/:slug" element={<PublicClone />} />
      </Routes>
    </>
  )
}
