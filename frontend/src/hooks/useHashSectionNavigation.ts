import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

export function useHashSectionNavigation(sectionId: string, ready: boolean) {
  const { hash } = useLocation();

  useEffect(() => {
    if (!ready || hash !== `#${sectionId}`) return;

    const frame = window.requestAnimationFrame(() => {
      const section = document.getElementById(sectionId);
      section?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      section?.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [hash, ready, sectionId]);
}
