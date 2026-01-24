
/**
 * Extracts a YouTube video ID from various URL formats or raw ID.
 * Returns null if invalid or if it's a playlist URL.
 */
export function extractVideoId(input: string): string | null {
  if (!input) return null;
  const trimmed = input.trim();
  
  if (!trimmed) return null;
  
  // Reject playlist URLs
  if (trimmed.includes('list=')) {
    return null;
  }
  
  // Check if it's a raw video ID (11 characters, alphanumeric with - and _)
  // Note: We use a slightly more permissive check for input detection inside other strings,
  // but for raw ID validation, 11 chars is the standard.
  const rawIdPattern = /^[a-zA-Z0-9_-]{11}$/;
  if (rawIdPattern.test(trimmed)) {
    return trimmed;
  }
  
  try {
    // Handle cases where protocols might be missing or it's just a domain
    // Also handle cases where browser/router creates multiple encoded slashes or strips them
    let urlToParse = trimmed;
    
    // If it starts with http:/ or https:/ but not // (common browser/router artifact)
    if (urlToParse.match(/^https?:\/[^\/]/)) {
      urlToParse = urlToParse.replace(/^(https?):\/+/, '$1://');
    }
    // If no protocol, add https://
    else if (!urlToParse.startsWith('http')) {
      urlToParse = 'https://' + urlToParse;
    }

    const url = new URL(urlToParse);
    const hostname = url.hostname.replace('www.', '');
    
    // youtube.com/watch?v=VIDEO_ID
    if (hostname.includes('youtube.com') && url.pathname === '/watch') {
      const videoId = url.searchParams.get('v');
      if (videoId && rawIdPattern.test(videoId)) {
        return videoId;
      }
    }
    
    // youtube.com/shorts/VIDEO_ID
    if (hostname.includes('youtube.com') && url.pathname.startsWith('/shorts/')) {
      const videoId = url.pathname.split('/shorts/')[1]?.split('?')[0];
      if (videoId && rawIdPattern.test(videoId)) {
        return videoId;
      }
    }
    
    // youtube.com/live/VIDEO_ID
    if (hostname.includes('youtube.com') && url.pathname.startsWith('/live/')) {
      const videoId = url.pathname.split('/live/')[1]?.split('?')[0];
      if (videoId && rawIdPattern.test(videoId)) {
        return videoId;
      }
    }
    
    // youtube.com/embed/VIDEO_ID
    if (hostname.includes('youtube.com') && url.pathname.startsWith('/embed/')) {
      const videoId = url.pathname.split('/embed/')[1]?.split('?')[0];
      if (videoId && rawIdPattern.test(videoId)) {
        return videoId;
      }
    }
    
    // youtu.be/VIDEO_ID
    if (hostname === 'youtu.be') {
      const videoId = url.pathname.slice(1).split('?')[0];
      if (videoId && rawIdPattern.test(videoId)) {
        return videoId;
      }
    }
  } catch {
    // Not a valid URL, already checked for raw ID above
    return null;
  }
  
  return null;
}
