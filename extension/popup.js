// ── Config ───────────────────────────────────────────────────────────────────
const CONSTANTS = {
  API: {
    BASE_URL: "https://vidwiz.online",
    API_URL: "https://api.vidwiz.online/v2",
    ENDPOINTS: {
      NOTES: (videoId) => `/videos/${videoId}/notes`
    }
  },
  STORAGE: {
    TOKEN: "token"
  },
  SELECTORS: {
    FEEDBACK: "feedback-message",
    TOKEN_SETUP: "token-setup",
    NOTES_VIEW: "notes-view",
    VIDEO_TITLE: "video-title",
    TIMESTAMP_WRAPPER: "timestamp-wrapper",
    NOTES_TEXTAREA: "notes-textarea",
    SAVE_BTN: "saveNotesBtn",
    OPEN_SMART_NOTES: "openSmartNotes",
    OPEN_IN_WIZ: "openInWiz",
    CURRENT_TIMESTAMP: "current-timestamp",
    RESET_TIMESTAMP: "reset-timestamp",
    GO_DASHBOARD: "goDashboard",
    GO_LOGIN: "goLoginFromSetup"
  },
  CLASSES: {
    HIDDEN: "hidden",
    INVALID: "timestamp-invalid",
    SUCCESS: "success",
    ERROR: "error"
  },
  MESSAGES: {
    NO_VIDEO: "No YouTube video found on this page.",
    RELOAD: "Please reload this YouTube page to enable the extension.",
    INVALID_URL: "Invalid YouTube URL.",
    INVALID_TIMESTAMP: "Invalid timestamp format.",
    SAVED: "Note saved successfully!",
    CONN_LOST: "Connection lost. Please reload the YouTube page.",
    SYNCED: "Synced with VidWiz!",
    WELCOME: "Welcome to VidWiz!"
  }
};

// ── DOM Helpers ──────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id)

function setMessage(msg, type) {
	const el = $(CONSTANTS.SELECTORS.FEEDBACK)
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
const getAuthToken = () => chrome.storage.local.get(CONSTANTS.STORAGE.TOKEN).then((r) => r[CONSTANTS.STORAGE.TOKEN] || null)
const setAuthToken = (token) => chrome.storage.local.set({ [CONSTANTS.STORAGE.TOKEN]: token })

// ── API Client ───────────────────────────────────────────────────────────────
async function apiRequest(path, options = {}) {
	const token = await getAuthToken()
	const res = await fetch(`${CONSTANTS.API.API_URL}${path}`, {
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
			await chrome.storage.local.remove(CONSTANTS.STORAGE.TOKEN)
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

// ── Content Script Communication ──────────────────────────────────────────────

// ── Helpers ──────────────────────────────────────────────────────────────────
function extractVideoId(url) {
	try { return new URL(url).searchParams.get("v") } catch { return null }
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
	chrome.tabs.create({ url: `${CONSTANTS.API.BASE_URL}${path}` })
}

function openVideoTab(pathPrefix) {
	chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
		const id = extractVideoId(tabs[0].url)
		if (id) openTab(`${pathPrefix}/${id}`)
	})
}

// ── Backend ──────────────────────────────────────────────────────────────────
async function saveNote(url, text, videoTitle, videoTimestamp) {
	if (videoTitle === CONSTANTS.MESSAGES.NO_VIDEO) {
		setMessage(CONSTANTS.MESSAGES.NO_VIDEO, CONSTANTS.CLASSES.ERROR)
		return false
	}
	const videoId = extractVideoId(url)
	if (!videoId) {
		setMessage(CONSTANTS.MESSAGES.INVALID_URL, CONSTANTS.CLASSES.ERROR)
		return false
	}
	if (!isValidTimestamp(videoTimestamp)) {
		setMessage(CONSTANTS.MESSAGES.INVALID_TIMESTAMP, CONSTANTS.CLASSES.ERROR)
		return false
	}
	await apiRequest(CONSTANTS.API.ENDPOINTS.NOTES(videoId), {
		method: "POST",
		body: JSON.stringify({ video_title: videoTitle, timestamp: videoTimestamp, text: text || null }),
	})
	return true
}

// ── Views ────────────────────────────────────────────────────────────────────
function showTokenSetup() {
	$(CONSTANTS.SELECTORS.TOKEN_SETUP).classList.remove(CONSTANTS.CLASSES.HIDDEN)
	$(CONSTANTS.SELECTORS.NOTES_VIEW).classList.add(CONSTANTS.CLASSES.HIDDEN)
}

function showNotesView() {
	$(CONSTANTS.SELECTORS.TOKEN_SETUP).classList.add(CONSTANTS.CLASSES.HIDDEN)
	$(CONSTANTS.SELECTORS.NOTES_VIEW).classList.remove(CONSTANTS.CLASSES.HIDDEN)
}

// Track AbortController to prevent duplicate listeners on re-init
let tsAbortController = null

async function initNotesView() {
	const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
	const { id: tabId, url: tabURL } = tab

	if (!tabURL.includes("youtube.com/watch")) {
		setMessage(CONSTANTS.MESSAGES.NO_VIDEO, CONSTANTS.CLASSES.ERROR)
		;[CONSTANTS.SELECTORS.VIDEO_TITLE, CONSTANTS.SELECTORS.TIMESTAMP_WRAPPER, CONSTANTS.SELECTORS.NOTES_TEXTAREA, CONSTANTS.SELECTORS.SAVE_BTN, CONSTANTS.SELECTORS.OPEN_SMART_NOTES, CONSTANTS.SELECTORS.OPEN_IN_WIZ]
			.forEach((id) => setVisible(id, false))
		return
	}

	let videoData = { title: null, timestamp: null, duration: null }
	try {
		videoData = await chrome.tabs.sendMessage(tabId, { action: "getVideoData" })
	} catch (e) {
		setMessage(CONSTANTS.MESSAGES.RELOAD, CONSTANTS.CLASSES.ERROR)
		setVisible(CONSTANTS.SELECTORS.VIDEO_TITLE, false)
		setVisible(CONSTANTS.SELECTORS.TIMESTAMP_WRAPPER, false)
		setVisible(CONSTANTS.SELECTORS.NOTES_TEXTAREA, false)
		setVisible(CONSTANTS.SELECTORS.SAVE_BTN, false)
		return
	}
	const { title, timestamp, duration } = videoData || {}

	if (title) $(CONSTANTS.SELECTORS.VIDEO_TITLE).textContent = title
	const tsInput = $(CONSTANTS.SELECTORS.CURRENT_TIMESTAMP)
	const tsWrapper = $(CONSTANTS.SELECTORS.TIMESTAMP_WRAPPER)
	const resetBtn = $(CONSTANTS.SELECTORS.RESET_TIMESTAMP)

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
			tsWrapper.classList.remove(CONSTANTS.CLASSES.INVALID)
		} else {
			tsWrapper.classList.add(CONSTANTS.CLASSES.INVALID)
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
		try {
			const current = await chrome.tabs.sendMessage(tabId, { action: "getVideoTimestamp" })
			if (current) {
				tsInput.value = current
				lastValid = current
				updateTimestampState()
				autoSize()
			}
		} catch (error) {
			console.error("Failed to fetch timestamp:", error)
			setMessage(CONSTANTS.MESSAGES.CONN_LOST, CONSTANTS.CLASSES.ERROR)
		}
	}, { signal })

	updateTimestampState()
}

