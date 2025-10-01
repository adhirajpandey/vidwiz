
import { useParams } from 'react-router-dom';

export default function VideoPage() {
  const { videoId } = useParams();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="max-w-4xl mx-auto px-6 py-12">
        <h1 className="text-4xl font-bold">Video Page</h1>
        <p className="mt-4 text-lg">Video ID: {videoId}</p>
      </div>
    </div>
  );
}
