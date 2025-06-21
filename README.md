# VidWiz

## Description
VidWiz is designed to enhance your YouTube learning and note-taking experience. It allows you to capture and organize your thoughts while watching YouTube videos/lectures/video essays, with a special focus on timestamp-based note-taking. The extension integrates seamlessly with YouTube's interface, making it easy to save notes at specific moments/timestamps in videos.

Additionally, it leverages AI to automatically generate comprehensive notes for any timestamp, providing intelligent summaries and insights from the video content at that specific moment.

The extension is built with:
- Frontend: HTML5, CSS3, and vanilla JavaScript for extension
- Backend: Flask (Python) for REST API
- Database: PostgreSQL for data storage
- LLM: OpenAI/Gemini models for intelligent note generation

## Features
1. **Multi-Client Support**
   - Use the extension with any Chromium-based browser.
   - Use with Android devices via Macrodroid macros.
   - Use with iOS devices via Shortcuts automation.

2. **Interactive Dashboard**
   - A modern UI with a consolidated view of all your notes.
   - Search for videos.
   - Open videos directly at the note's timestamp.
   - Edit and delete notes with ease.

3. **AI Magic**
   - Automatically generate accurate notes for any timestamp using LLMs.
   - Set your custom AI provider and API key.
   - Toggle the AI generation feature on or off.

4. **Self-Hosted**
   - Full privacy with a self-hosted backend.
   - Enhanced security over your data.
   - No third-party data sharing.



## Installation

### Prerequisites
- PostgreSQL database server running locally or remotely
- Docker installed on your system
- Chrome/Chromium based browser

### To Setup Backend
1. Clone the project to your local system using: `git clone https://github.com/adhirajpandey/vidwiz`

2. Create a `.env` file in the server directory with the following variables:
   ```
   DB_URL=postgresql://username:password@localhost:5432/postgres
   AUTH_TOKEN=your_secret_token_here
   TABLE_NAME=your_table_name

   LAMBDA_URL=your_lambda_url
   ```

3. Build Backend server image using: `docker build -t vidwiz .`

4. Setup Docker container using: `docker run -d -p 5000:5000 --name vidwiz-server vidwiz`

### To Setup Chrome Extension in Browser
1. Open Chrome on your machine and navigate to: `chrome://extensions/`

2. Ensure the "Developer mode" checkbox in the top-right corner is checked.

3. Click on Load Unpacked Extension Button, navigate to the `extension` folder in your cloned repository and select it.

4. Set up your authentication token:
   - Open the extension popup
   - Open your browser's developer tools (F12)
   - In the console, run: `localStorage.setItem('notes-token', 'your_secret_token_here')`
   - Replace 'your_secret_token_here' with the same token you set in the server's .env file

## API Endpoints
- `POST /notes`: Create a new note
- `GET /video-notes/{video_id}`: Get all notes for a specific video
- `GET /dashboard`: View the dashboard page
- `GET /dashboard/{video_id}`: View notes for a specific video
- `GET /search?query={search_term}`: Search for videos by title

## Sample

### Dashboard
   ![dashboard-UI](https://github.com/user-attachments/assets/9f2e2942-e0af-4db4-87f5-dc6c7f83a80a)

### Video Notes
   ![notes-ui](https://github.com/user-attachments/assets/b27b5a30-b087-4ce2-b962-b8eea6ee568d)

### Extension
   ![extension-ui](https://github.com/user-attachments/assets/175747d3-7ec3-410b-895c-d26ff996b957)
   
### Mobile View
   ![mobile-ui](https://github.com/user-attachments/assets/fd9133c1-8237-4b3f-94d9-a140154e0345)




