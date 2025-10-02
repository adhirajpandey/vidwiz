import { useState } from 'react';
import { FaEdit, FaTrashAlt, FaExternalLinkAlt, FaSave, FaTimes } from 'react-icons/fa';

interface Note {
  id: number;
  text: string;
  timestamp: string;
  video_id: string;
  generated_by_ai: boolean;
}

interface NoteCardProps {
  note: Note;
  onUpdate: (noteId: number, newText: string) => void;
  onDelete: (noteId: number) => void;
}

function timestampToSeconds(timestamp: string) {
  const parts = timestamp.split(':').map(Number);
  return parts.reduce((seconds, value, index) => seconds + value * Math.pow(60, parts.length - 1 - index), 0);
}

export default function NoteCard({ note, onUpdate, onDelete }: NoteCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(note.text);

  const handleSave = () => {
    onUpdate(note.id, editText);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditText(note.text);
    setIsEditing(false);
  };

  return (
    <li className="flex items-center p-2 hover:bg-accent rounded-lg transition-colors border-b last:border-b-0">
      <div className="px-1 py-0.5 flex-shrink-0">
        <a
          href={`https://www.youtube.com/watch?v=${note.video_id}&t=${timestampToSeconds(note.timestamp)}s`}
          target="_blank"
          rel="noopener noreferrer"
          className="font-bold text-foreground text-sm md:text-base"
        >
          {note.timestamp}
        </a>
      </div>
      <span className="px-1 py-0.5 text-bold rounded-full not-italic mr-2" title={note.generated_by_ai ? 'AI Generated' : 'Human Note'}>
        {note.generated_by_ai ? '🤖' : '👤'}
      </span>
      <div className="flex-grow pr-2 md:pr-4">
        {isEditing ? (
          <div className="flex flex-col">
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="w-full p-1 border border-input rounded text-sm md:text-base focus:outline-none focus:border-blue-500 bg-background text-foreground"
              style={{ minHeight: '60px', resize: 'vertical' }}
            />
            <div className="flex space-x-2 mt-2">
              <button onClick={handleSave} className="px-3 py-1 text-xs font-medium text-primary-foreground bg-primary rounded-md hover:bg-primary/90 transition-colors cursor-pointer">
                <FaSave className="inline-block mr-1" />
                Save
              </button>
              <button onClick={handleCancel} className="px-3 py-1 text-xs font-medium text-secondary-foreground bg-secondary rounded-md hover:bg-secondary/90 transition-colors cursor-pointer">
                <FaTimes className="inline-block mr-1" />
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <span className="text-muted-foreground text-sm md:text-base">{note.text}</span>
        )}
      </div>
      <div className="flex items-center space-x-4 text-muted-foreground">
        <a
          href={`https://www.youtube.com/watch?v=${note.video_id}&t=${timestampToSeconds(note.timestamp)}s`}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-red-600 transition-colors"
          title="Open in YouTube"
        >
          <FaExternalLinkAlt />
        </a>
        <button onClick={() => setIsEditing(true)} className="hover:text-blue-600 transition-colors cursor-pointer" title="Edit note">
          <FaEdit />
        </button>
        <button onClick={() => onDelete(note.id)} className="hover:text-red-600 transition-colors cursor-pointer" title="Delete note">
          <FaTrashAlt />
        </button>
      </div>
    </li>
  );
}
