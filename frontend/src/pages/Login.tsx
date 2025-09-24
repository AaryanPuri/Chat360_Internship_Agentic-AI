import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { BASE_URL } from "../lib/api";

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      const response = await fetch(`${BASE_URL.replace(/\/$/,"")}/token/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json();
      if (response.ok && data.access) {
        localStorage.setItem('access_token', data.access);
        localStorage.setItem('refresh_token', data.refresh);
        navigate('/'); // Redirect to home or chat page
      } else {
        setError('Invalid credentials');
      }
    } catch (err) {
      setError('Login failed');
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
      <div style={{ background: 'white', borderRadius: 16, boxShadow: '0 4px 32px rgba(0,0,0,0.12)', padding: 36, width: 350, maxWidth: '90%' }}>
        <h2 style={{ textAlign: 'center', marginBottom: 24, color: '#4F46E5', fontWeight: 700, fontSize: 28 }}>Sign in to Chat360</h2>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 18 }}>
            <label style={{ display: 'block', marginBottom: 6, color: '#333', fontWeight: 500 }}>Username</label>
            <input type="text" value={username} onChange={e => setUsername(e.target.value)} required style={{ width: '100%', padding: 10, borderRadius: 6, border: '1px solid #d1d5db', fontSize: 16, outline: 'none', transition: 'border 0.2s', boxSizing: 'border-box', color: '#222' }} placeholder="Enter your username" />
          </div>
          <div style={{ marginBottom: 18 }}>
            <label style={{ display: 'block', marginBottom: 6, color: '#333', fontWeight: 500 }}>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required style={{ width: '100%', padding: 10, borderRadius: 6, border: '1px solid #d1d5db', fontSize: 16, outline: 'none', transition: 'border 0.2s', boxSizing: 'border-box', color: '#222' }} placeholder="Enter your password" />
          </div>
          {error && <div style={{ color: '#e53e3e', marginBottom: 12, textAlign: 'center', fontWeight: 500 }}>{error}</div>}
          <button type="submit" style={{ width: '100%', background: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%)', color: 'white', padding: 12, border: 'none', borderRadius: 6, fontWeight: 600, fontSize: 17, cursor: 'pointer', boxShadow: '0 2px 8px rgba(102,126,234,0.08)', transition: 'background 0.2s' }}>
            {error ? 'Try Again' : 'Login'}
          </button>
        </form>
        <div style={{ marginTop: 18, textAlign: 'center', color: '#6b7280', fontSize: 14 }}>
          <span>Don't have an account? <Link to="/register" style={{ color: '#4F46E5', fontWeight: 500 }}>Create one</Link></span>
        </div>
        <div style={{ marginTop: 18, textAlign: 'center', color: '#6b7280', fontSize: 14 }}>
          <span>Demo: <b>user1</b> / <b>password</b></span>
        </div>
      </div>
    </div>
  );
};

export default Login;
