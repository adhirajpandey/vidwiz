
import type { ReactNode } from 'react';
import Navbar from './Navbar';
import vidwizLogo from '../../public/vidwiz.png';

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div>
      <Navbar />
      <main className="pt-16">{children}</main>
      <footer className="bg-background border-t border-border py-12">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <img src={vidwizLogo} alt="VidWiz" className="w-6 h-6" />
              <span className="text-xl font-bold text-foreground">VidWiz</span>
            </div>
            <p className="text-muted-foreground text-sm">© 2025 VidWiz. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
