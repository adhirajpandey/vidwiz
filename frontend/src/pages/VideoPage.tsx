import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import config from '../config';
import NoteCard from '../components/NoteCard';
import { useToast } from '../hooks/useToast';
import { FaExclamationTriangle, FaPlay, FaEye, FaHeart, FaExternalLinkAlt } from 'react-icons/fa';
import WatchYouTubeButton from '../components/WatchYouTubeButton';

interface Video {
  video_id: string;
  title: string;
  metadata?: {
    channel?: string;
    channel_url?: string;
    uploader?: string;
    uploader_url?: string;
    view_count?: number;
    like_count?: number;
    duration_string?: string;
    upload_date?: string;
    thumbnail?: string;
  };
}

interface Note {
  id: number;
  text: string;
  timestamp: string;
  video_id: string;
  generated_by_ai: boolean;
}

export default function VideoPage() {
  const { videoId } = useParams();
  const [video, setVideo] = useState<Video | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [noteToDelete, setNoteToDelete] = useState<number | null>(null);
  const navigate = useNavigate();
  const { addToast } = useToast();

  useEffect(() => {
    const fetchVideoDetails = async () => {
      const token = localStorage.getItem('token');
      if (token) {
        try {
          const response = await fetch(`${config.API_URL}/videos/${videoId}`, {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          });

          if (response.ok) {
            const data = await response.json();
            setVideo(data);
          } else if (response.status === 401) {
            localStorage.removeItem('token');
            navigate('/login');
          } else {
            navigate('/dashboard');
          }
        } catch (error) {
          console.error('Failed to fetch video details', error);
        }
      }
    };

    const getNotes = async () => {
      const token = localStorage.getItem('token');
      if (token) {
        try {
          const response = await fetch(`${config.API_URL}/notes/${videoId}`, {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          });

          if (response.ok) {
            const data = await response.json();
            setNotes(data.sort((a: Note, b: Note) => timestampToSeconds(a.timestamp) - timestampToSeconds(b.timestamp)));
          } else if (response.status === 401) {
            localStorage.removeItem('token');
            navigate('/login');
          } else {
            setNotes([]);
          }
        } catch (error) {
          console.error('Failed to fetch notes', error);
        }
      }
    };

    fetchVideoDetails();
    getNotes();
  }, [videoId, navigate]);

  const handleUpdateNote = async (noteId: number, newText: string) => {
    const token = localStorage.getItem('token');
    try {
      const response = await fetch(`${config.API_URL}/notes/${noteId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ text: newText }),
      });

      if (response.ok) {
        setNotes(notes.map(n => n.id === noteId ? { ...n, text: newText, generated_by_ai: false } : n));
        addToast({ title: 'Success', message: 'Note updated successfully', type: 'success' });
      } else if (response.status === 401) {
        localStorage.removeItem('token');
        navigate('/login');
      } else {
        addToast({ title: 'Error', message: 'Failed to update note', type: 'error' });
      }
    } catch (error) {
      console.error('Error updating note:', error);
      addToast({ title: 'Error', message: 'Failed to update note', type: 'error' });
    }
  };

  const handleDeleteNote = async () => {
    if (noteToDelete === null) return;
    const token = localStorage.getItem('token');
    try {
      const response = await fetch(`${config.API_URL}/notes/${noteToDelete}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.ok) {
        setNotes(notes.filter(n => n.id !== noteToDelete));
        addToast({ title: 'Success', message: 'Note deleted successfully', type: 'success' });
      } else if (response.status === 401) {
        localStorage.removeItem('token');
        navigate('/login');
        return;
      } else {
        addToast({ title: 'Error', message: 'Failed to delete note', type: 'error' });
      }
    } catch (error) {
      console.error('Error deleting note:', error);
      addToast({ title: 'Error', message: 'Failed to delete note', type: 'error' });
    }
    setShowDeleteModal(false);
    setNoteToDelete(null);
  };

  const openDeleteModal = (noteId: number) => {
    setNoteToDelete(noteId);
    setShowDeleteModal(true);
  };

  function timestampToSeconds(timestamp: string) {
    const parts = timestamp.split(':').map(Number);
    return parts.reduce((seconds, value, index) => seconds + value * Math.pow(60, parts.length - 1 - index), 0);
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg p-6 max-w-sm w-full mx-4 select-none">
            <div className="text-center">
              <div className="text-red-500 text-3xl mb-4">
                <FaExclamationTriangle className="inline-block" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-3">Delete Note</h3>
              <p className="text-sm text-muted-foreground mb-6">Are you sure you want to delete this note? This action cannot be undone.</p>
              <div className="flex justify-center space-x-4">
                <button onClick={() => setShowDeleteModal(false)} className="px-3 py-1.5 text-sm font-medium text-secondary-foreground bg-secondary rounded-md hover:bg-secondary/90 transition-colors cursor-pointer">
                  Cancel
                </button>
                <button onClick={handleDeleteNote} className="px-3 py-1.5 text-sm font-medium text-destructive-foreground bg-destructive rounded-md hover:bg-destructive/90 transition-colors cursor-pointer">
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      <div className="max-w-4xl mx-auto px-6 py-12">
        {video && (
          <div className="relative bg-gradient-to-br from-card via-card to-card/80 rounded-2xl shadow-2xl overflow-hidden mb-8 border border-border/30 select-none">
            {/* Ambient glow effect */}
            <div className="absolute -inset-1 bg-gradient-to-r from-red-500/20 via-transparent to-red-500/20 rounded-2xl blur-xl opacity-50"></div>
            
            <div className="relative">
              {/* Top section with thumbnail */}
              <div className="relative">
                {/* Thumbnail with overlay */}
                <div className="relative group cursor-pointer" onClick={() => window.open(`https://www.youtube.com/watch?v=${video.video_id}`, '_blank')}>
                  <div className="relative overflow-hidden">
                    <img 
                      src={video.metadata?.thumbnail || `https://i.ytimg.com/vi_webp/${video.video_id}/maxresdefault.webp`} 
                      alt={video.title}
                      className="w-full h-48 md:h-56 object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                    {/* Gradient overlay */}
                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent"></div>
                    
                    {/* Play button overlay */}
                    <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-300">
                      <div className="w-16 h-16 rounded-full bg-red-600/90 backdrop-blur-sm flex items-center justify-center shadow-2xl transform scale-90 group-hover:scale-100 transition-transform duration-300">
                        <FaPlay className="w-6 h-6 text-white ml-1" />
                      </div>
                    </div>
                    
                    {/* Duration badge */}
                    {video.metadata?.duration_string && (
                      <div className="absolute bottom-3 right-3 px-2.5 py-1 bg-black/80 backdrop-blur-sm rounded-md text-white text-sm font-medium">
                        {video.metadata.duration_string}
                      </div>
                    )}
                  </div>
                </div>
              </div>
              
              {/* Content section */}
              <div className="p-6">
                {/* Title and Action */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-4">
                  <h2 className="text-xl md:text-2xl font-bold text-foreground leading-tight tracking-tight select-none flex-1">{video.title}</h2>
                  <div className="flex-shrink-0 sm:mt-1 w-full sm:w-auto">
                    <WatchYouTubeButton videoId={video.video_id} variant="red" className="w-full sm:w-auto justify-center" />
                  </div>
                </div>
                
                {/* Stats bar with glassmorphism */}
                {video.metadata && (
                  <div className="flex flex-wrap items-center gap-2 mb-5">
                    {(video.metadata.channel || video.metadata.uploader) && (
                      (video.metadata.channel_url || video.metadata.uploader_url) ? (
                        <a 
                          href={video.metadata.channel_url || video.metadata.uploader_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center px-3 py-1.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-red-500/20 to-red-600/10 text-red-400 border border-red-500/20 hover:from-red-500/30 hover:to-red-600/20 hover:border-red-500/30 transition-all duration-200 cursor-pointer"
                        >
                          {video.metadata.channel || video.metadata.uploader}
                          <FaExternalLinkAlt className="w-2.5 h-2.5 ml-1.5 opacity-60" />
                        </a>
                      ) : (
                        <span className="inline-flex items-center px-3 py-1.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-red-500/20 to-red-600/10 text-red-400 border border-red-500/20 select-none">
                          {video.metadata.channel || video.metadata.uploader}
                        </span>
                      )
                    )}
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 backdrop-blur-sm border border-white/10 select-none">
                      {video.metadata.view_count && (
                        <span className="inline-flex items-center gap-1.5 text-sm text-foreground/70">
                          <FaEye className="w-3.5 h-3.5" />
                          {video.metadata.view_count.toLocaleString()}
                        </span>
                      )}
                      {video.metadata.view_count && video.metadata.like_count && (
                        <span className="text-foreground/30">•</span>
                      )}
                      {video.metadata.like_count && (
                        <span className="inline-flex items-center gap-1.5 text-sm text-foreground/70">
                          <FaHeart className="w-3.5 h-3.5" />
                          {video.metadata.like_count.toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                )}
                

              </div>
            </div>
          </div>
        )}
        <div className="relative bg-gradient-to-br from-card via-card to-card/90 rounded-xl md:rounded-2xl shadow-xl overflow-hidden border border-white/[0.08]">
          {/* Header */}
          <div className="px-4 py-3 md:px-6 md:py-4 border-b border-white/[0.06] bg-white/[0.02] flex items-center justify-between select-none">
            <div className="flex items-center gap-2.5 md:gap-3">
              <div className="w-7 h-7 md:w-8 md:h-8 rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center flex-shrink-0">
                <svg className="w-3.5 h-3.5 md:w-4 md:h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </div>
              <h3 className="text-base md:text-lg font-semibold text-foreground tracking-tight">Your Notes</h3>
            </div>
            <span className="inline-flex items-center px-2 py-0.5 md:px-2.5 md:py-1 rounded-md text-[11px] md:text-xs font-medium bg-white/[0.06] text-foreground/60 border border-white/[0.08]">
              {notes.length} {notes.length === 1 ? 'note' : 'notes'}
            </span>
          </div>
          
          {/* Notes list */}
          <div className="p-3 md:p-5">
            {notes.length === 0 ? (
              <div className="text-center py-10 md:py-14 select-none">
                <div className="w-14 h-14 md:w-16 md:h-16 mx-auto mb-3 md:mb-4 rounded-xl bg-white/[0.04] flex items-center justify-center">
                  <svg className="w-7 h-7 md:w-8 md:h-8 text-foreground/20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <p className="text-foreground/50 text-sm font-medium">No notes yet</p>
                <p className="text-foreground/30 text-xs mt-1">Start adding notes while watching!</p>
              </div>
            ) : (
              <div className="space-y-2 md:space-y-2.5">
                {notes.map(note => (
                  <NoteCard key={note.id} note={note} onUpdate={handleUpdateNote} onDelete={openDeleteModal} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}