
import { Sparkles } from 'lucide-react';

export default function PrivacyPolicyPage() {
  return (
    <div className="relative overflow-hidden min-h-screen bg-background text-foreground">
      {/* Background Effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-red-500/10 rounded-full blur-[120px] animate-pulse" />
        <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-[120px] animate-pulse delay-75" />
      </div>

      <div className="relative max-w-4xl mx-auto px-4 md:px-6 py-12 md:py-20">
        {/* Header */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 backdrop-blur-xl border border-white/10 text-sm text-foreground/80 mb-6">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <span>Privacy Policy</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold mb-6">
            <span className="bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
              Your Privacy Matters
            </span>
          </h1>
          <p className="text-lg text-foreground/60 max-w-2xl mx-auto">
            Transparency about how we handle your data is at the core of VidWiz.
          </p>
        </div>

        {/* Content */}
        <div className="space-y-12">
          <section className="bg-white/5 backdrop-blur-md rounded-2xl p-8 border border-white/10 hover:border-white/20 transition-colors">
            <h2 className="text-2xl font-bold mb-4 text-white">Introduction</h2>
            <p className="text-foreground/80 leading-relaxed">
              VidWiz ("we," "our," or "us") is committed to protecting your privacy. This Privacy Policy explains how our extension and services interact with your data. By using the VidWiz extension, you agree to the collection and use of information in accordance with this policy.
            </p>
          </section>

          <section className="bg-white/5 backdrop-blur-md rounded-2xl p-8 border border-white/10 hover:border-white/20 transition-colors">
            <h2 className="text-2xl font-bold mb-4 text-white">Data Collection and Usage</h2>
            
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-semibold mb-2 text-purple-400">User-Generated Content</h3>
                <p className="text-foreground/80 leading-relaxed">
                  When you use VidWiz to take notes or generate insights from videos, we process and store this content to provide you with our services. This includes:
                </p>
                <ul className="list-disc list-inside mt-2 text-foreground/80 ml-4 space-y-1">
                  <li>Notes you create manually or with AI assistance.</li>
                  <li>Timestamps and associated video metadata.</li>
                  <li>Chat interactions with the Wiz assistant.</li>
                </ul>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-2 text-red-400">Remote API Interaction</h3>
                <p className="text-foreground/80 leading-relaxed">
                  Our extension communicates with our backend servers at <code className="bg-black/30 px-2 py-1 rounded text-sm font-mono text-purple-300">https://api.vidwiz.online/*</code>. This is necessary to:
                </p>
                <ul className="list-disc list-inside mt-2 text-foreground/80 ml-4 space-y-1">
                  <li>Authenticate your account.</li>
                  <li>Sync your notes across devices.</li>
                  <li>Process AI requests for video analysis and chat.</li>
                </ul>
                <p className="mt-2 text-foreground/80">
                  We do not sell your personal data or user-generated content to third parties.
                </p>
              </div>
            </div>
          </section>

          <section className="bg-white/5 backdrop-blur-md rounded-2xl p-8 border border-white/10 hover:border-white/20 transition-colors">
            <h2 className="text-2xl font-bold mb-4 text-white">Data Security</h2>
            <p className="text-foreground/80 leading-relaxed">
              We implement industry-standard security measures to protect your data during transmission and storage. All communication between the extension and our servers is encrypted using simple HTTPS (TLS/SSL). However, please be aware that no method of transmission over the internet is 100% secure.
            </p>
          </section>

          <section className="bg-white/5 backdrop-blur-md rounded-2xl p-8 border border-white/10 hover:border-white/20 transition-colors">
            <h2 className="text-2xl font-bold mb-4 text-white">Contact Us</h2>
            <p className="text-foreground/80 leading-relaxed">
              If you have any questions about this Privacy Policy, please contact us at:
            </p>
            <a href="mailto:support@vidwiz.online" className="inline-block mt-4 text-purple-400 hover:text-purple-300 transition-colors">
              support@vidwiz.online
            </a>
          </section>
        </div>

        {/* Footer */}
        <div className="mt-20 text-center text-foreground/40 text-sm">
          <p>© {new Date().getFullYear()} VidWiz. All rights reserved.</p>
        </div>
      </div>
    </div>
  );
}
