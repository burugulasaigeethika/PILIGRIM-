import React, { useState } from 'react';
import { X, User, Lock, Mail, LogIn, UserPlus, LogOut, Loader2, KeyRound, ArrowLeft, CheckCircle } from 'lucide-react';
import { loginUser, registerUser, forgotPassword } from '../services/api';

export default function AuthModal({ isOpen, onClose, user, onAuthSuccess, onLogout }) {
  const [authMode, setAuthMode] = useState('login'); // 'login' | 'register' | 'forgot'
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setLoading(true);

    try {
      if (authMode === 'register') {
        await registerUser(email, password, name);
        // Automatically login after successful registration
        const loginRes = await loginUser(email, password);
        localStorage.setItem('pilgrim_token', loginRes.access_token);
        onAuthSuccess(loginRes.user, loginRes.access_token);
        onClose();
      } else if (authMode === 'login') {
        const res = await loginUser(email, password);
        localStorage.setItem('pilgrim_token', res.access_token);
        onAuthSuccess(res.user, res.access_token);
        onClose();
      } else if (authMode === 'forgot') {
        const res = await forgotPassword(email);
        setSuccessMsg(res.message || 'If this email is registered, a password reset link has been dispatched.');
      }
    } catch (err) {
      setError(err.message || 'Authentication request failed');
    } finally {
      setLoading(false);
    }
  };

  const getTitle = () => {
    if (user) return 'Your Pilgrim Profile';
    if (authMode === 'register') return 'Create Pilgrim Account';
    if (authMode === 'forgot') return 'Reset Password';
    return 'Welcome to PilgrimAI';
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: 440 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">{getTitle()}</h3>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {user ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: 12, background: '#FAF8F3', borderRadius: 12 }}>
                <div className="user-avatar-circle" style={{ width: 44, height: 44, fontSize: '1.1rem' }}>
                  {user.name ? user.name.charAt(0).toUpperCase() : 'U'}
                </div>
                <div>
                  <h4 style={{ color: '#123C32', fontSize: '1rem', fontWeight: 700 }}>{user.name || 'Pilgrim'}</h4>
                  <span style={{ color: '#6A7870', fontSize: '0.8rem' }}>{user.email}</span>
                </div>
              </div>

              <div style={{ fontSize: '0.82rem', color: '#55655E', lineHeight: 1.5 }}>
                You are securely signed in. Your conversation history, custom itineraries, and preferences are automatically synced across sessions.
              </div>

              <button 
                className="btn-hero-secondary"
                style={{ color: '#D9383A', borderColor: '#F5C6C6', marginTop: 10, alignSelf: 'flex-start' }}
                onClick={() => {
                  localStorage.removeItem('pilgrim_token');
                  onLogout();
                  onClose();
                }}
              >
                <LogOut size={15} style={{ marginRight: 6 }} />
                <span>Log Out</span>
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {authMode === 'register' && (
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#123C32', marginBottom: 4 }}>
                    Full Name
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', background: '#F8F5EE', border: '1px solid #E8E2D5', borderRadius: 8, padding: '6px 12px' }}>
                    <User size={15} color="#8A9890" style={{ marginRight: 8 }} />
                    <input 
                      type="text" 
                      placeholder="e.g. Sai Geethika" 
                      value={name} 
                      onChange={(e) => setName(e.target.value)}
                      required={authMode === 'register'}
                      style={{ border: 'none', background: 'transparent', outline: 'none', width: '100%', fontSize: '0.86rem' }}
                    />
                  </div>
                </div>
              )}

              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: '#123C32', marginBottom: 4 }}>
                  Email Address
                </label>
                <div style={{ display: 'flex', alignItems: 'center', background: '#F8F5EE', border: '1px solid #E8E2D5', borderRadius: 8, padding: '6px 12px' }}>
                  <Mail size={15} color="#8A9890" style={{ marginRight: 8 }} />
                  <input 
                    type="email" 
                    placeholder="you@domain.com" 
                    value={email} 
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    style={{ border: 'none', background: 'transparent', outline: 'none', width: '100%', fontSize: '0.86rem' }}
                  />
                </div>
              </div>

              {authMode !== 'forgot' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <label style={{ fontSize: '0.78rem', fontWeight: 600, color: '#123C32' }}>
                      Password
                    </label>
                    {authMode === 'login' && (
                      <button
                        type="button"
                        onClick={() => {
                          setAuthMode('forgot');
                          setError(null);
                          setSuccessMsg(null);
                        }}
                        style={{ background: 'none', border: 'none', color: '#D96B24', fontSize: '0.72rem', cursor: 'pointer', fontWeight: 600 }}
                      >
                        Forgot Password?
                      </button>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', background: '#F8F5EE', border: '1px solid #E8E2D5', borderRadius: 8, padding: '6px 12px' }}>
                    <Lock size={15} color="#8A9890" style={{ marginRight: 8 }} />
                    <input 
                      type="password" 
                      placeholder="••••••••" 
                      value={password} 
                      onChange={(e) => setPassword(e.target.value)}
                      required={authMode !== 'forgot'}
                      style={{ border: 'none', background: 'transparent', outline: 'none', width: '100%', fontSize: '0.86rem' }}
                    />
                  </div>
                </div>
              )}

              {error && (
                <div style={{ color: '#D9383A', background: '#FDF2F2', padding: '6px 10px', borderRadius: 6, fontSize: '0.78rem' }}>
                  {error}
                </div>
              )}

              {successMsg && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#2E7D4E', background: '#EEF7EF', border: '1px solid #D5EBD7', padding: '8px 12px', borderRadius: 6, fontSize: '0.78rem' }}>
                  <CheckCircle size={15} />
                  <span>{successMsg}</span>
                </div>
              )}

              <button 
                type="submit" 
                className="btn-hero-primary" 
                disabled={loading}
                style={{ width: '100%', justifyContent: 'center', marginTop: 6 }}
              >
                {loading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : authMode === 'register' ? (
                  <>
                    <UserPlus size={16} />
                    <span>Create Pilgrim Account</span>
                  </>
                ) : authMode === 'forgot' ? (
                  <>
                    <KeyRound size={16} />
                    <span>Send Password Reset Link</span>
                  </>
                ) : (
                  <>
                    <LogIn size={16} />
                    <span>Sign In</span>
                  </>
                )}
              </button>

              <div style={{ textAlign: 'center', marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {authMode === 'forgot' ? (
                  <button
                    type="button"
                    onClick={() => {
                      setAuthMode('login');
                      setError(null);
                      setSuccessMsg(null);
                    }}
                    style={{ background: 'none', border: 'none', color: '#123C32', fontSize: '0.78rem', cursor: 'pointer', fontWeight: 600, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}
                  >
                    <ArrowLeft size={13} />
                    <span>Back to Sign In</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      setAuthMode(authMode === 'register' ? 'login' : 'register');
                      setError(null);
                      setSuccessMsg(null);
                    }}
                    style={{ background: 'none', border: 'none', color: '#D96B24', fontSize: '0.78rem', cursor: 'pointer', fontWeight: 600 }}
                  >
                    {authMode === 'register' ? 'Already have an account? Sign In' : "Don't have an account? Register here"}
                  </button>
                )}
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
