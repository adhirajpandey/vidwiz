import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import config from '../config';
import NoteCard from '../components/NoteCard';
import { useToast } from '../hooks/useToast';
import { FaExclamationTriangle } from 'react-icons/fa';

interface Video {
  video_id: string;
  title: string;
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
          <div className="bg-card rounded-lg shadow-md p-6 mb-6">
            <div className="flex flex-col px-4">
              <h2 className="text-2xl font-bold text-foreground mb-4">{video.title}</h2>
              <a id="watch-button" href={`https://www.youtube.com/watch?v=${video.video_id}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center justify-center w-24 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 transition-colors cursor-pointer">
                Watch
              </a>
            </div>
          </div>
        )}
        <div className="bg-card rounded-lg shadow-md p-6">
          <h3 className="text-xl font-semibold text-foreground mb-4">Your Notes</h3>
          <ol className="space-y-2">
            {notes.map(note => (
              <NoteCard key={note.id} note={note} onUpdate={handleUpdateNote} onDelete={openDeleteModal} />
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}
