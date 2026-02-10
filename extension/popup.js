// ── Config ───────────────────────────────────────────────────────────────────
const APP_URL = "https://vidwiz.online"
const API_URL = "https://api.vidwiz.online/v2"
const TOKEN_KEY = "token"

// ── DOM Helpers ──────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id)

function setMessage(msg, type) {
	const el = $("feedback-message")
	if (!el) return
	el.textContent = msg
	el.className = type || ""
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

// ── Token Storage ────────────────────────────────────────────────────────────
const getAuthToken = () => chrome.storage.local.get(TOKEN_KEY).then((r) => r[TOKEN_KEY] || null)
const setAuthToken = (token) => chrome.storage.local.set({ [TOKEN_KEY]: token })

// ── API Client ───────────────────────────────────────────────────────────────
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
		if (res.status === 401) {
			await chrome.storage.local.remove(TOKEN_KEY)
			showTokenSetup()
		}
		throw { status: res.status, body }
	}
	return res.json()
}

function formatApiError(err) {
	const messages = {
		401: "Authentication failed. Please check your API token.",
		403: "Access denied. Please check your permissions.",
		404: "Resource not found.",
		500: "Server error. Please try again later.",
	}
	if (err.status === 422) {
		const d = err.body?.detail
		return Array.isArray(d) ? d.map((x) => x.msg).join("; ") : "Invalid data. Please check your input."
	}
	return messages[err.status] || err.body?.error || `HTTP error: ${err.status}`
}

// ── YouTube Tab Scripts (injected via chrome.scripting) ──────────────────────
// These run inside the YouTube tab, NOT in popup context — must be self-contained

function fetchVideoTitle() {
	if (window.location.hostname === "www.youtube.com" && window.location.pathname === "/watch") {
		const el = document.querySelector(".title.style-scope.ytd-video-primary-info-renderer")
		return el ? el.textContent.trim() : "No YouTube video title found."
	}
	return "No YouTube video found."
}

function fetchVideoTimestamp() {
	if (window.location.hostname === "www.youtube.com" && window.location.pathname === "/watch") {
		const el = document.querySelector(".ytp-time-current")
		return el ? el.textContent.trim() : null
	}
	return null
}

function fetchVideoDuration() {
	if (window.location.hostname === "www.youtube.com" && window.location.pathname === "/watch") {
		const el = document.querySelector(".ytp-time-duration")
		return el ? el.textContent.trim() : null
	}
	return null
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function extractVideoId(url) {
	try { return new URL(url).searchParams.get("v") } catch { return null }
}

function executeOnTab(tabId, fn) {
	return new Promise((resolve) => {
		chrome.scripting.executeScript(
			{ target: { tabId }, function: fn },
			(results) => resolve(results?.[0]?.result ?? null)
		)
	})
}

function timestampToSeconds(ts) {
	if (!isValidTimestamp(ts)) return NaN
	const p = ts.split(":").map(Number)
	return p.length === 3 ? p[0] * 3600 + p[1] * 60 + p[2] : p[0] * 60 + p[1]
}

function isValidTimestamp(ts) {
	if (!ts || !/^\d{1,2}(:\d{2}){1,2}$/.test(ts)) return false
	const p = ts.split(":").map(Number)
	if (p.length === 2) return p[1] < 60
	return p[0] < 100 && p[1] < 60 && p[2] < 60
}

function padTimestamp(ts) {
	const p = ts.replace(/[^\d:]/g, "").split(":")
	if (p.length === 1) return p[0].padStart(1, "0") + ":00"
	if (p.length === 2) return p[0].padStart(1, "0") + ":" + p[1].padEnd(2, "0").slice(0, 2)
	return p[0].padStart(1, "0") + ":" + p[1].padEnd(2, "0").slice(0, 2) + ":" + p[2].padEnd(2, "0").slice(0, 2)
}

function openTab(path) {
	chrome.tabs.create({ url: `${APP_URL}${path}` })
}

function openVideoTab(pathPrefix) {
	chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
		const id = extractVideoId(tabs[0].url)
		if (id) openTab(`${pathPrefix}/${id}`)
	})
}

// ── Backend ──────────────────────────────────────────────────────────────────
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
		body: JSON.stringify({ video_title: videoTitle, timestamp: videoTimestamp, text: text || null }),
	})
	return true
}

// ── Views ────────────────────────────────────────────────────────────────────
function showTokenSetup() {
	$("token-setup").classList.remove("hidden")
	$("notes-view").classList.add("hidden")
}

function showNotesView() {
	$("token-setup").classList.add("hidden")
	$("notes-view").classList.remove("hidden")
}

// Track AbortController to prevent duplicate listeners on re-init
let tsAbortController = null

