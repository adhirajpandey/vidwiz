

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import config from '../config';
import { useToast } from '../hooks/useToast';
import { FaExclamationTriangle, FaEye, FaEyeSlash, FaCopy, FaSpinner } from 'react-icons/fa';

interface UserProfile {
  username: string;
  ai_notes_enabled: boolean;
  token_exists: boolean;
}

export default function ProfilePage() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [apiToken, setApiToken] = useState<string | null>(null);
  const [showToken, setShowToken] = useState(false);
  const [showRevokeModal, setShowRevokeModal] = useState(false);
  const [isGeneratingToken, setIsGeneratingToken] = useState(false);
  const [isRevokingToken, setIsRevokingToken] = useState(false);
  const navigate = useNavigate();
  const { addToast } = useToast();

  const fetchProfile = async () => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const response = await fetch(`${config.API_URL}/user/profile`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          setUser(data);
          if (data.token_exists) {
            setApiToken('hidden_token'); // Indicate token exists but don't show it
          } else {
            setApiToken(null);
          }
        } else {
          localStorage.removeItem('token');
          navigate('/login');
        }
      } catch (error) {
        console.error('Failed to fetch profile', error);
        addToast({ title: 'Error', message: 'Failed to load profile data', type: 'error' });
      }
    }
  };

  useEffect(() => {
    fetchProfile();
  }, [navigate]);

  const handleAiNotesToggle = async () => {
    if (!user) return;
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const response = await fetch(`${config.API_URL}/user/profile`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ ai_notes_enabled: !user.ai_notes_enabled }),
        });

        if (response.ok) {
          const data = await response.json();
          setUser(data);
          addToast({ title: 'Success', message: 'Profile updated successfully', type: 'success' });
        } else {
          addToast({ title: 'Error', message: 'Failed to update AI notes setting', type: 'error' });
        }
      } catch (error) {
        console.error('Failed to update profile', error);
        addToast({ title: 'Error', message: 'Failed to update AI notes setting', type: 'error' });
      }
    }
  };

  const handleGenerateToken = async () => {
    setIsGeneratingToken(true);
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const response = await fetch(`${config.API_URL}/user/token`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          setApiToken(data.token);
          setUser(prev => prev ? { ...prev, token_exists: true } : null);
          addToast({ title: 'Success', message: data.message || 'API token generated successfully', type: 'success' });
        } else {
          const errorData = await response.json();
          addToast({ title: 'Error', message: errorData.error || 'Failed to generate token', type: 'error' });
        }
      } catch (error) {
        console.error('Error generating token:', error);
        addToast({ title: 'Error', message: 'Error generating token', type: 'error' });
      } finally {
        setIsGeneratingToken(false);
      }
    }
  };

  const handleRevokeToken = async () => {
    setIsRevokingToken(true);
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const response = await fetch(`${config.API_URL}/user/token`, {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          setApiToken(null);
          setUser(prev => prev ? { ...prev, token_exists: false } : null);
          addToast({ title: 'Success', message: data.message || 'API token revoked successfully', type: 'success' });
        } else {
          const errorData = await response.json();
          addToast({ title: 'Error', message: errorData.error || 'Failed to revoke token', type: 'error' });
        }
      } catch (error) {
        console.error('Error revoking token:', error);
        addToast({ title: 'Error', message: 'Error revoking token', type: 'error' });
      } finally {
        setIsRevokingToken(false);
        setShowRevokeModal(false);
      }
    }
  };

  const handleCopyToken = () => {
    if (apiToken && apiToken !== 'hidden_token') {
      navigator.clipboard.writeText(apiToken);
      addToast({ title: 'Success', message: 'Token copied to clipboard', type: 'success' });
    } else if (apiToken === 'hidden_token') {
      addToast({ title: 'Info', message: 'Token is hidden. Click show to reveal and copy.', type: 'info' });
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      {showRevokeModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg p-6 max-w-sm w-full mx-4">
            <div className="text-center">
              <div className="text-red-500 text-3xl mb-4">
                <FaExclamationTriangle className="inline-block" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-3">Revoke API Token</h3>
              <p className="text-sm text-muted-foreground mb-6">Are you sure you want to revoke your API token? This action cannot be undone and will immediately invalidate the token. Any applications using this token will stop working.</p>
              <div className="flex justify-center space-x-4">
                <button onClick={() => setShowRevokeModal(false)} className="px-3 py-1.5 text-sm font-medium text-secondary-foreground bg-secondary rounded-md hover:bg-secondary/90 transition-colors cursor-pointer">
                  Cancel
                </button>
                <button onClick={handleRevokeToken} className="px-3 py-1.5 text-sm font-medium text-destructive-foreground bg-destructive rounded-md hover:bg-destructive/90 transition-colors cursor-pointer">
                  {isRevokingToken ? <FaSpinner className="animate-spin mr-1" /> : null}Revoke Token
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      <div className="max-w-4xl mx-auto px-6 py-12">
        <h1 className="text-4xl font-bold">Profile</h1>
        <p className="text-muted-foreground mb-4">Manage your account settings and API access.</p>
        {user && (
          <div className="mt-8 bg-card p-6 rounded-lg shadow-md">
            {/* Username Section */}
            <div className="mb-6">
              <label className="block text-foreground mb-2 font-medium" htmlFor="username">Username</label>
              <input
                className="w-full px-3 py-2 border border-input rounded-lg bg-background text-muted-foreground cursor-not-allowed"
                type="text"
                id="username"
                name="username"
                readOnly
                disabled
                value={user.username}
              />
            </div>

            {/* LLM Note Settings Section */}
            <div className="mb-6">
              <label className="block text-foreground mb-3 font-medium">LLM Note Generation</label>
              <div className="flex items-center justify-between p-4 border border-border rounded-lg bg-card">
                <div>
                  <h3 className="text-sm font-medium text-foreground">Auto-generate AI notes</h3>
                  <p className="text-xs text-muted-foreground">Automatically generate notes based on video timestamp content using AI</p>
                </div>
                <div className="relative">
                  <input
                    type="checkbox"
                    id="llm-notes-toggle"
                    className="sr-only"
                    checked={user.ai_notes_enabled}
                    onChange={handleAiNotesToggle}
                  />
                  <label
                    htmlFor="llm-notes-toggle"
                    className="flex items-center cursor-pointer"
                  >
                    <div className={`block w-14 h-8 rounded-full transition-colors duration-200 ease-in-out ${user.ai_notes_enabled ? 'bg-primary' : 'bg-input'}`}></div>
                    <div className={`dot absolute left-1 top-1 bg-primary-foreground w-6 h-6 rounded-full transition-transform duration-200 ease-in-out ${user.ai_notes_enabled ? 'translate-x-full' : 'translate-x-0'}`}></div>
                  </label>
                </div>
              </div>
            </div>

            {/* API Token Section */}
            <div className="mb-6">
              <label className="block text-foreground mb-3 font-medium">API Access</label>
              <div className="border border-border rounded-lg p-4 bg-card">
                <div className="flex items-center justify-between mb-3 flex-wrap">
                  <div>
                    <h3 className="text-sm font-medium text-foreground">Long-term API Token</h3>
                    <p className="text-xs text-muted-foreground">Generate a token for API access to your VidWiz account</p>
                  </div>
                </div>

                {/* Current Token Display */}
                {apiToken && (
                  <div className="mb-4">
                    <label className="block text-xs text-muted-foreground mb-1">Current Token:</label>
                    <div className="flex items-center space-x-2">
                      <input
                        type={showToken ? 'text' : 'password'}
                        id="current-token"
                        className="flex-1 min-w-0 px-3 py-2 text-xs border border-input rounded bg-background font-mono text-foreground"
                        readOnly
                        value={apiToken === 'hidden_token' ? '••••••••••••••••••••••••••••••••' : apiToken}
                      />
                      <button
                        onClick={() => setShowToken(!showToken)}
                        className="flex-shrink-0 flex items-center gap-1 px-3 py-2 text-xs bg-secondary hover:bg-secondary/90 rounded transition-colors text-secondary-foreground cursor-pointer"
                        type="button"
                      >
                        {showToken ? <FaEyeSlash /> : <FaEye />} {showToken ? 'Hide' : 'Show'}
                      </button>
                      <button
                        onClick={handleCopyToken}
                        className="flex-shrink-0 flex items-center gap-1 px-3 py-2 text-xs bg-red-500 hover:bg-red-600 text-white rounded transition-colors cursor-pointer"
                        type="button"
                      >
                        <FaCopy /> Copy
                      </button>
                    </div>
                  </div>
                )}

                {/* No Token Message */}
                {!apiToken && (
                  <div className="mb-4">
                    <p className="text-sm text-muted-foreground">No API token generated yet.</p>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex space-x-2">
                  <button
                    id="generate-token-btn"
                    onClick={handleGenerateToken}
                    className="w-32 px-4 py-2 text-sm bg-red-500 hover:bg-red-600 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    type="button"
                    disabled={user.token_exists || isGeneratingToken}
                  >
                    {isGeneratingToken ? <FaSpinner className="animate-spin mr-1" /> : null} Generate
                  </button>
                  <button
                    id="revoke-token-btn"
                    onClick={() => setShowRevokeModal(true)}
                    className="w-32 px-4 py-2 text-sm bg-secondary hover:bg-secondary/90 text-secondary-foreground rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    type="button"
                    disabled={!user.token_exists || isRevokingToken}
                  >
                    {isRevokingToken ? <FaSpinner className="animate-spin mr-1" /> : null} Revoke
                  </button>
                </div>

                {/* Token Generation Warning */}
                <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
                  <strong>Long-term API Token:</strong> This token never expires and provides full access to your account. Only one token can exist at a time. Keep it secure and revoke immediately if compromised. You must revoke your existing token before generating a new one.
                </div>
              </div>
            </div>


          </div>
        )}
      </div>
    </div>
  );
}
