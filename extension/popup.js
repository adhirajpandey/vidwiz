// const backendEndpoint = "http://127.0.0.1:5000/"
const backendEndpoint = "https://vidwiz.adhirajpandey.tech/"
const AUTH_TOKEN = localStorage.getItem("notes-token")

function fetchVideoTitle() {
	if (
		window.location.hostname === "www.youtube.com" &&
		window.location.pathname === "/watch"
	) {
		const titleElement = document.querySelector(
			".title.style-scope.ytd-video-primary-info-renderer"
		)
		if (titleElement) {
			return titleElement.textContent.trim()
		} else {
			return "No YouTube video title found."
		}
	} else {
		return "No YouTube video found."
	}
}

function fetchVideoTimestamp() {
	if (
		window.location.hostname === "www.youtube.com" &&
		window.location.pathname === "/watch"
	) {
		const timestampElement = document.querySelector(".ytp-time-current")
		if (timestampElement) {
			return timestampElement.textContent
		} else {
			return "Timestamp element not found."
		}
	} else {
		return "Not on a YouTube video page."
	}
}

function validateTimestamp(timestamp) {
	if (!timestamp || typeof timestamp !== 'string') {
		return false
	}
	// Check if timestamp contains at least one ':' and two numbers
	return timestamp.includes(':') && (timestamp.match(/\d/g) || []).length >= 2
}

function saveNotesToBackend(url, notes, videoTitle, videoTimestamp) {
	if (videoTitle === "No YouTube video found.") {
		setMessage("No YouTube video found on this page. Notes not saved.")
		return
	}

	// Extract video ID from YouTube URL
	const videoId = new URL(url).searchParams.get("v")
	if (!videoId) {
		setMessage("Invalid YouTube URL. Notes not saved.", "red")
		return
	}

	// Validate timestamp format
	if (!validateTimestamp(videoTimestamp)) {
		setMessage("Invalid timestamp format. Notes not saved.", "red")
		return
	}

	const apiEndpoint = backendEndpoint + "notes"

	const noteData = {
		video_id: videoId,
		video_title: videoTitle,
		note_timestamp: videoTimestamp,
		note: notes || null // Ensure note is null if empty
	}

	fetch(apiEndpoint, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			"Authorization": `Bearer ${AUTH_TOKEN}`
		},
		body: JSON.stringify(noteData)
	})
		.then(response => {
			if (!response.ok) {
				return response.json().then(err => {
					let errorMessage = "Error saving notes. ";
					switch (response.status) {
						case 401:
							errorMessage += "Authentication failed. Please check your token.";
							break;
						case 403:
							errorMessage += "Access denied. Please check your permissions.";
							break;
						case 404:
							errorMessage += "Resource not found.";
							break;
						case 500:
							errorMessage += "Server error. Please try again later.";
							break;
						default:
							errorMessage += err.error || `HTTP error! status: ${response.status}`;
					}
					throw new Error(errorMessage);
				})
			}
			return response.json()
		})
		.then(data => {
			setMessage("Note saved successfully!", "green")
		})
		.catch(error => {
			console.error("Error saving notes:", error)
			setMessage(error.message || "Error saving notes. Please check your authentication token.", "red")
		})
}

function checkNotesExistence(url) {
	const videoId = new URL(url).searchParams.get("v")
	if (!videoId) {
		return Promise.reject("Invalid YouTube URL")
	}

	const apiEndpoint = backendEndpoint + `notes/${videoId}`

	return fetch(apiEndpoint, {
		method: "GET",
		headers: {
			"Authorization": `Bearer ${AUTH_TOKEN}`
		}
	})
		.then(response => {
			if (response.status === 404) {
				return false
			}
			if (!response.ok) {
				throw new Error(`HTTP error! status: ${response.status}`)
			}
			return response.json()
		})
		.then(data => {
			return Array.isArray(data) && data.length > 0
		})
		.catch(error => {
			console.error("Error checking notes:", error)
			setMessage("Error checking notes. Please check your authentication token.", "red")
			return false
		})
}

function setMessage(message, color) {
	document.getElementById("feedback-message").textContent = message
	document.getElementById("feedback-message").style.color = color || "black"
}

document.addEventListener("DOMContentLoaded", function() {
	// Set welcome message
	setMessage("Welcome to VidWiz!", "black")

	if (!localStorage.getItem("notes-token")) {
		setMessage("Please set your notes-token in localStorage before using the extension.\nOpen DevTools and run: localStorage.setItem('notes-token', 'YOUR_TOKEN')", "red")
	}

	chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
		const tabId = tabs[0].id
		const tabURL = tabs[0].url

		// Check if we're on a YouTube video page
		if (!tabURL.includes("youtube.com/watch")) {
			setMessage("No YouTube video found on this page.", "red")
			document.getElementById("video-title").style.display = "none"
			document.getElementById("current-timestamp").style.display = "none"
			document.getElementById("notes-textarea").style.display = "none"
			document.getElementById("saveNotesBtn").style.display = "none"
			document.getElementById("viewNotes").style.display = "none"
			return
		}

		chrome.scripting.executeScript(
			{
				target: {tabId: tabId},
				function: fetchVideoTitle,
			},
			function(results) {
				if (results && results[0]) {
					document.getElementById("video-title").textContent = results[0].result
				}
			}
		)

		chrome.scripting.executeScript(
			{
				target: {tabId: tabId},
				function: fetchVideoTimestamp,
			},
			function(results) {
				if (results && results[0]) {
					document.getElementById("current-timestamp").textContent = results[0].result
				}
			}
		)
	})
})

document.getElementById("saveNotesBtn").addEventListener("click", function () {
	chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
		const tabURL = tabs[0].url

		chrome.scripting.executeScript(
			{
				target: { tabId: tabs[0].id },
				function: fetchVideoTitle,
			},
			function (titleResults) {
				chrome.scripting.executeScript(
					{
						target: { tabId: tabs[0].id },
						function: fetchVideoTimestamp,
					},
					function (timestampResults) {
						const notes = document.getElementById("notes-textarea").value
						saveNotesToBackend(
							tabURL,
							notes,
							titleResults[0].result,
							timestampResults[0].result
						)
					}
				)
			}
		)
	})
})

document.getElementById("viewNotes").addEventListener("click", function(e) {
	e.preventDefault();
	chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
		const tabURL = tabs[0].url;
		const videoId = new URL(tabURL).searchParams.get("v");
		if (videoId) {
			const viewNotesURL = backendEndpoint + `dashboard/${videoId}`;
			chrome.tabs.create({ url: viewNotesURL });
		}
	});
});

document.getElementById("goDashboard").addEventListener("click", function(e) {
	e.preventDefault();
	const dashboardURL = backendEndpoint + "dashboard";
	chrome.tabs.create({ url: dashboardURL });
});
