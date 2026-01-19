
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import config from '../config';
import { useToast } from '../hooks/useToast';
import { FaExclamationTriangle, FaEye, FaEyeSlash, FaCopy, FaSpinner, FaKey, FaShieldAlt, FaSave, FaPen, FaTimes } from 'react-icons/fa';
import { Settings, Zap, User as UserIcon, Calendar, Mail } from 'lucide-react';

interface UserProfile {
  email: string;
  name?: string;
  profile_image_url?: string;
  ai_notes_enabled: boolean;
  token_exists: boolean;
  created_at?: string;
}

export default function ProfilePage() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [apiToken, setApiToken] = useState<string | null>(null);
  const [showToken, setShowToken] = useState(false);
  const [showRevokeModal, setShowRevokeModal] = useState(false);
  const [isGeneratingToken, setIsGeneratingToken] = useState(false);
  const [isRevokingToken, setIsRevokingToken] = useState(false);
  const [editName, setEditName] = useState('');
  const [isEditingDetails, setIsEditingDetails] = useState(false);
  const [isEditingToken, setIsEditingToken] = useState(false);
  const [isSavingDetails, setIsSavingDetails] = useState(false);
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
          setEditName(data.name || '');
          // Use the actual token from API response
          setApiToken(data.long_term_token || null);
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

  const handleSaveDetails = async () => {
    const token = localStorage.getItem('token');
    if (!token || !user) return;

    setIsSavingDetails(true);
    try {
      const response = await fetch(`${config.API_URL}/user/profile`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ name: editName }),
      });

      if (response.ok) {
        const data = await response.json();
        setUser(data);
        addToast({ title: 'Success', message: 'Profile updated successfully', type: 'success' });
      } else if (response.status === 401) {
        localStorage.removeItem('token');
        navigate('/login');
      } else {
        const errorData = await response.json();
        addToast({ title: 'Error', message: errorData.error || 'Failed to update profile', type: 'error' });
      }
    } catch (error) {
      console.error('Failed to save details', error);
      addToast({ title: 'Error', message: 'Failed to update profile', type: 'error' });
    } finally {
      setIsSavingDetails(false);
    }
  };

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
        } else if (response.status === 401) {
          localStorage.removeItem('token');
          navigate('/login');
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
        } else if (response.status === 401) {
          localStorage.removeItem('token');
          navigate('/login');
          return;
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
        } else if (response.status === 401) {
          localStorage.removeItem('token');
          navigate('/login');
          return;
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
    if (apiToken) {
      navigator.clipboard.writeText(apiToken);
      addToast({ title: 'Copied!', message: 'Token copied to clipboard', type: 'success' });
    } else {
      addToast({ title: 'No Token', message: 'Generate a token first', type: 'error' });
    }
  };

  const handleToggleShowToken = () => {
    if (!apiToken) {
      addToast({ title: 'No Token', message: 'Generate a token first', type: 'error' });
      return;
    }
    setShowToken(!showToken);
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Revoke Modal */}
      {showRevokeModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="relative bg-gradient-to-br from-card via-card to-card/90 rounded-2xl p-6 max-w-sm w-full mx-4 border border-white/[0.08] shadow-2xl select-none">
            {/* Ambient glow */}
            <div className="absolute -inset-1 bg-gradient-to-r from-red-500/20 via-transparent to-red-500/20 rounded-2xl blur-xl opacity-50"></div>
            
            <div className="relative text-center">
              <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-gradient-to-br from-red-500/20 to-red-600/10 border border-red-500/20 flex items-center justify-center">
                <FaExclamationTriangle className="w-6 h-6 text-red-400" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">Revoke API Token</h3>
              <p className="text-sm text-foreground/50 mb-6">Are you sure? This action cannot be undone. Any applications using this token will stop working.</p>
              <div className="flex justify-center gap-3">
                <button 
                  onClick={() => setShowRevokeModal(false)} 
                  className="px-4 py-2 text-sm font-medium bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] hover:border-white/[0.12] rounded-lg text-foreground/70 hover:text-foreground transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button 
                  onClick={handleRevokeToken} 
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-gradient-to-r from-red-600 via-red-500 to-red-600 bg-[length:200%_100%] rounded-lg hover:bg-right transition-all duration-500 shadow-lg shadow-red-500/25 cursor-pointer"
                >
                  {isRevokingToken ? <FaSpinner className="animate-spin w-4 h-4" /> : null}
                  Revoke Token
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-4xl mx-auto px-4 md:px-6 py-8 md:py-12">
        {user && (
          <div className="space-y-12">
            
            {/* Profile Identity Section */}
            <div className="relative select-none">
              <div className="flex flex-col md:flex-row items-center md:items-start gap-6 md:gap-8">
                {/* Large Avatar */}
                <div className="relative">
                  <div className="absolute inset-0 bg-gradient-to-br from-violet-500 to-fuchsia-600 rounded-full blur-xl opacity-30 animate-pulse"></div>
                  <div className="relative w-24 h-24 md:w-32 md:h-32 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-600 p-1 shadow-2xl">
                    {user.profile_image_url ? (
                      <img 
                        src={user.profile_image_url} 
                        alt={user.name || user.email}
                        className="w-full h-full rounded-full object-cover"
                        onError={(e) => {
                          // Fallback to char avatar on image load error
                          e.currentTarget.style.display = 'none';
                          e.currentTarget.nextElementSibling?.classList.remove('hidden');
                        }}
                      />
                    ) : null}
                    <div className={`w-full h-full rounded-full bg-background flex items-center justify-center text-4xl md:text-5xl font-bold text-foreground ${user.profile_image_url ? 'hidden' : ''}`}>
                      {(user.name || user.email).charAt(0).toUpperCase()}
                    </div>
                  </div>
                  <div className="absolute -bottom-2 md:bottom-0 right-0 md:right-2">
                    <div className="w-8 h-8 rounded-full bg-background border-4 border-background flex items-center justify-center">
                      <div className="w-4 h-4 rounded-full bg-green-500 animate-pulse"></div>
                    </div>
                  </div>
                </div>

                {/* Info */}
                <div className="text-center md:text-left pt-2">
                  <h1 className="text-3xl md:text-4xl font-bold tracking-tight mb-3">
                    {user.name || user.email}
                  </h1>
                  <div className="flex flex-col items-center md:items-start gap-2 text-sm text-foreground/60">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/[0.04] border border-white/[0.08]">
                      <UserIcon className="w-3.5 h-3.5" />
                      Free Plan
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/[0.04] border border-white/[0.08]">
                      <Calendar className="w-3.5 h-3.5" />
                      Member since {user.created_at ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'N/A'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Main Content Grid */}
            <div className="grid gap-8">
              
              {/* Settings Group: User Details */}
              <div className="space-y-4">
                <div className="flex items-center justify-between px-1 select-none">
                  <div className="flex items-center gap-2">
                    <UserIcon className="w-4 h-4 text-foreground/40" />
                    <h2 className="text-sm font-semibold text-foreground/40 uppercase tracking-wider">User Details</h2>
                  </div>
                  {!isEditingDetails && (
                    <button
                      onClick={() => setIsEditingDetails(true)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-foreground/60 bg-white/[0.04] border border-white/[0.08] rounded-lg hover:bg-white/[0.08] hover:text-foreground transition-all cursor-pointer"
                    >
                      <FaPen className="w-3 h-3" />
                      Edit
                    </button>
                  )}
                </div>
                
                <div className="relative bg-white/[0.02] border border-white/[0.06] rounded-xl p-5">
                  <div className="space-y-4">
                    {/* Name Field */}
                    <div className="space-y-2">
                      <label htmlFor="name" className="text-sm font-medium text-foreground/70">Name</label>
                      {isEditingDetails ? (
                        <input
                          id="name"
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          placeholder="Enter your name"
                          className="w-full px-4 py-2.5 text-sm bg-black/20 border border-white/[0.08] rounded-lg text-foreground focus:outline-none focus:border-violet-500/50 transition-colors"
                        />
                      ) : (
                        <div className="w-full px-4 py-2.5 text-sm bg-black/10 border border-white/[0.04] rounded-lg text-foreground/80">
                          {user?.name || <span className="text-foreground/40 italic">Not set</span>}
                        </div>
                      )}
                    </div>
                    
                    {/* Email Field (Read-only) */}
                    <div className="space-y-2">
                      <label htmlFor="email" className="text-sm font-medium text-foreground/70 flex items-center gap-2">
                        <Mail className="w-3.5 h-3.5" />
                        Email
                      </label>
                      <div className="w-full px-4 py-2.5 text-sm bg-black/10 border border-white/[0.04] rounded-lg text-foreground/60">
                        {user?.email || ''}
                      </div>
                    </div>
                    
                    {/* Action Buttons (only when editing) */}
                    {isEditingDetails && (
                      <div className="pt-2 flex items-center gap-3">
                        <button
                          onClick={async () => {
                            await handleSaveDetails();
                            setIsEditingDetails(false);
                          }}
                          disabled={isSavingDetails}
                          className="inline-flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-gradient-to-r from-violet-600 via-violet-500 to-violet-600 bg-[length:200%_100%] rounded-lg hover:bg-right transition-all duration-500 shadow-lg shadow-violet-500/20 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                        >
                          {isSavingDetails ? <FaSpinner className="animate-spin w-4 h-4" /> : <FaSave className="w-4 h-4" />}
                          Save
                        </button>
                        <button
                          onClick={() => {
                            setEditName(user?.name || '');
                            setIsEditingDetails(false);
                          }}
                          disabled={isSavingDetails}
                          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-foreground/70 bg-white/[0.04] border border-white/[0.08] rounded-lg hover:bg-white/[0.08] hover:text-foreground transition-all disabled:opacity-50 cursor-pointer"
                        >
                          <FaTimes className="w-4 h-4" />
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Settings Group: Preferences */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 px-1 select-none">
                  <Settings className="w-4 h-4 text-foreground/40" />
                  <h2 className="text-sm font-semibold text-foreground/40 uppercase tracking-wider">Preferences</h2>
                </div>
                
                {/* AI Note Generation Toggle Row */}
                <div className="group relative bg-white/[0.02] hover:bg-white/[0.04] border border-white/[0.06] rounded-xl p-5 transition-colors select-none">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500/20 to-fuchsia-500/20 flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform duration-300">
                        <Zap className="w-5 h-5 text-violet-400" />
                      </div>
                      <div>
                        <h3 className="text-base font-medium text-foreground">AI Note Generation</h3>
                        <p className="text-sm text-foreground/50 mt-1 max-w-lg">
                          Automatically generate summary notes using AI when you save a timestamp. 
                          <span className="hidden sm:inline"> Uses advanced language models to synthesize video content.</span>
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className={`text-xs font-medium transition-colors ${user.ai_notes_enabled ? 'text-violet-400' : 'text-foreground/30'}`}>
                        {user.ai_notes_enabled ? 'On' : 'Off'}
                      </span>
                      <button
                        onClick={handleAiNotesToggle}
                        className={`relative inline-flex h-7 w-12 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                          user.ai_notes_enabled ? 'bg-violet-500' : 'bg-white/[0.1]'
                        }`}
                      >
                        <span
                          className={`pointer-events-none inline-block h-6 w-6 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                            user.ai_notes_enabled ? 'translate-x-5' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Settings Group: Developer */}
              <div className="space-y-4">
                <div className="flex items-center justify-between px-1 select-none">
                  <div className="flex items-center gap-2">
                    <FaKey className="w-4 h-4 text-foreground/40" />
                    <h2 className="text-sm font-semibold text-foreground/40 uppercase tracking-wider">Developer Access</h2>
                  </div>
                  {!isEditingToken && (
                    <button
                      onClick={() => setIsEditingToken(true)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-foreground/60 bg-white/[0.04] border border-white/[0.08] rounded-lg hover:bg-white/[0.08] hover:text-foreground transition-all cursor-pointer"
                    >
                      <FaPen className="w-3 h-3" />
                      Edit
                    </button>
                  )}
                </div>

                {/* API Token Card - Kept as card for complexity */}
                <div className="relative bg-gradient-to-br from-card via-card to-card/90 rounded-xl shadow-xl overflow-hidden border border-white/[0.08] select-none">
                  <div className="p-1 px-1"> {/* Thin padding container for potential future gradient border */}
                    <div className="p-5 md:p-6 space-y-6">
                      <div className="flex md:items-start justify-between gap-4 flex-col md:flex-row">
                        <div className="space-y-1">
                          <h3 className="text-base font-medium text-foreground">Personal Access Token</h3>
                          <p className="text-sm text-foreground/50 max-w-xl">
                            Use this token to authenticate with the VidWiz API for external integrations, mobile apps, or custom scripts. 
                            Treat this like your password.
                          </p>
                        </div>
                        <span className={`self-start inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${
                          user.token_exists 
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                            : 'bg-white/[0.04] text-foreground/50 border border-white/[0.08]'
                        }`}>
                          {user.token_exists ? 'Active' : 'Inactive'}
                        </span>
                      </div>

                      {/* Token Display Area */}
                      <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4">
                        {apiToken ? (
                          <div className="flex flex-col sm:flex-row gap-3">
                            <div className="relative flex-1">
                              <input
                                type={showToken ? 'text' : 'password'}
                                className="w-full pl-10 pr-4 py-2.5 text-xs font-mono bg-black/20 border border-white/[0.08] rounded-lg text-foreground/80 focus:outline-none focus:border-white/[0.2] transition-colors"
                                readOnly
                                value={apiToken === 'hidden_token' ? '••••••••••••••••••••••••••••••••' : apiToken}
                              />
                              <div className="absolute left-3 top-1/2 -translate-y-1/2 text-foreground/30">
                                <FaKey className="w-3.5 h-3.5" />
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <button
                                onClick={handleToggleShowToken}
                                className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-medium bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] rounded-lg text-foreground/70 hover:text-foreground transition-all cursor-pointer"
                              >
                                {showToken ? <FaEyeSlash className="w-3.5 h-3.5" /> : <FaEye className="w-3.5 h-3.5" />}
                                {showToken ? 'Hide' : 'Show'}
                              </button>
                              <button
                                onClick={handleCopyToken}
                                className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold text-white bg-white/[0.1] hover:bg-white/[0.15] border border-white/[0.1] rounded-lg transition-all cursor-pointer"
                              >
                                <FaCopy className="w-3.5 h-3.5" />
                                Copy
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="text-center py-2">
                            <span className="text-sm text-foreground/40 italic">No active token</span>
                          </div>
                        )}
                      </div>

                      {/* Actions Footer */}
                      <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
                        <div className="flex items-center gap-2 text-xs text-amber-500/80 bg-amber-500/5 px-3 py-1.5 rounded-lg border border-amber-500/10">
                          <FaShieldAlt className="w-3 h-3" />
                          <span>Never share this token</span>
                        </div>
                        
                        {isEditingToken && (
                          <div className="flex gap-3 ml-auto">
                            <button
                              onClick={handleGenerateToken}
                              disabled={user.token_exists || isGeneratingToken}
                              className="inline-flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-gradient-to-r from-violet-600 via-violet-500 to-violet-600 bg-[length:200%_100%] rounded-lg hover:bg-right transition-all duration-500 shadow-lg shadow-violet-500/20 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                            >
                              {isGeneratingToken ? <FaSpinner className="animate-spin w-4 h-4" /> : null}
                              Generate New
                            </button>
                            
                            {user.token_exists && (
                               <button
                                onClick={() => setShowRevokeModal(true)}
                                disabled={isRevokingToken}
                                className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium text-red-400 bg-red-500/5 hover:bg-red-500/10 border border-red-500/10 hover:border-red-500/20 rounded-lg transition-all cursor-pointer"
                              >
                                Revoke
                              </button>
                            )}
                            
                            <button
                              onClick={() => setIsEditingToken(false)}
                              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-foreground/70 bg-white/[0.04] border border-white/[0.08] rounded-lg hover:bg-white/[0.08] hover:text-foreground transition-all cursor-pointer"
                            >
                              <FaTimes className="w-4 h-4" />
                              Cancel
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        )}
      </div>
    </div>
  );
}
