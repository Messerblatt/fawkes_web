;(() => {
  // Declare the io variable before using it
  const io = window.io
  const socket = io()
  let currentMode = "low"
  let sessionId = null
  let fileUploaded = false

  const dropZone = document.getElementById("dropZone")
  const uploadBtn = document.getElementById("uploadBtn")
  const fileInput = document.getElementById("fileInput")
  const uploadedFile = document.getElementById("uploadedFile")
  const fileName = document.getElementById("fileName")
  const consoleOutput = document.getElementById("consoleOutput")
  const statusText = document.getElementById("statusText")
  const statusIndicator = document.getElementById("statusIndicator")
  const cloakBtn = document.getElementById("cloakBtn")
  const downloadBtn = document.getElementById("downloadBtn")

  // Prevent default drag behaviors
  ;["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
    document.addEventListener(
      eventName,
      (e) => {
        e.preventDefault()
        e.stopPropagation()
      },
      false,
    )
  })

  // Drag and drop handlers
  dropZone.addEventListener("dragenter", () => dropZone.classList.add("dragover"))
  dropZone.addEventListener("dragover", () => dropZone.classList.add("dragover"))
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"))
  dropZone.addEventListener("drop", (e) => {
    dropZone.classList.remove("dragover")
    const files = e.dataTransfer.files
    if (files.length > 0) {
      handleFileUpload(files[0])
    }
  })

  // Upload button click
  uploadBtn.addEventListener("click", (e) => {
    e.preventDefault()
    e.stopPropagation()
    fileInput.click()
  })

  // File input change
  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFileUpload(e.target.files[0])
    }
  })

  // Mode selection
  document.querySelectorAll(".mode-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!btn.disabled) {
        document.querySelectorAll(".mode-btn").forEach((b) => b.classList.remove("active"))
        btn.classList.add("active")
        currentMode = btn.dataset.mode
      }
    })
  })

  // Cloak button
  cloakBtn.addEventListener("click", () => {
    if (fileUploaded) {
      startCloaking()
    }
  })

  function sanitizeText(text) {
    const div = document.createElement("div")
    div.textContent = text
    return div.innerHTML
  }

  function handleFileUpload(file) {
    const allowedTypes = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/bmp"]
    if (!allowedTypes.includes(file.type)) {
      updateStatus("Invalid file type", "error")
      addToConsole("Error: Invalid file type")
      return
    }

    if (file.size > 16 * 1024 * 1024) {
      updateStatus("File too large (max 16MB)", "error")
      addToConsole("Error: File too large")
      return
    }

    const formData = new FormData()
    formData.append("file", file)

    updateStatus("Uploading...", "processing")

    fetch("/upload", {
      method: "POST",
      body: formData,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        return response.json()
      })
      .then((data) => {
        if (data.success) {
          fileUploaded = true
          fileName.textContent = sanitizeText(data.filename)
          uploadedFile.classList.add("show")
          cloakBtn.disabled = false
          updateStatus("Ready to cloak", "ready")
          addToConsole(`Image uploaded: ${sanitizeText(data.filename)}`)
        } else {
          updateStatus("Upload failed", "error")
          addToConsole("Error: Upload failed")
        }
      })
      .catch((error) => {
        updateStatus("Upload failed", "error")
        addToConsole("Error: Upload failed")
        console.error("Upload error:", error)
      })
  }

  function startCloaking() {
    sessionId = generateSecureId()
    cloakBtn.disabled = true
    downloadBtn.classList.add("hidden")
    updateStatus("Processing...", "processing")

    fetch("/cloak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: currentMode, session_id: sessionId }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        return response.json()
      })
      .then((data) => {
        if (!data.success) {
          updateStatus("Failed to start", "error")
          addToConsole("Error: Failed to start cloaking")
          cloakBtn.disabled = false
        }
      })
      .catch((error) => {
        updateStatus("Error", "error")
        addToConsole("Error: Request failed")
        cloakBtn.disabled = false
        console.error("Cloak error:", error)
      })
  }

  function updateStatus(message, type) {
    statusText.textContent = sanitizeText(message)
    statusIndicator.className = "status-indicator"
    if (type === "processing") {
      statusIndicator.classList.add("processing")
    } else if (type === "error") {
      statusIndicator.classList.add("error")
    }
  }

  function addToConsole(text) {
    const sanitized = sanitizeText(text)
    consoleOutput.textContent += sanitized + "\n"
    consoleOutput.scrollTop = consoleOutput.scrollHeight
  }

  function generateSecureId() {
    return Array.from(crypto.getRandomValues(new Uint8Array(16)))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("")
  }

  // Socket.IO handlers
  socket.on("command_output", (data) => {
    if (!sessionId || data.session_id === sessionId) {
      const sanitizedData = sanitizeText(data.data.trim())
      if (sanitizedData) {
        addToConsole(sanitizedData)
      }
    }
  })

  socket.on("command_complete", (data) => {
    if (!sessionId || data.session_id === sessionId) {
      if (data.success) {
        updateStatus("Completed", "ready")
        downloadBtn.classList.remove("hidden")
        addToConsole("Process completed successfully")
      } else {
        updateStatus("Failed", "error")
        addToConsole(`Error: ${sanitizeText(data.message)}`)
      }
      cloakBtn.disabled = false
    }
  })

  socket.on("connect_error", () => {
    updateStatus("Connection error", "error")
    addToConsole("Error: Failed to connect to server")
  })
})()
