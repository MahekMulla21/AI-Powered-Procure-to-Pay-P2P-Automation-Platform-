import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./DecisionAgent.css";

// ─── API base URL — FastAPI runs on port 8000 ─────────────────────────────────
const API_BASE = "http://127.0.0.1:8000";

const DecisionAgent = () => {

  const navigate = useNavigate();

  const [invoiceFile, setInvoiceFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [running, setRunning] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [currentStep, setCurrentStep] = useState(0);
  const [verdict, setVerdict] = useState(null);
  const [ragOpen, setRagOpen] = useState(false);

  // =========================================================
  // HANDLE FILE
  // =========================================================
  const handleFile = (file) => {
    if (!file) return;

    const allowedExtensions = [".pdf", ".doc", ".docx"];

    const fileName = file.name.toLowerCase();

    const isValid = allowedExtensions.some((ext) =>
      fileName.endsWith(ext)
    );

    if (!isValid) {
      alert("Only PDF, DOC, and DOCX invoices accepted");
      return;
    }

    setInvoiceFile(file);
    setVerdict(null);
    setCurrentStep(0);
    setStatusText("");
  };

  // =========================================================
  // RUN PIPELINE
  // =========================================================
  const runPipeline = async () => {
    if (!invoiceFile) {
      alert("Please upload invoice file");
      return;
    }

    try {
      setRunning(true);
      setVerdict(null);
      setCurrentStep(1);
      setStatusText("Uploading invoice and extracting fields...");

      const formData = new FormData();
      formData.append("file", invoiceFile);

      // ── Upload ──────────────────────────────────────────────────────────
      const uploadResponse = await fetch(`${API_BASE}/upload-invoice`, {
        method: "POST",
        body: formData,
      });

      if (!uploadResponse.ok) {
        let errorMessage = "Upload failed";
        try {
          const errorData = await uploadResponse.json();
          errorMessage = errorData.detail || errorData.message || "Upload failed";
        } catch (e) { }
        alert(errorMessage);
        setRunning(false);
        return;
      }

      const uploadResult = await uploadResponse.json();

      if (!uploadResult.ok) {
        alert(uploadResult.message || "Upload failed");
        setRunning(false);
        return;
      }

      const fileId = uploadResult.file_id;

      if (!fileId) {
        alert("File ID not received");
        setRunning(false);
        return;
      }

      // ── Poll for result ─────────────────────────────────────────────────
      let attempts = 0;

      const interval = setInterval(async () => {
        attempts++;

        try {
          const pollResponse = await fetch(
            `${API_BASE}/invoice-decision/${fileId}`
          );

          if (pollResponse.status === 404) return; // still processing

          if (!pollResponse.ok) {
            clearInterval(interval);
            setRunning(false);
            alert("Polling API failed");
            return;
          }

          const pollResult = await pollResponse.json();

          // ── Update step indicator ─────────────────────────────────────
          if (pollResult.state === "running" || pollResult.state === "processing") {
            if (attempts < 5) {
              setCurrentStep(2);
              setStatusText("Checking PO / PR / MSA / SOW...");
            }
            else if (attempts < 10) {
              setCurrentStep(3);
              setStatusText("Running RAG vector search...");
            }
            else {
              setCurrentStep(4);
              setStatusText("AI Decision Agent evaluating...");
            }
            return;
          }

          if (pollResult.state === "failed") {
            clearInterval(interval);
            setRunning(false);
            setStatusText("Pipeline failed");
            alert(pollResult.error || "Pipeline failed");
            return;
          }

          if (pollResult.state === "done") {
            clearInterval(interval);
            setCurrentStep(5);
            setStatusText("Pipeline completed successfully");

            setVerdict({
              ...(pollResult.verdict || {}),
              rag_context: pollResult.rag_context || ""
            });

            setRunning(false);
          }

        } catch (err) {
          console.error("Polling Error:", err);

          if (attempts > 30) {
            clearInterval(interval);
            setRunning(false);
            alert("Backend connection failed");
          }
        }
      }, 3000);

    } catch (err) {
      console.error("UPLOAD ERROR:", err);
      alert(err.message || "Something went wrong");
      setRunning(false);
    }
  };

  // =========================================================
  // STEP CLASS
  // =========================================================
  const getStepClass = (step) => {
    if (step < currentStep) return "step done";
    if (step === currentStep) return "step active";
    return "step";
  };

  return (
    <div className="decision-page">

      <button
  className="back-btn"
  onClick={() => navigate("/")}
  title="Back to Home"
>
  <span className="back-arrow">←</span>
</button>
      <div className="decision-card">

        <h1 className="decision-title">Invoice Decision Pipeline</h1>

        <p className="decision-subtitle">
          Upload Invoice → Validate → RAG Search → AI Decision
        </p>

        {/* DROP ZONE */}
        <div
          className={`drop-zone ${dragOver ? "dragover" : ""}`}
          onClick={() => document.getElementById("invoiceInput").click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFile(e.dataTransfer.files[0]);
          }}
        >
          <p>📄 Click or Drop Invoice File</p>

          <span>
            PDF, DOC, and DOCX files accepted
          </span>

          <input
            id="invoiceInput"
            type="file"
            accept=".pdf,.doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            hidden
            onChange={(e) => handleFile(e.target.files[0])}
          />
        </div>

        {invoiceFile && (
          <div className="invoice-file">
            📎 {invoiceFile.name}
          </div>
        )}

        <button
          className="run-btn"
          disabled={!invoiceFile || running}
          onClick={runPipeline}
        >
          {running ? "Running Pipeline..." : "Run Decision Pipeline"}
        </button>

        {/* STEPS */}
        {currentStep > 0 && (
          <div className="steps">
            <div className={getStepClass(1)}>Extract Fields</div>
            <div className={getStepClass(2)}>Check DB</div>
            <div className={getStepClass(3)}>RAG Search</div>
            <div className={getStepClass(4)}>AI Decision</div>
            <div className={getStepClass(5)}>Done</div>
          </div>
        )}

        {statusText && (
          <div className="status-text">
            {statusText}
          </div>
        )}

        {/* VERDICT PANEL */}
        {verdict && (
          <div className="verdict-panel">

            <div
              className={`verdict-badge ${verdict.verdict === "approved"
                ? "approved"
                : verdict.verdict === "rejected"
                  ? "rejected"
                  : "review"
                }`}
            >
              {verdict.verdict
                ? verdict.verdict.toUpperCase()
                : "NEEDS REVIEW"}
            </div>

            <div className="confidence-section">

              <div className="confidence-header">
                <span>Confidence</span>

                <span>
                  {Math.round((verdict.confidence || 0) * 100)}%
                </span>
              </div>

              <div className="confidence-bar">
                <div
                  className="confidence-fill"
                  style={{
                    width: `${(verdict.confidence || 0) * 100}%`
                  }}
                />
              </div>

            </div>

            <div className="summary-box">
              {verdict.summary || "No summary available"}
            </div>

            <div className="signals-grid">
              {Object.entries(verdict.signals || {}).map(([key, value]) => (
                <div className="signal-item" key={key}>
                  <span>{key}</span>

                  <span>
                    {typeof value === "boolean"
                      ? (value ? "✓" : "✗")
                      : String(value)}
                  </span>
                </div>
              ))}
            </div>

            {verdict.reasons && verdict.reasons.length > 0 && (
              <div className="reasons-box">

                <h3>Rejection Reasons</h3>

                {verdict.reasons.map((reason, index) => (
                  <div className="reason-item" key={index}>
                    <strong>{reason.code || "ERROR"}</strong>

                    <p>{reason.message || "Unknown reason"}</p>
                  </div>
                ))}

              </div>
            )}

            {verdict.rag_context && (
              <div className="rag-section">

                <button
                  className="rag-toggle"
                  onClick={() => setRagOpen(!ragOpen)}
                >
                  🔍 View RAG Context
                </button>

                {ragOpen && (
                  <div className="rag-body">
                    {verdict.rag_context}
                  </div>
                )}

              </div>
            )}

          </div>
        )}

      </div>
    </div>
  );
};

export default DecisionAgent;