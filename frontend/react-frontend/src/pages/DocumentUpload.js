import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./DocumentUpload.css";

// =========================
// API BASE URL
// =========================
const API_BASE =
  "https://ai-powered-procure-to-pay-p2p-automation-swbi.onrender.com";

// =========================
// PIPELINE STEPS
// =========================
const PIPELINE_STEPS = [
  {
    id: "uploading",
    icon: "📂",
    label: "Uploading File",
    desc: "Sending file to server...",
  },
  {
    id: "validating",
    icon: "🔍",
    label: "Validating Document",
    desc: "Checking document integrity...",
  },
  {
    id: "ocr",
    icon: "🧠",
    label: "Running OCR",
    desc: "Extracting text from document...",
  },
  {
    id: "detecting",
    icon: "📄",
    label: "Detecting Type",
    desc: "Identifying document category...",
  },
  {
    id: "extracting",
    icon: "⚡",
    label: "Extracting Fields",
    desc: "Reading metadata and fields...",
  },
  {
    id: "duplicate",
    icon: "⚠️",
    label: "Duplicate Check",
    desc: "Checking duplicate records...",
  },
  {
    id: "done",
    icon: "✅",
    label: "Completed",
    desc: "Document processing completed.",
  },
];

// =========================
// BUILD STEP STATE
// =========================
const buildStepState = () =>
  PIPELINE_STEPS.reduce(
    (acc, step) => ({
      ...acc,
      [step.id]: "idle",
    }),
    {},
  );

