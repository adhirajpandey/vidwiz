import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import config from '../config';
import NoteCard from '../components/NoteCard';
import { useToast } from '../hooks/useToast';
import { FaExclamationTriangle, FaPlay, FaEye, FaHeart, FaExternalLinkAlt } from 'react-icons/fa';

interface Video {
  video_id: string;
  title: string;
  metadata?: {
    channel?: string;
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
          <div className="bg-card rounded-lg p-6 max-w-sm w-full mx-4">
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
          <div className="relative bg-gradient-to-br from-card via-card to-card/80 rounded-2xl shadow-2xl overflow-hidden mb-8 border border-border/30">
            {/* Ambient glow effect */}
            <div className="absolute -inset-1 bg-gradient-to-r from-red-500/20 via-transparent to-red-500/20 rounded-2xl blur-xl opacity-50"></div>
            
            <div className="relative">
              {/* Top section with thumbnail */}
              <div className="relative">
                {/* Thumbnail with overlay */}
                {video.metadata?.thumbnail ? (
                  <div className="relative group cursor-pointer" onClick={() => window.open(`https://www.youtube.com/watch?v=${video.video_id}`, '_blank')}>
                    <div className="relative overflow-hidden">
                      <img 
                        src={video.metadata.thumbnail} 
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
                      {video.metadata.duration_string && (
                        <div className="absolute bottom-3 right-3 px-2.5 py-1 bg-black/80 backdrop-blur-sm rounded-md text-white text-sm font-medium">
                          {video.metadata.duration_string}
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="w-full h-48 md:h-56 bg-muted flex items-center justify-center">
                    <FaPlay className="w-12 h-12 text-muted-foreground/30" />
                  </div>
                )}
              </div>
              
              {/* Content section */}
              <div className="p-6">
                {/* Title */}
                <h2 className="text-xl md:text-2xl font-bold text-foreground mb-4 leading-tight">{video.title}</h2>
                
                {/* Stats bar with glassmorphism */}
                {video.metadata && (
                  <div className="flex flex-wrap items-center gap-2 mb-5">
                    {video.metadata.channel && (
                      <span className="inline-flex items-center px-3 py-1.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-red-500/20 to-red-600/10 text-red-400 border border-red-500/20">
                        {video.metadata.channel}
                      </span>
                    )}
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 backdrop-blur-sm border border-white/10">
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
                
                {/* CTA Button */}
                <a 
                  id="watch-button" 
                  href={`https://www.youtube.com/watch?v=${video.video_id}`} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="group/btn inline-flex items-center justify-center gap-2.5 px-6 py-3 text-sm font-semibold text-white bg-gradient-to-r from-red-600 via-red-500 to-red-600 bg-[length:200%_100%] rounded-xl hover:bg-right transition-all duration-500 shadow-lg shadow-red-500/25 hover:shadow-xl hover:shadow-red-500/30 cursor-pointer"
                >
                  <FaPlay className="w-3.5 h-3.5 transition-transform duration-300 group-hover/btn:scale-110" />
                  <span>Watch on YouTube</span>
                  <FaExternalLinkAlt className="w-3 h-3 opacity-60" />
                </a>
              </div>
            </div>
          </div>
        )}
        <div className="bg-card rounded-xl shadow-lg overflow-hidden border border-border/50">
          <div className="px-6 py-4 border-b border-border/50 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-foreground">Your Notes</h3>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
              {notes.length} {notes.length === 1 ? 'note' : 'notes'}
            </span>
          </div>
          <div className="p-6">
            {notes.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">No notes yet. Start adding notes while watching!</p>
            ) : (
              <ol className="space-y-3">
                {notes.map(note => (
                  <NoteCard key={note.id} note={note} onUpdate={handleUpdateNote} onDelete={openDeleteModal} />
                ))}
              </ol>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
