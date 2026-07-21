import { useRef, useState } from "react";
import "./DocumentUpload.css";

// =========================
// API BASE URL
// =========================
const API_BASE = "http://127.0.0.1:8000";

// =========================
// PIPELINE STEPS DEFINITION
// =========================
const PIPELINE_STEPS = [
  { id: "uploading", icon: "📂", label: "Uploading File", desc: "Sending file to server..." },
  { id: "validating", icon: "🔍", label: "Validating Document", desc: "Checking format & integrity..." },
  { id: "ocr", icon: "🧠", label: "Running OCR Extraction", desc: "Extracting text from document..." },
  { id: "detecting", icon: "📄", label: "Detecting Document Type", desc: "Identifying MSA, SOW, PO, PR or Invoice..." },
  { id: "extracting", icon: "⚡", label: "Extracting Fields", desc: "Parsing key fields with AI..." },
  { id: "done", icon: "✅", label: "Upload Successful", desc: "All steps completed." },
];

// Step status: 'idle' | 'active' | 'success' | 'error'
const buildStepState = () =>
  PIPELINE_STEPS.reduce((acc, s) => ({ ...acc, [s.id]: "idle" }), {});

const DocumentUpload = () => {

  // =========================
  // STATE
  // =========================
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [toasts, setToasts] = useState([]);

  // Per-file pipeline: { [filename]: { [stepId]: status } }
  const [filePipelines, setFilePipelines] = useState({});
  // Which file's pipeline is currently shown
  const [activeFile, setActiveFile] = useState(null);

  const fileInputRef = useRef(null);

  // =========================
  // FORMAT SIZE
  // =========================
  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
  };

  // =========================
  // TOAST
  // =========================
  const addToast = (message, type) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  };

  // =========================
  // STEP HELPERS
  // =========================
  const setStep = (filename, stepId, status) => {
    setFilePipelines((prev) => ({
      ...prev,
      [filename]: {
        ...(prev[filename] || buildStepState()),
        [stepId]: status,
      },
    }));
  };

  const delay = (ms) => new Promise((r) => setTimeout(r, ms));

  // =========================
  // FILE CHANGE
  // =========================
  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) addFiles(files);
    e.target.value = "";
  };

  const addFiles = (files) => {
    const allowedTypes = [
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "image/png",
      "image/jpeg",
      "image/jpg",
    ];
    const validFiles = files.filter((f) => allowedTypes.includes(f.type));
    setSelectedFiles((prev) => [...prev, ...validFiles]);
    if (validFiles.length !== files.length)
      addToast("Some unsupported files were skipped", "error");
  };

  const removeFile = (index) =>
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));

  const clearAll = () => {
    setSelectedFiles([]);
    setFilePipelines({});
    setActiveFile(null);
    setToasts([]);
  };

  // =========================
  // HANDLE UPLOAD
  // =========================
  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    setUploading(true);

    let failedFiles = [];

    for (const file of selectedFiles) {
      const name = file.name;

      // Init pipeline for this file
      setFilePipelines((prev) => ({ ...prev, [name]: buildStepState() }));
      setActiveFile(name);

      const formData = new FormData();
      formData.append("file", file);

      try {
        // Step 1: Uploading
        setStep(name, "uploading", "active");
        await delay(400);

        const response = await fetch(`${API_BASE}/upload`, {
          method: "POST",
          body: formData,
        });

        setStep(name, "uploading", "success");
        await delay(200);

        // Step 2: Validating
        setStep(name, "validating", "active");
        await delay(600);

        const result = await response.json();
        if (!response.ok || result.error)
          throw new Error(result.detail || result.message || "Upload failed");

        setStep(name, "validating", "success");
        await delay(200);

        // Step 3: OCR
        setStep(name, "ocr", "active");
        await delay(700);
        setStep(name, "ocr", "success");
        await delay(200);

        // Step 4: Doc type detection
        setStep(name, "detecting", "active");
        await delay(600);
        setStep(name, "detecting", "success");
        await delay(200);

        // Step 5: AI field extraction
        setStep(name, "extracting", "active");
        await delay(700);
        setStep(name, "extracting", "success");
        await delay(200);

        // Step 6: Done
        setStep(name, "done", "success");

        const docType = result.doc_type ? ` (${result.doc_type.toUpperCase()})` : "";
        addToast(`✅ ${name}${docType} uploaded successfully`, "success");

      } catch (err) {
        console.error(err);
        failedFiles.push(file);

        // Mark current active step as error, rest stay idle
        setFilePipelines((prev) => {
          const steps = { ...(prev[name] || buildStepState()) };
          // Find the active step and mark it error; mark final as error
          Object.keys(steps).forEach((k) => {
            if (steps[k] === "active") steps[k] = "error";
          });
          steps["done"] = "error";
          return { ...prev, [name]: steps };
        });

        addToast(`❌ ${name} → ${err.message}`, "error");
      }

      await delay(400);
    }

    setSelectedFiles(failedFiles);
    setUploading(false);
  };

  // =========================
  // PIPELINE DISPLAY for active file
  // =========================
  const currentPipeline =
    activeFile && filePipelines[activeFile]
      ? filePipelines[activeFile]
      : null;

  // For done step: if any step errored, override done icon/label
  const getDoneStep = (pipeline) => {
    if (!pipeline) return PIPELINE_STEPS[5];
    const hasFailed = Object.entries(pipeline).some(
      ([k, v]) => k !== "done" && v === "error"
    );
    if (hasFailed) {
      return { ...PIPELINE_STEPS[5], icon: "❌", label: "Upload Failed", desc: "An error occurred during processing." };
    }
    return PIPELINE_STEPS[5];
  };

  // =========================
  // UI
  // =========================
  return (
    <div className="upload-page">

      {/* BACKGROUND GLOWS */}
      <div className="bg-glow glow1"></div>
      <div className="bg-glow glow2"></div>
      <div className="bg-glow glow3"></div>

      <div className="upload-container">

        {/* HEADER */}
        <div className="upload-header">
          <div className="brand-mark">CV</div>
          <h1 className="main-title">ClearView</h1>
          <p className="sub-title">AI Smart Document Upload &amp; Validation Platform</p>
        </div>

        {/* MAIN CARD */}
        <div className="upload-card">

          {/* CARD HEADER */}
          <div className="card-header">
            <div className="header-left">
              <h2>Document Upload</h2>
              <p>Upload MSA, SOW, PO, PR &amp; Invoice documents</p>
            </div>
            <span className="upload-badge">
              <span className="badge-dot"></span>AI Powered
            </span>
          </div>

          {/* DROP ZONE */}
          <div
            className={`drop-zone ${isDragOver ? "dragover" : ""}`}
            onClick={() => fileInputRef.current.click()}
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragOver(false);
              addFiles(Array.from(e.dataTransfer.files));
            }}
          >
            <div className="dz-inner">
              <div className="upload-icon-wrap">
                <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" className="dz-svg">
                  <path d="M24 32V16M24 16L17 23M24 16L31 23" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M8 36C5.8 34.4 4 31.9 4 29C4 24.6 7.6 21 12 21C12.3 21 12.7 21 13 21.1C14.1 17 17.7 14 22 14C22.7 14 23.3 14.1 24 14.2C24.7 14.1 25.3 14 26 14C30.4 14 34 17.6 34 22C34.3 22 34.7 22 35 22C39.4 22 43 25.6 43 30C43 33 41.2 35.6 38.7 36.8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
                </svg>
              </div>
              <h3 className="drop-title">Drag &amp; Drop Files Here</h3>
              <p className="drop-sub">Supports PDF, DOCX, PNG, JPG</p>
              <button className="browse-btn" type="button">Browse Files</button>
            </div>
            <input
              type="file"
              ref={fileInputRef}
              multiple
              onChange={handleFileChange}
              style={{ display: "none" }}
            />
          </div>

          {/* FILE LIST */}
          {selectedFiles.length > 0 && (
            <div className="file-list">
              <div className="list-header">
                <h3 className="section-title">
                  <span className="file-count-pill">{selectedFiles.length}</span>
                  Selected Files
                </h3>
                <button className="clear-btn" onClick={clearAll} type="button">Clear All</button>
              </div>

              {selectedFiles.map((file, index) => (
                <div className="file-item" key={`${file.name}-${index}`}>
                  <div className="file-info">
                    <div className="file-icon-wrap">
                      <span className="file-ext">{file.name.split(".").pop().toUpperCase()}</span>
                    </div>
                    <div>
                      <div className="file-name">{file.name}</div>
                      <div className="file-size">{formatSize(file.size)}</div>
                    </div>
                  </div>
                  <button
                    className="remove-btn"
                    onClick={() => removeFile(index)}
                    type="button"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* ACTIONS */}
          <div className="actions">
            <button
              className="upload-btn primary-btn"
              disabled={selectedFiles.length === 0 || uploading}
              onClick={handleUpload}
              type="button"
            >
              {uploading ? (
                <><span className="spinner"></span> Processing...</>
              ) : (
                <><span className="btn-icon">↑</span> Upload Files</>
              )}
            </button>
            <button
              className="upload-btn secondary-btn"
              onClick={clearAll}
              disabled={uploading}
              type="button"
            >
              Reset
            </button>
          </div>

          {/* =====================
              PIPELINE TRACKER
          ===================== */}
          {activeFile && currentPipeline && (
            <div className="pipeline-section">
              <div className="pipeline-header">
                <h3 className="pipeline-heading">Processing Pipeline</h3>
                <span className="pipeline-filename">{activeFile}</span>
              </div>

              <div className="pipeline-track">
                {PIPELINE_STEPS.map((step, idx) => {
                  const displayStep = step.id === "done" ? getDoneStep(currentPipeline) : step;
                  const status = currentPipeline[step.id] || "idle";
                  const isLast = idx === PIPELINE_STEPS.length - 1;

                  return (
                    <div className="pipeline-row" key={step.id}>
                      {/* Connector line (not for last) */}
                      {!isLast && (
                        <div className={`connector-line ${status === "success" ? "line-done" : ""
                          }`}></div>
                      )}

                      {/* Step card */}
                      <div className={`pipeline-step step-${status}`}>
                        <div className="step-indicator">
                          {status === "active" && <span className="step-pulse"></span>}
                          {status === "success" && <span className="step-check">✓</span>}
                          {status === "error" && <span className="step-x">✕</span>}
                          {status === "idle" && <span className="step-num">{idx + 1}</span>}
                        </div>
                        <div className="step-body">
                          <div className="step-label">
                            <span className="step-icon">{displayStep.icon}</span>
                            {displayStep.label}
                          </div>
                          <div className="step-desc">
                            {status === "active"
                              ? <span className="typing-dots">{displayStep.desc}<span className="dots"><span>.</span><span>.</span><span>.</span></span></span>
                              : displayStep.desc
                            }
                          </div>
                        </div>
                        <div className={`step-status-badge badge-${status}`}>
                          {status === "idle" ? "Pending" : ""}
                          {status === "active" ? "Running" : ""}
                          {status === "success" ? "Done" : ""}
                          {status === "error" ? "Failed" : ""}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Multi-file tabs */}
              {Object.keys(filePipelines).length > 1 && (
                <div className="file-tabs">
                  {Object.keys(filePipelines).map((fname) => (
                    <button
                      key={fname}
                      className={`file-tab ${activeFile === fname ? "tab-active" : ""}`}
                      onClick={() => setActiveFile(fname)}
                      type="button"
                    >
                      {fname.length > 18 ? fname.slice(0, 16) + "…" : fname}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>{/* /upload-card */}

      </div>{/* /upload-container */}

      {/* TOASTS */}
      <div className="toast-area">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.type}`}>
            {toast.message}
          </div>
        ))}
      </div>

    </div>
  );
};

export default DocumentUpload;