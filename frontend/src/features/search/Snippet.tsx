import type { SnippetPart } from '../../api';

export default function Snippet({ parts }: { parts: SnippetPart[] }) {
  return (
    <p className="text-[15px] leading-6 text-foreground">
      {parts.map((part, index) => part.highlight
        ? <mark key={index} className="rounded-sm bg-saved px-0.5 text-saved-foreground">{part.text}</mark>
        : <span key={index}>{part.text}</span>)}
    </p>
  );
}