async function initNotesView() {
	const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
	const { id: tabId, url: tabURL } = tab

	if (!tabURL.includes("youtube.com/watch")) {
		setMessage("No YouTube video found on this page.", "error")
		;["video-title", "timestamp-wrapper", "notes-textarea", "saveNotesBtn", "openSmartNotes", "openInWiz"]
			.forEach((id) => setVisible(id, false))
		return
	}

	const title = await executeOnTab(tabId, fetchVideoTitle)
	if (title) $("video-title").textContent = title

	const timestamp = await executeOnTab(tabId, fetchVideoTimestamp)
	const duration = await executeOnTab(tabId, fetchVideoDuration)
	const tsInput = $("current-timestamp")
	const tsWrapper = $("timestamp-wrapper")
	const resetBtn = $("reset-timestamp")

	const autoSize = () => { tsInput.size = Math.max(tsInput.value.length, 4) }
	if (timestamp) tsInput.value = timestamp
	autoSize()

	const maxSeconds = duration ? timestampToSeconds(duration) : Infinity

	// Abort previous listeners to prevent stacking on re-init
	if (tsAbortController) tsAbortController.abort()
	tsAbortController = new AbortController()
	const { signal } = tsAbortController

	const updateTimestampState = () => {
		if (isValidTimestamp(tsInput.value)) {
			tsWrapper.classList.remove("timestamp-invalid")
		} else {
			tsWrapper.classList.add("timestamp-invalid")
		}
	}

	// Real-time timestamp enforcement
	let lastValid = isValidTimestamp(tsInput.value) ? tsInput.value : "0:00"
	tsInput.addEventListener("input", () => {
		let v = tsInput.value.replace(/[^\d:]/g, "")
		if ((v.match(/:/g) || []).length > 2) { tsInput.value = lastValid; updateTimestampState(); return }

		const parts = v.split(":")
		const valid = parts.every((p, i) => {
			if (p === "") return true
			if (p.length > 2) return false
			const n = Number(p)
			if (parts.length === 3 && i === 0) return n < 100
			return i > 0 ? n < 60 : n < 100
		})

		const overMax = valid && isValidTimestamp(v) && timestampToSeconds(v) > maxSeconds

		if (valid && !overMax) {
			tsInput.value = v
			if (isValidTimestamp(v)) lastValid = v
		} else {
			tsInput.value = lastValid
		}

		updateTimestampState()
		autoSize()
	}, { signal })

	// Normalize partial input on blur
	tsInput.addEventListener("blur", () => {
		if (!isValidTimestamp(tsInput.value)) {
			const padded = padTimestamp(tsInput.value)
			if (isValidTimestamp(padded) && timestampToSeconds(padded) <= maxSeconds) {
				tsInput.value = padded
				lastValid = padded
			} else {
				tsInput.value = lastValid
			}
		}
		updateTimestampState()
		autoSize()
	}, { signal })

	// Reset to current video playback time
	resetBtn.addEventListener("click", async () => {
		const current = await executeOnTab(tabId, fetchVideoTimestamp)
		if (current) {
			tsInput.value = current
			lastValid = current
			updateTimestampState()
			autoSize()
		}
	}, { signal })

	updateTimestampState()
}

// ── Event Handlers ───────────────────────────────────────────────────────────
async function onSaveToken() {
	const input = $("token-input")
	const token = input.value.trim()
	if (!token) {
		input.style.borderColor = "rgba(239, 68, 68, 0.5)"
		input.placeholder = "Please enter a valid API token..."
		return
	}
	await setAuthToken(token)
	showNotesView()
	setMessage("API token saved! Welcome to VidWiz!", "success")
	await initNotesView()
}

async function onSaveNote() {
	const btn = $("saveNotesBtn")
	const textarea = $("notes-textarea")
	setButtonLoading(btn, true)
	try {
		const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
		const title = await executeOnTab(tab.id, fetchVideoTitle)
		const success = await saveNote(tab.url, textarea.value, title, $("current-timestamp").value)
		if (success) { setMessage("Note saved successfully!", "success"); textarea.value = "" }
	} catch (err) {
		console.error("Error saving note:", err)
		setMessage(formatApiError(err), "error")
	} finally {
		setButtonLoading(btn, false)
	}
}

// ── Init ─────────────────────────────────────────────────────────────────────
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
	$("openSmartNotes").addEventListener("click", (e) => { e.preventDefault(); openVideoTab("/dashboard") })
	$("openInWiz").addEventListener("click", (e) => { e.preventDefault(); openVideoTab("/wiz") })
	$("goDashboard").addEventListener("click", (e) => { e.preventDefault(); openTab("/dashboard") })
	$("goLoginFromSetup").addEventListener("click", (e) => { e.preventDefault(); openTab("/profile") })
})
