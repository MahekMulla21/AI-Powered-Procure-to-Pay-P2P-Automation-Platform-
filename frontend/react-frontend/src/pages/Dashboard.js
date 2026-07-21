import {
  useCallback,
  useEffect,
  useState,
} from "react";

import "./Dashboard.css";

function Dashboard() {

  const [activeTab, setActiveTab] =
    useState("Overview");

  const [data, setData] = useState([]);
  const [overview, setOverview] =
    useState([]);

  const [expandedFiles, setExpandedFiles] =
    useState({});

  const tabs = [
    "Overview",
    "SOW",
    "MSA",
    "INVOICE",
    "PR",
    "PO",
  ];

  // =============================
  // FORMAT VALUE
  // =============================
  const formatValue = (value) => {

    if (
      value === null ||
      value === undefined ||
      value === ""
    ) {
      return "NA";
    }

    if (typeof value === "object") {

      try {

        return JSON.stringify(
          value,
          null,
          2
        );

      } catch {

        return "NA";
      }
    }

    return value;
  };

  // =============================
  // FORMAT FIELD TYPE
  // =============================
  const formatFieldType = (
    type
  ) => {

    if (!type) {
      return "Unstructured";
    }

    const t =
      type.toUpperCase();

    if (t === "STRUCTURED") {
      return "Structured";
    }

    return "Unstructured";
  };

  // =============================
  // FORMAT FIELD NAME
  // =============================
  const formatFieldName = (
    field
  ) => {

    if (!field) {
      return "";
    }

    return field

      .replace(/_field_type/g, "")

      .replace(/_/g, " ")

      .replace(
        /\b\w/g,
        (char) =>
          char.toUpperCase()
      );
  };

  // =============================
  // TOGGLE FILE
  // =============================
  const toggleFile = (index) => {

    setExpandedFiles((prev) => ({
      ...prev,
      [index]: !prev[index],
    }));
  };

  // =============================
  // TRANSFORM DATA
  // =============================
  const transformData = useCallback(
    (rows) => {

      return rows.map((row) => {

        let fields = [];
        let valid = 0;
        let total = 0;

        Object.keys(row).forEach(
          (key) => {

            if (
              [
                "id",
                "file_id",
                "file_name",
                "active_flag",
                "doc_type",
              ].includes(key)
            ) {
              return;
            }

            // =============================
            // SKIP FIELD TYPE COLUMNS
            // =============================
            if (
              key.endsWith("_field_type")
            ) {
              return;
            }

            // =============================
            // SKIP STATUS FIELDS
            // Example:
            // sow_id_status
            // vendor_name_status
            // =============================
            if (
              key.toLowerCase().endsWith("_status")
            ) {
              return;
            }

            const value =
              formatValue(row[key]);

            const rawFieldType =
              row[
              `${key}_field_type`
              ] || "UNSTRUCTURED";

            const fieldType =
              formatFieldType(
                rawFieldType
              );

            const status =
              value === "NA" ||
                value === "null" ||
                value === "[]" ||
                value === "{}"
                ? "Missing"
                : "Valid";

            if (status === "Valid") {
              valid++;
            }

            total++;

            fields.push({

              field:
                formatFieldName(
                  key
                ),

              value,

              field_type:
                fieldType,

              status,
            });
          }
        );

        const score =
          total > 0
            ? Math.round(
              (valid / total) * 100
            )
            : 0;

        return {

          file_name:
            row.file_name ||
            `File ID: ${row.file_id}`,

          fields,

          summary: {
            score,
            total_fields: total,
            valid_fields: valid,
            missing_fields:
              total - valid,
          },
        };
      });
    },
    []
  );

  // =============================
  // FETCH DATA
  // =============================
  const fetchData = useCallback(
    async (type) => {

      try {

        const endpoint =
          `http://127.0.0.1:8000/${type.toLowerCase()}-dataset`;

        const res = await fetch(
          endpoint
        );

        if (!res.ok) {

          console.error(
            "❌ API Error:",
            res.status
          );

          return [];
        }

        const json =
          await res.json();

        const rows = Array.isArray(
          json.data
        )
          ? json.data
          : [];

        return transformData(rows);

      } catch (err) {

        console.error(
          "❌ Fetch Error:",
          err
        );

        return [];
      }
    },
    [transformData]
  );

  // =============================
  // FETCH OVERVIEW
  // =============================
  const fetchOverview =
    useCallback(async () => {

      const types = [
        "SOW",
        "MSA",
        "INVOICE",
        "PR",
        "PO",
      ];

      let result = [];

      for (let type of types) {

        const res =
          await fetchData(type);

        const totalFiles =
          res.length;

        const validFiles =
          res.filter(
            (item) =>
              item.summary.score >= 70
          ).length;

        const invalidFiles =
          res.filter(
            (item) =>
              item.summary.score < 70
          ).length;

        const avgScore =
          totalFiles > 0
            ? Math.round(
              res.reduce(
                (sum, item) =>
                  sum +
                  item.summary.score,
                0
              ) / totalFiles
            )
            : 0;

        let status = "Poor";

        if (avgScore >= 90) {

          status =
            "Excellent";

        } else if (
          avgScore >= 75
        ) {

          status = "Good";

        } else if (
          avgScore >= 60
        ) {

          status = "Fair";
        }

        result.push({
          type,
          totalFiles,
          validFiles,
          invalidFiles,
          avgScore,
          status,
        });
      }

      setOverview(result);

    }, [fetchData]);

  // =============================
  // EFFECT
  // =============================
  useEffect(() => {

    setExpandedFiles({});

    if (
      activeTab === "Overview"
    ) {

      fetchOverview();

    } else {

      fetchData(activeTab).then(
        setData
      );
    }

  }, [
    activeTab,
    fetchOverview,
    fetchData,
  ]);

  // =============================
  // SCORE COLOR
  // =============================
  const getColor = (score) => {

    if (score >= 80)
      return "#00E599";

    if (score >= 60)
      return "#FACC15";

    return "#EF4444";
  };

  // =============================
  // STATUS CLASS
  // =============================
  const getStatusClass = (
    status
  ) => {

    switch (status) {

      case "Excellent":
        return "status-excellent";

      case "Good":
        return "status-good";

      case "Fair":
        return "status-fair";

      default:
        return "status-poor";
    }
  };

  // =============================
  // TOTALS
  // =============================
  const totalFiles =
    overview.reduce(
      (sum, item) =>
        sum + item.totalFiles,
      0
    );

  const totalValid =
    overview.reduce(
      (sum, item) =>
        sum + item.validFiles,
      0
    );

  const totalInvalid =
    overview.reduce(
      (sum, item) =>
        sum + item.invalidFiles,
      0
    );

  const datasetsWithFiles =
    overview.filter(
      (item) =>
        item.totalFiles > 0
    );

  const totalAverage =
    datasetsWithFiles.length > 0
      ? Math.round(
        datasetsWithFiles.reduce(
          (sum, item) =>
            sum +
            item.avgScore,
          0
        ) /
        datasetsWithFiles.length
      )
      : 0;

  // =============================
  // GET TAB ICON
  // =============================
  const getTabIcon = (type) => {

    switch (type) {

      case "SOW":
        return "📘";

      case "MSA":
        return "📄";

      case "INVOICE":
        return "🧾";

      case "PR":
        return "📑";

      case "PO":
        return "📋";

      default:
        return "📁";
    }
  };

  return (

    <div className="app">

      {/* SIDEBAR */}
      <div className="sidebar">

        <div className="sidebar-logo">

          <div className="logo-circle">
            DQ
          </div>

          <div className="logo-text">

            <h2>
              Data Quality
            </h2>

            <p>
              Dashboard
            </p>

          </div>

        </div>

        <div className="menu-heading">
          Dashboard
        </div>

        <ul>

          {tabs.map((tab) => (

            <li
              key={tab}
              className={
                activeTab === tab
                  ? "active"
                  : ""
              }
              onClick={() =>
                setActiveTab(tab)
              }
            >

              <span className="menu-label">

                {tab === "Overview"
                  ? "🏠"
                  : getTabIcon(tab)}

                {" "}
                {tab}

              </span>

            </li>
          ))}

        </ul>

      </div>

      {/* CONTENT */}
      <div className="content">

        {/* HEADER */}
      {/* HEADER */}
<div className="header">

  <div className="header-left">

    <button
      className="back-arrow-btn"
      onClick={() => window.history.back()}
    >
      ←
    </button>

    <div>

      <h1>
        📊 Data Quality Dashboard
      </h1>

      <p>
        Monitor extraction accuracy,
        validation status and
        document quality insights
      </p>

      <span className="live-monitor">
        Live Monitoring
      </span>

    </div>

  </div>

</div>

        {/* OVERVIEW */}
        {activeTab === "Overview" && (

          <>

            {/* SUMMARY CARDS */}
            <div className="avg-container">

              {overview.map(
                (
                  item,
                  index
                ) => (

                  <div
                    key={index}
                    className="avg-card"
                  >

                    <div className="card-top">

                      <div className="card-icon">
                        {getTabIcon(item.type)}
                      </div>

                      <h3>
                        {item.type}
                      </h3>

                    </div>

                    <div
                      className="avg-score"
                      style={{
                        color:
                          getColor(
                            item.avgScore
                          ),
                      }}
                    >
                      {item.avgScore}%
                    </div>

                    <div className="avg-bar">

                      <div
                        className="avg-fill"
                        style={{
                          width: `${item.avgScore}%`,
                          background:
                            getColor(
                              item.avgScore
                            ),
                        }}
                      ></div>

                    </div>

                  </div>
                )
              )}

            </div>

            {/* TABLE */}
            <div className="card">

              <div className="section-header">

                <h2>
                  Documents Dashboard
                </h2>

                <div className="section-badge">
                  {totalFiles} Files
                </div>

              </div>

              <table className="table">

                <thead>

                  <tr>
                    <th>Type</th>
                    <th>Total Files</th>
                    <th>Valid Files</th>
                    <th>Invalid Files</th>
                    <th>Average Score</th>
                    <th>Status</th>
                  </tr>

                </thead>

                <tbody>

                  {overview.map(
                    (doc, i) => (

                      <tr
                        key={i}
                        style={{
                          cursor: "pointer",
                        }}
                        onClick={() =>
                          setActiveTab(
                            doc.type
                          )
                        }
                      >

                        <td
                          style={{
                            color: "#60A5FA",
                            fontWeight: "700",
                          }}
                        >
                          {getTabIcon(doc.type)}{" "}
                          {doc.type}
                        </td>

                        <td>
                          {doc.totalFiles}
                        </td>

                        <td>
                          {doc.validFiles}
                        </td>

                        <td>
                          {doc.invalidFiles}
                        </td>

                        <td>
                          {doc.avgScore}%
                        </td>

                        <td>

                          <span
                            className={`status-pill ${getStatusClass(
                              doc.status
                            )}`}
                          >
                            {doc.status}
                          </span>

                        </td>

                      </tr>
                    )
                  )}

                  <tr className="total-row">

                    <td>TOTAL</td>

                    <td>
                      {totalFiles}
                    </td>

                    <td>
                      {totalValid}
                    </td>

                    <td>
                      {totalInvalid}
                    </td>

                    <td>
                      {totalAverage}%
                    </td>

                    <td>

                      <span className="status-pill status-good">
                        Good
                      </span>

                    </td>

                  </tr>

                </tbody>

              </table>

            </div>

          </>
        )}

        {/* DETAILS */}
        {[
          "SOW",
          "MSA",
          "INVOICE",
          "PR",
          "PO",
        ].includes(activeTab) && (

            <>

              {/* SUMMARY */}
              <div className="top-summary-grid">

                {/* TOTAL FILES */}
                <div className="top-summary-card">

                  <div className="summary-icon">
                    📁
                  </div>

                  <h3>
                    Total Files
                  </h3>

                  <div className="top-summary-count">
                    {data.length}
                  </div>

                  <p>
                    Uploaded documents in {activeTab}
                  </p>

                </div>

                {/* AVG SCORE */}
                <div className="top-summary-card">

                  <div className="summary-icon">
                    📈
                  </div>

                  <h3>
                    Average Score
                  </h3>

                  <div
                    className="top-summary-count"
                    style={{
                      color:
                        data.length > 0
                          ? getColor(
                            Math.round(
                              data.reduce(
                                (
                                  sum,
                                  item
                                ) =>
                                  sum +
                                  item.summary.score,
                                0
                              ) / data.length
                            )
                          )
                          : "#ffffff",
                    }}
                  >

                    {data.length > 0
                      ? Math.round(
                        data.reduce(
                          (
                            sum,
                            item
                          ) =>
                            sum +
                            item.summary.score,
                          0
                        ) / data.length
                      )
                      : 0}
                    %

                  </div>

                  <p>
                    Validation accuracy
                  </p>

                </div>

              </div>

              {/* FILES */}
              <div className="card">

                <div className="section-header">

                  <h2>
                    {activeTab} Files
                  </h2>

                  <div className="section-badge">
                    {data.length} Records
                  </div>

                </div>

                {data.map(
                  (item, index) => (

                    <div
                      key={index}
                      className="file-expand-card"
                    >

                      {/* HEADER */}
                      <div
                        className="file-expand-header"
                        onClick={() =>
                          toggleFile(index)
                        }
                      >

                        <div className="file-left">

                          <span className="arrow">
                            {expandedFiles[index]
                              ? "▼"
                              : "▶"}
                          </span>

                          <span className="file-title">
                            📄 {item.file_name}
                          </span>

                        </div>

                        <div className="file-right">

                          <span
                            className="badge"
                            style={{
                              background:
                                getColor(
                                  item.summary.score
                                ),
                            }}
                          >
                            {
                              item.summary.score
                            }%
                          </span>

                        </div>

                      </div>

                      {/* CONTENT */}
                      {expandedFiles[index] && (

                        <div className="expanded-content">

                          <table className="table">

                            <thead>

                              <tr>
                                <th>Field</th>
                                <th>Value</th>
                                <th>Field Type</th>
                                <th>Status</th>
                              </tr>

                            </thead>

                            <tbody>

                              {item.fields.map(
                                (
                                  f,
                                  i
                                ) => (

                                  <tr key={i}>

                                    <td className="field-name">
                                      {f.field}
                                    </td>

                                    <td className="value-cell">
                                      {f.value}
                                    </td>

                                    <td>

                                      <span
                                        className={
                                          f.field_type ===
                                            "Structured"
                                            ? "field-type-pill field-structured"
                                            : "field-type-pill field-unstructured"
                                        }
                                      >
                                        {
                                          f.field_type
                                        }
                                      </span>

                                    </td>

                                    <td>

                                      <span
                                        className={
                                          f.status ===
                                            "Valid"
                                            ? "valid"
                                            : "missing"
                                        }
                                      >
                                        {
                                          f.status
                                        }
                                      </span>

                                    </td>

                                  </tr>
                                )
                              )}

                            </tbody>

                          </table>

                          {/* FOOTER */}
                          <div className="card-footer">

                            <span>
                              Total Fields:
                              {
                                item.summary
                                  .total_fields
                              }
                            </span>

                            <span>
                              Valid Fields:
                              {
                                item.summary
                                  .valid_fields
                              }
                            </span>

                            <span>
                              Missing Fields:
                              {
                                item.summary
                                  .missing_fields
                              }
                            </span>

                          </div>

                        </div>
                      )}

                    </div>
                  )
                )}

              </div>

            </>
          )}

      </div>

    </div>
  );
}

export default Dashboard