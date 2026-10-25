import Seo from '../../components/Seo';
import config from '../../config';
import { documentTitle } from '../../lib/title';
import DocPage, { DocCode, DocLink, DocSection } from './DocPage';

const ISSUES_URL = 'https://github.com/adhirajpandey/vidwiz/issues';

export default function SupportPage() {
  return (
    <>
      <Seo
        title={documentTitle('Help')}
        description="Connect the VidWiz Chrome extension, save and revisit YouTube moments, fix common problems, and contact support."
        path="/support"
      />
      <DocPage eyebrow="Support" title="VidWiz help" intro="Set up the Chrome extension, save moments on YouTube, and fix common problems.">
        <DocSection title="Connect your account">
          <p>
            <DocLink href={config.CHROME_WEBSTORE_URL}>Install the extension</DocLink>, then sign in at <DocLink to="/login">vidwiz.online</DocLink> with Google or email and password. Refresh the web app if you were already signed in, then refresh your YouTube tab after installing or updating. Use the same Chrome profile for the web app and extension.
          </p>
        </DocSection>

        <DocSection title="Save a moment">
          <p>
            On a YouTube video or Short, press <kbd className="font-semibold">Alt+S</kbd> or open VidWiz and choose <b>Save moment</b>. Use <b>Add note</b> for a personal note. <b>Save options</b> lets you save without an AI line for free, or with an AI line for 1 credit. Choosing a menu option saves immediately; change your default in <DocLink to="/settings">Settings</DocLink>. Wait for an ad to finish before saving.
          </p>
        </DocSection>

        <DocSection title="Revisit and edit">
          <p>
            Open the extension on a video to see its moments. Click a timestamp to play from five seconds before it. Use the three-dot menu to add or edit a note, or delete a moment after confirming. Delete has no undo. Nearby captures can join an existing moment.
          </p>
        </DocSection>

        <DocSection title="Find more in the web app">
          <p>
            Open <DocLink to="/">vidwiz.online</DocLink> for your library, search, Ask, transcripts, timestamped overviews and export.
          </p>
        </DocSection>

        <DocSection title="Troubleshooting">
          <p>
            If sign-in is missing, sign in again on vidwiz.online and reopen the popup. If VidWiz asks for a reload, refresh YouTube and check the extension's YouTube access. If Alt+S conflicts, set <b>Capture the current moment</b> at <DocCode>chrome://extensions/shortcuts</DocCode>, or save from the popup.
          </p>
          <p>
            AI lines need an available transcript and credits. Check the moment's status and allow time for generation. Saving without AI is free. Check generated text against the video.
          </p>
        </DocSection>

        <DocSection title="Contact">
          <p>
            Email <DocLink href="mailto:support@vidwiz.online">support@vidwiz.online</DocLink> with your Chrome and extension versions, the steps that failed and a public video URL if relevant. Do not send passwords, session tokens or payment details. Remove private information from screenshots.
          </p>
          <p>
            You can also report a bug as a <DocLink href={ISSUES_URL}>GitHub issue</DocLink>. Issues are public, so leave out personal information. See the <DocLink to="/privacy">privacy policy</DocLink> for how VidWiz handles your data.
          </p>
        </DocSection>
      </DocPage>
    </>
  );
}