// ── Event Handlers ───────────────────────────────────────────────────────────


async function onSaveNote() {
	const btn = $(CONSTANTS.SELECTORS.SAVE_BTN)
	const textarea = $(CONSTANTS.SELECTORS.NOTES_TEXTAREA)
	setButtonLoading(btn, true)
	try {
		const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
		const data = await chrome.tabs.sendMessage(tab.id, { action: "getVideoData" })
		const title = data?.title
		const success = await saveNote(tab.url, textarea.value, title, $(CONSTANTS.SELECTORS.CURRENT_TIMESTAMP).value)
		if (success) { setMessage(CONSTANTS.MESSAGES.SAVED, CONSTANTS.CLASSES.SUCCESS); textarea.value = "" }
	} catch (err) {
		console.error("Error saving note:", err)
		if (err.message && (err.message.includes("Could not establish connection") || err.message.includes("measure to prevent"))) {
			setMessage(CONSTANTS.MESSAGES.CONN_LOST, CONSTANTS.CLASSES.ERROR)
		} else {
			setMessage(formatApiError(err), CONSTANTS.CLASSES.ERROR)
		}
	} finally {
		setButtonLoading(btn, false)
	}
}

// ── Storage Listener ─────────────────────────────────────────────────────────
chrome.storage.onChanged.addListener((changes, area) => {
	if (area === "local" && changes[CONSTANTS.STORAGE.TOKEN]) {
		const newToken = changes[CONSTANTS.STORAGE.TOKEN].newValue
		if (newToken) {
			setMessage(CONSTANTS.MESSAGES.SYNCED, CONSTANTS.CLASSES.SUCCESS)
			showNotesView()
			initNotesView()
		} else {
			showTokenSetup()
		}
	}
})

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
	const token = await getAuthToken()
	if (token) {
		showNotesView()
		setMessage(CONSTANTS.MESSAGES.WELCOME, CONSTANTS.CLASSES.SUCCESS)
		await initNotesView()
	} else {
		// If not logged in, show setup screen immediately
		showTokenSetup()
	}

	$(CONSTANTS.SELECTORS.SAVE_BTN).addEventListener("click", onSaveNote)
	$(CONSTANTS.SELECTORS.OPEN_SMART_NOTES).addEventListener("click", (e) => { e.preventDefault(); openVideoTab("/dashboard") })
	$(CONSTANTS.SELECTORS.OPEN_IN_WIZ).addEventListener("click", (e) => { e.preventDefault(); openVideoTab("/wiz") })
	$(CONSTANTS.SELECTORS.GO_DASHBOARD).addEventListener("click", (e) => { e.preventDefault(); openTab("/dashboard") })
	$(CONSTANTS.SELECTORS.GO_LOGIN).addEventListener("click", (e) => { e.preventDefault(); openTab("/login") })
})
