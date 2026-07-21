import { useNavigate } from "react-router-dom";
import "./Home.css";

const Home = () => {
  const navigate = useNavigate();

  return (
    <div className="home-page">

      {/* Background glow */}
      <div className="bg-glow glow1"></div>
      <div className="bg-glow glow2"></div>

      <div className="home-container">

        {/* HEADER */}
        <div className="home-header">
          <h1 className="home-title">
            ClearView
          </h1>

          <p className="home-subtitle">
            Smart Document Validation & Decision Portal
          </p>
        </div>

        {/* CARDS */}
        <div className="options-grid">

          {/* UPLOAD */}
          <div className="option-card blue"
            onClick={() => navigate("/upload")}
          >
            <div className="icon-wrapper blue-icon">
              📁
            </div>

            <h2>Upload Documents</h2>

            <p>
              Upload and validate documents using AI validation system.
            </p>

            <button className="btn-blue">
              Go to Upload
            </button>
          </div>

          {/* DECISION AGENT */}
          <div className="option-card purple"
            onClick={() => navigate("/decision-agent")}
          >
            <div className="icon-wrapper purple-icon">
              🤖
            </div>

            <h2>Decision Agent</h2>

            <p>
              Upload documents and get AI decision results instantly.
            </p>

            <button className="btn-purple">
              Open Decision Agent
            </button>
          </div>

          {/* DASHBOARD */}
          <div className="option-card green"
            onClick={() => navigate("/dashboard")}
          >
            <div className="icon-wrapper green-icon">
              📊
            </div>

            <h2>DQ Dashboard</h2>

            <p>
              View document quality dashboard, reports and analytics.
            </p>

            <button className="btn-green">
              Open Dashboard
            </button>
          </div>

        </div>

      </div>
    </div>
  );
};

export default Home;