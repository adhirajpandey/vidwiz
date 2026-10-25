import Seo from '../../components/Seo';
import { documentTitle } from '../../lib/title';
import DocPage, { DocLink, DocSection } from './DocPage';

const USER_DATA_POLICY_URL = 'https://developer.chrome.com/docs/webstore/program-policies/policies';

export default function PrivacyPolicyPage() {
  return (
    <>
      <Seo
        title={documentTitle('Privacy policy')}
        description="What data the VidWiz website and Chrome extension handle, which services process it, and how to contact us."
        path="/privacy"
      />
      <DocPage eyebrow="Last updated October 24, 2026" title="Privacy policy" intro="This policy covers the VidWiz website, its API, and the VidWiz Chrome extension.">
        <DocSection title="What VidWiz handles">
          <p>
            VidWiz uses account and saved-video data to provide capture, your library, search and AI features. Google sign-in provides identity details such as your name, email and profile image. Email/password sign-in stores your name, email and a password hash. The web app syncs a session token to the extension, which stores it locally to authenticate API requests.
          </p>
          <p>
            On YouTube, the extension reads the current video's ID, title, channel, playback time and ad state. When you save, it sends the video ID, title, timestamp, optional note, AI choice and capture source to VidWiz. Moments and library associations are stored on the server; video metadata and available transcripts are fetched and stored for related features. Web-app questions and answers are also stored.
          </p>
        </DocSection>

        <DocSection title="Services that process data">
          <p>
            Google handles Google sign-in, and YouTube supplies video metadata, captions and thumbnails. AWS stores transcripts and runs AI background jobs. OpenRouter and its model providers process transcript context for AI lines and overviews, and questions, conversation history and retrieved content for Ask. Library Ask may include your personal notes. Profile images load from their image host. Dodo Payments receives your name and email for web credit checkout; VidWiz stores purchase identifiers, credits and status.
          </p>
          <p>
            Cloudflare hosts the website. Its pages load fonts and the Google sign-in script from Google.
          </p>
        </DocSection>

        <DocSection title="Data use">
          <p>
            We use this data to provide, operate and secure VidWiz in accordance with the{' '}
            <DocLink href={USER_DATA_POLICY_URL}>Chrome Web Store User Data Policy</DocLink>, including its Limited Use requirements.
          </p>
        </DocSection>

        <DocSection title="Service data and security">
          <p>
            VidWiz processes IP addresses for rate limiting. API logs can include request paths, status, timing, device/browser information, account identifiers and limited request/response content. Named credential fields are redacted, but notes and other content can appear in logs. Production API requests use HTTPS.
          </p>
        </DocSection>

        <DocSection title="Your controls and contact">
          <p>
            You can edit a personal note or delete an individual moment. Deleting a moment removes its moment record; transcripts, video metadata, logs and other records are stored separately. For privacy questions or requests about your account or data, contact{' '}
            <DocLink href="mailto:support@vidwiz.online">support@vidwiz.online</DocLink>.
          </p>
          <p>
            For help using VidWiz, see <DocLink to="/support">VidWiz help</DocLink>.
          </p>
        </DocSection>
      </DocPage>
    </>
  );
}