const DocumentUpload = () => {
  const navigate = useNavigate();

  // =========================
  // STATES
  // =========================
  const [selectedFiles, setSelectedFiles] = useState([]);

  const [uploading, setUploading] = useState(false);

  const [isDragOver, setIsDragOver] = useState(false);

  const [toasts, setToasts] = useState([]);

  const [filePipelines, setFilePipelines] = useState({});

  const [activeFile, setActiveFile] = useState(null);

  // FINAL RESULT
  const [finalStatus, setFinalStatus] = useState({});

  const fileInputRef = useRef(null);

  // =========================
  // FORMAT FILE SIZE
  // =========================
  const formatSize = (bytes) => {
    if (bytes < 1024) {
      return `${bytes} B`;
    }

    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(2)} KB`;
    }

    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  // =========================
  // TOAST
  // =========================
  const addToast = (message, type = "success") => {
    const id = Date.now() + Math.random();

    setToasts((prev) => [...prev, { id, message, type }]);

    setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 4000);
  };

  // =========================
  // LIVE LOGS
  // =========================
  const addLog = (filename, message, type = "info") => {
    const log = {
      id: Date.now() + Math.random(),
      message,
      type,
      time: new Date().toLocaleTimeString(),
    };
  };

  // =========================
  // STEP STATUS
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

  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  // =========================
  // FILE CHANGE
  // =========================
  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);

    if (files.length > 0) {
      addFiles(files);
    }

    e.target.value = "";
  };

  // =========================
  // ADD FILES
  // =========================
  const addFiles = (files) => {
    const allowedTypes = [
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "image/png",
      "image/jpeg",
      "image/jpg",
    ];

    const validFiles = files.filter((file) => allowedTypes.includes(file.type));

    setSelectedFiles((prev) => [...prev, ...validFiles]);

    if (validFiles.length !== files.length) {
      addToast("Some unsupported files were skipped", "error");
    }
  };

  // =========================
  // REMOVE FILE
  // =========================
  const removeFile = (index) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // =========================
  // RESET
  // =========================
  const clearAll = () => {
    setSelectedFiles([]);
    setFilePipelines({});
    setActiveFile(null);
    setToasts([]);
    setFinalStatus({});
  };

  // =========================
  // HANDLE UPLOAD
  // =========================
  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;

    setUploading(true);

    let failedFiles = [];

    for (const file of selectedFiles) {
      const filename = file.name;

      setActiveFile(filename);

      setFilePipelines((prev) => ({
        ...prev,
        [filename]: buildStepState(),
      }));

      addLog(filename, "Upload started");

      const formData = new FormData();

      formData.append("file", file);

      try {
        // =========================
        // STEP 1
        // =========================
        setStep(filename, "uploading", "active");

        await delay(600);

        const response = await fetch(`${API_BASE}/upload`, {
          method: "POST",
          body: formData,
        });

        const result = await response.json();

        if (!response.ok || result.error) {
          throw new Error(result.detail || result.message || "Upload failed");
        }

        setStep(filename, "uploading", "success");

        // =========================
        // STEP 2
        // =========================
        setStep(filename, "validating", "active");

        await delay(700);

        setStep(filename, "validating", "success");

        // =========================
        // STEP 3
        // =========================
        setStep(filename, "ocr", "active");

        await delay(900);

        setStep(filename, "ocr", "success");

        // =========================
        // STEP 4
        // =========================
        setStep(filename, "detecting", "active");

        await delay(800);

        setStep(filename, "detecting", "success");

        // =========================
        // STEP 5
        // =========================
        setStep(filename, "extracting", "active");

        await delay(900);

        setStep(filename, "extracting", "success");

        // =========================
        // STEP 6
        // =========================
        setStep(filename, "duplicate", "active");

        await delay(1000);

        const isDuplicate =
          result?.is_duplicate ||
          result?.duplicate ||
          result?.status === "duplicate" ||
          result?.final_status === "DUPLICATE";

        // =========================
        // DUPLICATE FOUND
        // =========================
        if (isDuplicate) {
          setStep(filename, "duplicate", "error");

          setStep(filename, "done", "error");

          // FINAL STATUS
          setFinalStatus((prev) => ({
            ...prev,
            [filename]: {
              type: "duplicate",
              title: "Duplicate Record Found",
              message: "This document already exists in the database.",
            },
          }));

          addToast(`⚠️ Duplicate File: ${filename}`, "error");

          continue;
        }

        // =========================
        // NO DUPLICATE
        // =========================
        setStep(filename, "duplicate", "success");

        // =========================
        // STEP 7
        // =========================
        setStep(filename, "done", "active");

        await delay(700);

        setStep(filename, "done", "success");

        // FINAL STATUS
        setFinalStatus((prev) => ({
          ...prev,
          [filename]: {
            type: "success",
            title: "Document Processed Successfully",
            message: "File uploaded and validated successfully.",
          },
        }));

        addToast(`✅ ${filename} uploaded successfully`, "success");
      } catch (error) {
        console.error(error);

        failedFiles.push(file);

        setFilePipelines((prev) => {
          const updated = {
            ...(prev[filename] || buildStepState()),
          };

          Object.keys(updated).forEach((key) => {
            if (updated[key] === "active") {
              updated[key] = "error";
            }
          });

          updated.done = "error";

          return {
            ...prev,
            [filename]: updated,
          };
        });

        // FINAL STATUS
        setFinalStatus((prev) => ({
          ...prev,
          [filename]: {
            type: "error",
            title: "Upload Failed",
            message: error.message || "Something went wrong.",
          },
        }));

        addToast(`❌ ${filename} → ${error.message}`, "error");
      }

      await delay(500);
    }

    setSelectedFiles(failedFiles);

    setUploading(false);
  };

  // =========================
  // CURRENT FILE
  // =========================
  const currentPipeline =
    activeFile && filePipelines[activeFile] ? filePipelines[activeFile] : null;

  const currentFinalStatus =
    activeFile && finalStatus[activeFile] ? finalStatus[activeFile] : null;

  // =========================
  // UI
  // =========================
  return (
    <div className="upload-page">
      <div className="bg-glow glow1"></div>

      <div className="bg-glow glow2"></div>

      <div className="upload-container">
        <button
          className="back-btn"
          onClick={() => navigate("/")}
          title="Back to Home"
        >
          <span className="back-arrow">←</span>
        </button>

        {/* HEADER */}
        <div className="upload-header">
          <div className="brand-mark">CV</div>

          <h1 className="main-title">ClearView</h1>

          <p className="sub-title">AI Smart Document Upload Platform</p>
        </div>

        {/* CARD */}
        <div className="upload-card">
          {/* HEADER */}
          <div className="card-header">
            <div className="header-left">
              <h2>Document Upload</h2>

              <p>Upload MSA, SOW, PO, PR & Invoice documents</p>
            </div>

            <span className="upload-badge">
              <span className="badge-dot"></span>
              AI Powered
            </span>
          </div>

          {/* DROP ZONE */}
          <div
            className={`drop-zone ${isDragOver ? "dragover" : ""}`}
            onClick={() => fileInputRef.current.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();

              setIsDragOver(false);

              addFiles(Array.from(e.dataTransfer.files));
            }}
          >
            <div className="dz-inner">
              <div className="upload-icon-wrap">📂</div>

              <h3 className="drop-title">Drag & Drop Files Here</h3>

              <p className="drop-sub">Supports PDF, DOCX, PNG, JPG</p>

              <button className="browse-btn" type="button">
                Browse Files
              </button>
            </div>

            <input
              type="file"
              ref={fileInputRef}
              multiple
              onChange={handleFileChange}
              style={{
                display: "none",
              }}
            />
          </div>

          {/* FILE LIST */}
          {selectedFiles.length > 0 && (
            <div className="file-list">
              <div className="list-header">
                <h3 className="section-title">Selected Files</h3>

                <button className="clear-btn" onClick={clearAll}>
                  Clear All
                </button>
              </div>

              {selectedFiles.map((file, index) => (
                <div className="file-item" key={index}>
                  <div className="file-info">
                    <div>
                      <div className="file-name">{file.name}</div>

                      <div className="file-size">{formatSize(file.size)}</div>
                    </div>
                  </div>

                  <button
                    className="remove-btn"
                    onClick={() => removeFile(index)}
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
            >
              {uploading ? <>Processing...</> : <>Upload Files</>}
            </button>

            <button
              className="upload-btn secondary-btn"
              onClick={clearAll}
              disabled={uploading}
            >
              Reset
            </button>
          </div>

          {/* PIPELINE */}
          {activeFile && currentPipeline && (
            <div className="pipeline-section">
              <div className="pipeline-header">
                <h3 className="pipeline-heading">Live Processing Pipeline</h3>

                <span className="pipeline-filename">{activeFile}</span>
              </div>

              <div className="pipeline-track">
                {PIPELINE_STEPS.map((step, index) => {
                  const status = currentPipeline[step.id] || "idle";

                  return (
                    <div
                      key={step.id}
                      className={`pipeline-step step-${status}`}
                    >
                      <div className="step-indicator">
                        {status === "success" && "✓"}

                        {status === "error" && "✕"}

                        {status === "active" && (
                          <span className="step-pulse"></span>
                        )}

                        {status === "idle" && index + 1}
                      </div>

                      <div className="step-body">
                        <div className="step-label">
                          {step.icon} {step.label}
                        </div>

                        <div className="step-desc">{step.desc}</div>
                      </div>

                      <div className={`step-status-badge badge-${status}`}>
                        {status.toUpperCase()}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* FINAL RESULT */}
              {currentFinalStatus && (
                <div className={`final-result-card ${currentFinalStatus.type}`}>
                  <div className="final-result-icon">
                    {currentFinalStatus.type === "success" && "✅"}

                    {currentFinalStatus.type === "duplicate" && "⚠️"}

                    {currentFinalStatus.type === "error" && "❌"}
                  </div>

                  <div>
                    <div className="final-result-title">
                      {currentFinalStatus.title}
                    </div>

                    <div className="final-result-message">
                      {currentFinalStatus.message}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

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
