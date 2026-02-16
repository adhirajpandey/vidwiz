import { useState } from 'react';
import { FaEdit, FaTrashAlt, FaExternalLinkAlt, FaSave, FaTimes, FaPlay } from 'react-icons/fa';
import { HiSparkles } from 'react-icons/hi';
import { BiUser } from 'react-icons/bi';

interface Note {
  id: number;
  text: string | null;
  timestamp: string | number;
  video_id: string;
  generated_by_ai: boolean;
}

interface NoteCardProps {
  note: Note;
  userAiNotesEnabled: boolean;
  onUpdate: (noteId: number, newText: string) => void;
  onDelete: (noteId: number) => void;
}

function timestampToSeconds(timestamp: string | number) {
  if (typeof timestamp === 'number') return timestamp;
  const parts = timestamp.split(':').map(Number);
  return parts.reduce((seconds, value, index) => seconds + value * Math.pow(60, parts.length - 1 - index), 0);
}

function formatTimestamp(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function NoteCard({
  note,
  userAiNotesEnabled,
  onUpdate,
  onDelete,
}: NoteCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(note.text || '');
  const isPendingAI =
    userAiNotesEnabled &&
    !note.generated_by_ai &&
    (!note.text || !note.text.trim());

  const handleSave = () => {
    onUpdate(note.id, editText);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditText(note.text || '');
    setIsEditing(false);
  };

  const youtubeUrl = `https://www.youtube.com/watch?v=${note.video_id}&t=${timestampToSeconds(note.timestamp)}s`;

  return (
    <div className="group bg-card hover:bg-muted/30 rounded-lg md:rounded-xl p-3 md:p-4 transition-all duration-200 border border-border hover:border-border/80 select-none">
      <div className="flex items-center gap-3">
        {/* Left side: Timestamp + Source indicator */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Timestamp badge */}
          <a
            href={youtubeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-2 py-1 md:px-2.5 md:py-1.5 rounded-md bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 transition-colors"
          >
            <FaPlay className="w-2 h-2 md:w-2.5 md:h-2.5 text-red-400" />
            <span className="text-xs md:text-sm font-semibold text-red-400 tabular-nums">
              {typeof note.timestamp === 'number' ? formatTimestamp(note.timestamp) : note.timestamp}
            </span>
          </a>
          
          {/* AI/Human indicator - cleaned up design */}
          {isPendingAI ? (
            <div
              className="inline-flex items-center gap-1 px-1.5 py-1 md:px-2 md:py-1 rounded-md bg-amber-500/10 border border-amber-500/20"
              title="AI Processing"
            >
              <span className="text-xs md:text-sm leading-none">⏳</span>
              <span className="text-[10px] md:text-xs font-medium text-amber-400 hidden sm:inline">AI</span>
            </div>
          ) : note.generated_by_ai ? (
            <div 
              className="inline-flex items-center gap-1 px-1.5 py-1 md:px-2 md:py-1 rounded-md bg-gradient-to-r from-violet-500/15 to-fuchsia-500/15 border border-violet-500/25"
              title="AI Generated"
            >
              <HiSparkles className="w-3 h-3 md:w-3.5 md:h-3.5 text-violet-400" />
              <span className="text-[10px] md:text-xs font-medium text-violet-400 hidden sm:inline">AI</span>
            </div>
          ) : (
            <div 
              className="inline-flex items-center gap-1 px-1.5 py-1 md:px-2 md:py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20"
              title="Your Note"
            >
              <BiUser className="w-3 h-3 md:w-3.5 md:h-3.5 text-emerald-400" />
              <span className="text-[10px] md:text-xs font-medium text-emerald-400 hidden sm:inline">You</span>
            </div>
          )}
        </div>
        
        {/* Middle: Note content - takes remaining space */}
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <div className="space-y-2.5">
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                className="w-full p-2.5 md:p-3 rounded-lg bg-muted/50 border border-input text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500/40 focus:ring-1 focus:ring-blue-500/20 transition-all resize-none"
                style={{ minHeight: '70px' }}
                autoFocus
              />
              <div className="flex gap-2">
                <button 
                  onClick={handleSave} 
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors cursor-pointer"
                >
                  <FaSave className="w-2.5 h-2.5" />
                  Save
                </button>
                <button 
                  onClick={handleCancel} 
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-foreground/70 bg-secondary hover:bg-secondary/80 border border-border rounded-md transition-colors cursor-pointer"
                >
                  <FaTimes className="w-2.5 h-2.5" />
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <p className="text-foreground/70 text-sm leading-relaxed break-words">
              {isPendingAI ? 'Generating AI note...' : note.text}
            </p>
          )}
        </div>
        
        {/* Right side: Action buttons */}
        {!isEditing && (
          <div className="flex items-center gap-0.5 flex-shrink-0 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
            <a
              href={youtubeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 md:p-2 rounded-md text-foreground/40 hover:text-red-400 hover:bg-red-500/10 transition-all"
              title="Watch on YouTube"
            >
              <FaExternalLinkAlt className="w-3 h-3 md:w-3.5 md:h-3.5" />
            </a>
            {!isPendingAI && (
              <button 
                onClick={() => setIsEditing(true)} 
                className="p-1.5 md:p-2 rounded-md text-foreground/40 hover:text-blue-400 hover:bg-blue-500/10 transition-all cursor-pointer" 
                title="Edit"
              >
                <FaEdit className="w-3 h-3 md:w-3.5 md:h-3.5" />
              </button>
            )}
            <button 
              onClick={() => onDelete(note.id)} 
              className="p-1.5 md:p-2 rounded-md text-foreground/40 hover:text-red-400 hover:bg-red-500/10 transition-all cursor-pointer" 
              title="Delete"
            >
              <FaTrashAlt className="w-3 h-3 md:w-3.5 md:h-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
