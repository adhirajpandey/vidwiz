// ============================================================================
// CONFIG
// ============================================================================

const APP_URL = "https://vidwiz.online"
const API_URL = "https://api.vidwiz.online/v2"
const TOKEN_KEY = "notes-token"

// ============================================================================
// DOM HELPERS
// ============================================================================

const $ = (id) => document.getElementById(id)

function setMessage(message, type) {
	const el = $("feedback-message")
	if (!el) return

	el.textContent = message
	el.classList.remove("error", "success")

	if (type === "error") {
		el.classList.add("error")
	} else if (type === "success") {
		el.classList.add("success")
	}
}

function setVisible(id, visible) {
	const el = $(id)
	if (el) el.style.display = visible ? "" : "none"
}

function setButtonLoading(btn, loading) {
	btn.disabled = loading
	btn.dataset.originalText = btn.dataset.originalText || btn.textContent
	btn.textContent = loading ? "Saving..." : btn.dataset.originalText
}

// ============================================================================
// TOKEN STORAGE (chrome.storage.local)
// ============================================================================

async function getAuthToken() {
	const result = await chrome.storage.local.get(TOKEN_KEY)
	return result[TOKEN_KEY] || null
}

async function setAuthToken(token) {
	await chrome.storage.local.set({ [TOKEN_KEY]: token })
}

// ============================================================================
// API CLIENT
// ============================================================================

/**
 * Make an authenticated API request.
 * Returns parsed JSON on success, throws on error.
 */
async function apiRequest(path, options = {}) {
	const token = await getAuthToken()

	const res = await fetch(`${API_URL}${path}`, {
		...options,
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
			...options.headers,
		},
	})

	if (!res.ok) {
		const body = await res.json().catch(() => ({}))

		// Auto-clear token on auth failure so user can re-enter
		if (res.status === 401) {
			await chrome.storage.local.remove(TOKEN_KEY)
			showTokenSetup()
		}

		throw { status: res.status, body }
	}

	return res.json()
}

/** Map API error to user-friendly message */
function formatApiError(err) {
	if (err.status === 401) return "Authentication failed. Please check your token."
	if (err.status === 403) return "Access denied. Please check your permissions."
	if (err.status === 404) return "Resource not found."
	if (err.status === 422) {
		const details = err.body?.detail
		if (Array.isArray(details)) {
			return details.map((d) => d.msg).join("; ")
		}
		return "Invalid data. Please check your input."
	}
	if (err.status === 500) return "Server error. Please try again later."
	return err.body?.error || `HTTP error: ${err.status}`
}

// ============================================================================
// YOUTUBE PAGE SCRIPTS (injected into the active tab)
// ============================================================================

function fetchVideoTitle() {
	if (
		window.location.hostname === "www.youtube.com" &&
		window.location.pathname === "/watch"
	) {
		const titleEl = document.querySelector(
			".title.style-scope.ytd-video-primary-info-renderer"
		)
		return titleEl ? titleEl.textContent.trim() : "No YouTube video title found."
	}
	return "No YouTube video found."
}

function fetchVideoTimestamp() {
	if (
		window.location.hostname === "www.youtube.com" &&
		window.location.pathname === "/watch"
	) {
		const timestampEl = document.querySelector(".ytp-time-current")
		return timestampEl ? timestampEl.textContent : "Timestamp element not found."
	}
	return "Not on a YouTube video page."
}

// ============================================================================
// YOUTUBE HELPERS
// ============================================================================

function extractVideoId(url) {
	try {
		return new URL(url).searchParams.get("v")
	} catch {
		return null
	}
}

function isValidTimestamp(timestamp) {
	if (!timestamp || typeof timestamp !== "string") return false
	return timestamp.includes(":") && (timestamp.match(/\d/g) || []).length >= 2
}

function executeOnTab(tabId, fn) {
	return new Promise((resolve) => {
		chrome.scripting.executeScript(
			{ target: { tabId }, function: fn },
			(results) => resolve(results?.[0]?.result ?? null)
		)
	})
}

// ============================================================================
// BACKEND API ACTIONS
// ============================================================================



