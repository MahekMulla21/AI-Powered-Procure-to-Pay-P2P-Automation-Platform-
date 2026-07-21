import { BrowserRouter, Route, Routes } from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import DecisionAgent from "./pages/DecisionAgent";
import DocumentUpload from "./pages/DocumentUpload";
import Home from "./pages/Home";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/upload" element={<DocumentUpload />} />
        <Route path="/decision-agent" element={<DecisionAgent />} />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;