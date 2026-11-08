;(() => {
  const io = window.io
  const socket = io()
  let currentMode = "low"
  let currentJobId = null // uploaded, waiting to be cloaked
  let watchedJobId = null // job whose completion we are tracking
  let fileUploaded = false

  const $ = (id) => document.getElementById(id)
  const dropZone = $("dropZone")
  const uploadBtn = $("uploadBtn")
  const fileInput = $("fileInput")
  const uploadedFile = $("uploadedFile")
  const uploadThumb = $("uploadThumb")
  const fileName = $("fileName")
  const consoleOutput = $("consoleOutput")
  const statusText = $("statusText")
  const statusIndicator = $("statusIndicator")
  const cloakBtn = $("cloakBtn")
  const downloadBtn = $("downloadBtn")
  const historyList = $("historyList")
  const historyEmpty = $("historyEmpty")
  const notifyToggle = $("notifyToggle")
  const notifyHint = $("notifyHint")
  const confirmDialog = $("confirmDialog")
  const confirmText = $("confirmText")

  const originalTitle = document.title

  // ---------------------------------------------------------------- upload
  ;["dragenter", "dragover", "dragleave", "drop"].forEach((ev) => {
    document.addEventListener(ev, (e) => { e.preventDefault(); e.stopPropagation() }, false)
  })
  dropZone.addEventListener("dragenter", () => dropZone.classList.add("dragover"))
  dropZone.addEventListener("dragover", () => dropZone.classList.add("dragover"))
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"))
  dropZone.addEventListener("drop", (e) => {
    dropZone.classList.remove("dragover")
    if (e.dataTransfer.files.length > 0) handleFileUpload(e.dataTransfer.files[0])
  })
  dropZone.addEventListener("click", () => fileInput.click())
  dropZone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click() }
  })
  uploadBtn.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); fileInput.click() })
  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) handleFileUpload(e.target.files[0])
    fileInput.value = ""
  })
  // paste an image from the clipboard
  document.addEventListener("paste", (e) => {
    const item = Array.from(e.clipboardData?.items || []).find((i) => i.type.startsWith("image/"))
    if (item) handleFileUpload(item.getAsFile())
  })

  document.querySelectorAll(".mode-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return
      document.querySelectorAll(".mode-btn").forEach((b) => b.classList.remove("active"))
      btn.classList.add("active")
      currentMode = btn.dataset.mode
      updateModeHint()
    })
  })

  const modeHint = $("modeHint")
  function updateModeHint() {
    const gpu = modeHint.dataset.gpu === "true"
    const hints = gpu
      ? { low: "Fastest, lighter protection.", mid: "Balanced protection and time.", high: "Strongest protection, slowest." }
      : {
          low: "Fastest: a few minutes on CPU.",
          mid: "No GPU: CPU-capped so the server stays responsive, so it is much slower than Low (likely over an hour).",
          high: "No GPU: CPU-capped and very slow, can take many hours. You can close the page; the result lands in History.",
        }
    modeHint.textContent = hints[currentMode]
    modeHint.classList.toggle("warn", !gpu && currentMode !== "low")
  }
  updateModeHint()

  cloakBtn.addEventListener("click", () => { if (fileUploaded) startCloaking() })

  function handleFileUpload(file) {
    const allowed = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/bmp"]
    if (!allowed.includes(file.type)) {
      updateStatus("Invalid file type", "error"); addToConsole("Error: Invalid file type"); return
    }
    if (file.size > 16 * 1024 * 1024) {
      updateStatus("File too large (max 16MB)", "error"); addToConsole("Error: File too large"); return
    }

    // pasted screenshots have a generic name: give them a useful one
    const name = file.name && file.name !== "image.png" ? file.name : `pasted-${Date.now()}.png`
    const formData = new FormData()
    formData.append("file", file, name)
    updateStatus("Uploading...", "processing")

    fetch("/upload", { method: "POST", body: formData })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((data) => {
        if (!data.success) throw new Error("upload")
        fileUploaded = true
        currentJobId = data.job_id
        fileName.textContent = data.filename
        if (uploadThumb.dataset.url) URL.revokeObjectURL(uploadThumb.dataset.url)
        const url = URL.createObjectURL(file)
        uploadThumb.dataset.url = url
        uploadThumb.src = url
        uploadedFile.classList.add("show")
        cloakBtn.disabled = false
        downloadBtn.classList.add("hidden")
        updateStatus("Ready to cloak", "ready")
        addToConsole(`Image uploaded: ${data.filename}`)
      })
      .catch((err) => {
        updateStatus("Upload failed", "error"); addToConsole("Error: Upload failed"); console.error(err)
      })
  }

  function startCloaking() {
    cloakBtn.disabled = true
    downloadBtn.classList.add("hidden")
    updateStatus("Processing...", "processing")
    watchedJobId = currentJobId

    fetch("/cloak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: currentMode, job_id: currentJobId }),
    })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((data) => {
        if (!data.success) throw new Error("start")
        // the upload is now a history entry: reset the form
        fileUploaded = false
        currentJobId = null
        uploadedFile.classList.remove("show")
        loadHistory()
      })
      .catch((err) => {
        updateStatus("Error", "error"); addToConsole("Error: Request failed")
        cloakBtn.disabled = false; watchedJobId = null; console.error(err)
      })
  }

  function updateStatus(message, type) {
    statusText.textContent = message
    statusIndicator.className = "status-indicator"
    if (type === "processing") statusIndicator.classList.add("processing")
    else if (type === "error") statusIndicator.classList.add("error")
  }

  function addToConsole(text) {
    consoleOutput.textContent += text + "\n"
    consoleOutput.scrollTop = consoleOutput.scrollHeight
  }

  // --------------------------------------------------------- notifications
  const NOTIFY_KEY = "fawkes.notify"
  const canNotify = "Notification" in window

  function readPref() {
    try { return localStorage.getItem(NOTIFY_KEY) === "1" } catch (e) { return false }
  }
  function savePref(on) {
    try { localStorage.setItem(NOTIFY_KEY, on ? "1" : "0") } catch (e) { /* ignore */ }
  }

  function syncNotifyUi() {
    if (!canNotify) {
      notifyToggle.checked = false
      notifyToggle.disabled = true
      notifyHint.textContent = "Notifications are not supported by this browser."
    } else if (Notification.permission === "denied") {
      notifyToggle.checked = false
      notifyToggle.disabled = true
      notifyHint.textContent = "Blocked in the browser settings for this site."
    } else {
      notifyToggle.checked = readPref() && Notification.permission === "granted"
    }
  }

  notifyToggle.addEventListener("change", async () => {
    if (!notifyToggle.checked) { savePref(false); return }
    let permission = Notification.permission
    if (permission === "default") permission = await Notification.requestPermission()
    savePref(permission === "granted")
    syncNotifyUi()
  })

  function notifyDone(success, body) {
    if (!notifyToggle.checked || !canNotify || Notification.permission !== "granted") return
    if (document.visibilityState === "visible" && document.hasFocus()) return // already looking at it
    try {
      const n = new Notification(success ? "Cloaking finished ✓" : "Cloaking failed", { body, tag: "fawkes-done" })
      n.onclick = () => { window.focus(); n.close() }
    } catch (e) { /* some mobile browsers only allow service-worker notifications */ }
  }

  function flashTitle(text) {
    document.title = text
    const reset = () => {
      if (document.visibilityState === "visible") {
        document.title = originalTitle
        document.removeEventListener("visibilitychange", reset)
      }
    }
    document.addEventListener("visibilitychange", reset)
  }

  // --------------------------------------------------------------- history
  const items = new Map() // id -> { el, job, expiresAt }

  function formatRemaining(seconds) {
    if (seconds <= 0) return "expired"
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m left`
    if (m > 0) return `${m} min left`
    return `${seconds}s left`
  }

  function buildItem(job) {
    const li = document.createElement("li")
    li.className = "history-item"

    const thumb = document.createElement("div")
    thumb.className = "history-thumb"
    li.appendChild(thumb)

    const info = document.createElement("div")
    const name = document.createElement("div")
    name.className = "history-name"
    name.textContent = job.name
    const meta = document.createElement("div")
    meta.className = "history-meta"
    info.append(name, meta)
    li.appendChild(info)

    const actions = document.createElement("div")
    actions.className = "history-actions"
    li.appendChild(actions)

    const entry = { el: li, thumb, meta, actions, job, expiresAt: 0, state: null }
    items.set(job.id, entry)
    return entry
  }

  function applyState(entry) {
    const { job, thumb, actions } = entry
    if (entry.state === job.status) return
    entry.state = job.status
    actions.textContent = ""
    thumb.textContent = ""
    thumb.className = "history-thumb"

    if (job.status === "done") {
      const img = document.createElement("img")
      img.className = "history-thumb"
      img.alt = ""
      img.loading = "lazy"
      img.src = `/api/jobs/${job.id}/preview`
      thumb.replaceWith(img)
      entry.thumb = img

      const dl = document.createElement("a")
      dl.className = "btn-small"
      dl.href = `/api/jobs/${job.id}/download`
      dl.textContent = "Download"
      const del = document.createElement("button")
      del.className = "btn-small danger"
      del.type = "button"
      del.textContent = "Delete"
      del.addEventListener("click", () => askDelete(job))
      actions.append(dl, del)
    } else {
      thumb.classList.add("loading")
      thumb.textContent = "…"
    }
  }

  function renderHistory(jobs) {
    const seen = new Set()
    jobs.forEach((job) => {
      seen.add(job.id)
      let entry = items.get(job.id)
      if (!entry) { entry = buildItem(job); historyList.appendChild(entry.el) }
      entry.job = job
      entry.expiresAt = Date.now() + job.remaining_seconds * 1000
      applyState(entry)
    })
    for (const [id, entry] of items) {
      if (!seen.has(id)) { entry.el.remove(); items.delete(id) }
    }
    // keep server order (newest first)
    jobs.forEach((job) => historyList.appendChild(items.get(job.id).el))
    historyEmpty.classList.toggle("hidden", items.size > 0)
    tick()
  }

  function tick() {
    let expiredAny = false
    for (const entry of items.values()) {
      if (entry.job.status === "processing") {
        entry.meta.textContent = `Processing (${entry.job.mode || "low"} mode)…`
        entry.meta.classList.remove("soon")
        continue
      }
      const remaining = Math.max(0, Math.round((entry.expiresAt - Date.now()) / 1000))
      entry.meta.textContent = `Expires in: ${formatRemaining(remaining)}`.replace("Expires in: expired", "Expired")
      entry.meta.classList.toggle("soon", remaining < 3600)
      if (remaining === 0) expiredAny = true
    }
    if (expiredAny) loadHistory()
  }

  function loadHistory() {
    return fetch("/api/jobs", { cache: "no-store" })
      .then((r) => r.json())
      .then((data) => renderHistory(data.jobs))
      .catch((err) => console.error("History error:", err))
  }

  let pendingDelete = null
  function askDelete(job) {
    pendingDelete = job
    confirmText.textContent = job.name
    confirmDialog.showModal()
  }
  confirmDialog.addEventListener("close", () => {
    const job = pendingDelete
    pendingDelete = null
    if (confirmDialog.returnValue !== "confirm" || !job) return
    fetch(`/api/jobs/${job.id}`, { method: "DELETE" })
      .then((r) => { if (!r.ok && r.status !== 404) throw new Error(`HTTP ${r.status}`) })
      .then(() => { addToConsole(`Deleted: ${job.name}`); return loadHistory() })
      .catch((err) => { addToConsole("Error: delete failed"); console.error(err) })
  })

  setInterval(tick, 30 * 1000)
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") loadHistory() })

  // -------------------------------------------------------------- sockets
  socket.on("command_output", (data) => {
    const text = (data.data || "").trim()
    if (text) addToConsole(text)
  })

  socket.on("command_complete", (data) => {
    if (data.success) {
      updateStatus("Completed", "ready")
      addToConsole("Process completed successfully")
      if (data.job_id) {
        downloadBtn.href = `/api/jobs/${data.job_id}/download`
        downloadBtn.classList.remove("hidden")
      }
      notifyDone(true, "Your cloaked image is ready in the history.")
      if (document.visibilityState !== "visible") flashTitle("✓ Done - " + originalTitle)
    } else {
      updateStatus("Failed", "error")
      addToConsole(`Error: ${data.message}`)
      notifyDone(false, String(data.message || "").slice(0, 120))
    }
    watchedJobId = null
    cloakBtn.disabled = !fileUploaded
  })

  socket.on("jobs_changed", loadHistory)
  socket.on("connect", loadHistory) // also catches jobs finished while we were away

  socket.on("connect_error", () => {
    updateStatus("Connection error", "error")
    addToConsole("Error: Failed to connect to server")
  })

  syncNotifyUi()
  loadHistory()
})()