async function saveNote(url, text, videoTitle, videoTimestamp) {
	if (videoTitle === "No YouTube video found.") {
		setMessage("No YouTube video found on this page.", "error")
		return false
	}

	const videoId = extractVideoId(url)
	if (!videoId) {
		setMessage("Invalid YouTube URL.", "error")
		return false
	}

	if (!isValidTimestamp(videoTimestamp)) {
		setMessage("Invalid timestamp format.", "error")
		return false
	}

	await apiRequest(`/videos/${videoId}/notes`, {
		method: "POST",
		body: JSON.stringify({
			video_title: videoTitle,
			timestamp: videoTimestamp,
			text: text || null,
		}),
	})

	return true
}

// ============================================================================
// VIEW MANAGEMENT
// ============================================================================

function showTokenSetup() {
	$("token-setup").classList.remove("hidden")
	$("notes-view").classList.add("hidden")
}

function showNotesView() {
	$("token-setup").classList.add("hidden")
	$("notes-view").classList.remove("hidden")
}

async function initNotesView() {
	const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
	const { id: tabId, url: tabURL } = tab

	if (!tabURL.includes("youtube.com/watch")) {
		setMessage("No YouTube video found on this page.", "error")
		;["video-title", "current-timestamp", "notes-textarea", "saveNotesBtn", "openSmartNotes", "openInWiz"]
			.forEach((id) => setVisible(id, false))
		return
	}

	const title = await executeOnTab(tabId, fetchVideoTitle)
	if (title) $("video-title").textContent = title

	const timestamp = await executeOnTab(tabId, fetchVideoTimestamp)
	if (timestamp) $("current-timestamp").textContent = timestamp
}

// ============================================================================
// EVENT HANDLERS
// ============================================================================

async function onSaveToken() {
	const input = $("token-input")
	const token = input.value.trim()

	if (!token) {
		input.style.borderColor = "rgba(239, 68, 68, 0.5)"
		input.placeholder = "Please enter a valid token..."
		return
	}

	await setAuthToken(token)
	showNotesView()
	setMessage("Token saved! Welcome to VidWiz!", "success")
	await initNotesView()
}

async function onSaveNote() {
	const btn = $("saveNotesBtn")
	const textarea = $("notes-textarea")

	setButtonLoading(btn, true)

	try {
		const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
		const { id: tabId, url: tabURL } = tab

		const title = await executeOnTab(tabId, fetchVideoTitle)
		const timestamp = await executeOnTab(tabId, fetchVideoTimestamp)
		const text = textarea.value

		const success = await saveNote(tabURL, text, title, timestamp)
		if (success) {
			setMessage("Note saved successfully!", "success")
			textarea.value = ""
		}
	} catch (err) {
		console.error("Error saving note:", err)
		setMessage(formatApiError(err), "error")
	} finally {
		setButtonLoading(btn, false)
	}
}

function onOpenSmartNotes(e) {
	e.preventDefault()
	chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
		const videoId = extractVideoId(tabs[0].url)
		if (videoId) {
			chrome.tabs.create({ url: `${APP_URL}/dashboard/${videoId}` })
		}
	})
}

function onOpenInWiz(e) {
	e.preventDefault()
	chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
		const videoId = extractVideoId(tabs[0].url)
		if (videoId) {
			chrome.tabs.create({ url: `${APP_URL}/wiz/${videoId}` })
		}
	})
}

function onDashboard(e) {
	e.preventDefault()
	chrome.tabs.create({ url: `${APP_URL}/dashboard` })
}

function onGetToken(e) {
	e.preventDefault()
	chrome.tabs.create({ url: `${APP_URL}/profile` })
}

// ============================================================================
// INIT
// ============================================================================

document.addEventListener("DOMContentLoaded", async () => {
	const token = await getAuthToken()

	if (token) {
		showNotesView()
		setMessage("Welcome to VidWiz!", "success")
		await initNotesView()
	} else {
		showTokenSetup()
	}

	$("saveTokenBtn").addEventListener("click", onSaveToken)
	$("saveNotesBtn").addEventListener("click", onSaveNote)
	$("openSmartNotes").addEventListener("click", onOpenSmartNotes)
	$("openInWiz").addEventListener("click", onOpenInWiz)
	$("goDashboard").addEventListener("click", onDashboard)
	$("goLoginFromSetup").addEventListener("click", onGetToken)
})
