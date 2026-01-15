// const AppURL = "http://localhost:5173/"
// const ApiURL = "http://127.0.0.1:5000/"
const AppURL = "https://vidwiz.adhirajpandey.tech/"
const ApiURL = "https://vidwiz.adhirajpandey.tech/api/"

// Get token from localStorage (will be null if not set)
function getAuthToken() {
	return localStorage.getItem("notes-token")
}

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
	const AUTH_TOKEN = getAuthToken()
	
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

	const apiEndpoint = ApiURL + "notes"

	const noteData = {
		video_id: videoId,
		video_title: videoTitle,
		timestamp: videoTimestamp,
		text: notes || null // Ensure text is null if empty
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
	const AUTH_TOKEN = getAuthToken()
	const videoId = new URL(url).searchParams.get("v")
	if (!videoId) {
		return Promise.reject("Invalid YouTube URL")
	}

	const apiEndpoint = ApiURL + `notes/${videoId}`

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

function setMessage(message, type) {
	const el = document.getElementById("feedback-message")
	if (!el) return
	el.textContent = message
	el.classList.remove("error", "success")
	if (type === "red" || type === "error") {
		el.classList.add("error")
	} else if (type === "green" || type === "success") {
		el.classList.add("success")
	}
}

// Show/hide views based on token presence
function updateViewState() {
	const tokenSetup = document.getElementById("token-setup")
	const notesView = document.getElementById("notes-view")
	const hasToken = !!getAuthToken()
	
	if (hasToken) {
		tokenSetup.classList.add("hidden")
		notesView.classList.remove("hidden")
	} else {
		tokenSetup.classList.remove("hidden")
		notesView.classList.add("hidden")
	}
	
	return hasToken
}

document.addEventListener("DOMContentLoaded", function() {
	// Check if token exists and show appropriate view
	const hasToken = updateViewState()
	
	if (!hasToken) {
		// Token setup view is shown, no need to do anything else
		return
	}
	
	// Set welcome message for notes view
	setMessage("Welcome to VidWiz!", "black")

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

// Save token button handler
document.getElementById("saveTokenBtn").addEventListener("click", function() {
	const tokenInput = document.getElementById("token-input")
	const token = tokenInput.value.trim()
	
	if (!token) {
		tokenInput.style.borderColor = "rgba(239, 68, 68, 0.5)"
		tokenInput.placeholder = "Please enter a valid token..."
		return
	}
	
	// Save token to localStorage
	localStorage.setItem("notes-token", token)
	
	// Update view state to show notes view
	updateViewState()
	
	// Set welcome message
	setMessage("Token saved! Welcome to VidWiz!", "green")
	
	// Initialize the notes view
	chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
		const tabId = tabs[0].id
		const tabURL = tabs[0].url

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

// Go to profile from token setup
document.getElementById("goLoginFromSetup").addEventListener("click", function(e) {
	e.preventDefault()
	const profileURL = AppURL + "profile"
	chrome.tabs.create({ url: profileURL })
})

// Save notes button handler
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
			const viewNotesURL = AppURL + `dashboard/${videoId}`;
			chrome.tabs.create({ url: viewNotesURL });
		}
	});
});

document.getElementById("goDashboard").addEventListener("click", function(e) {
	e.preventDefault();
	const dashboardURL = AppURL + "dashboard";
	chrome.tabs.create({ url: dashboardURL });
});
