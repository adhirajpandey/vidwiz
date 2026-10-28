import { Route, Routes } from 'react-router-dom';
import PrivacyPolicyPage from '../features/landing/PrivacyPolicyPage';
import SupportPage from '../features/landing/SupportPage';
import NotFoundPage from '../features/landing/NotFoundPage';
import Seo from '../components/Seo';
import { TooltipProvider } from '../components/ui/Tooltip';
import PublicShell from './PublicShell';

export default function PublicPages() {
  return (
    <TooltipProvider>
      <PublicShell>
        <Seo title="VidWiz" description="Save and search YouTube moments, and ask questions across your library." noIndex />
        <Routes>
          <Route path="/support" element={<SupportPage />} />
          <Route path="/privacy" element={<PrivacyPolicyPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </PublicShell>
    </TooltipProvider>
  );
}
