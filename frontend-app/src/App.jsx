import { useState, useRef } from "react";
import html2pdf from "html2pdf.js";
import QueryBar from "./components/QueryBar";
import ResultsView from "./components/ResultsView";
import EmptyState from "./components/EmptyState";
import EvidenceBlock from "./components/EvidenceBlock";
import "./App.css";

const formatActivityName = (name) => {
  const labels = {
    get_country_health_profile: "Country profile",
    get_country_comparison: "Country comparison",
    get_indicator_metadata: "Indicator metadata",
    search_indicators: "Indicator search",
    resolve_indicator: "Indicator resolution",
    query_cache: "Cache lookup",
    get_health_summary: "Health summary",
    get_indicator_trend: "Trend analysis",
    default: "Backend step",
  };

  return labels[name] || name.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
};

const formatExportValue = (value, indent = 0) => {
  if (value === null || value === undefined) return "—";
  if (typeof value !== "object") return String(value);
  if (Array.isArray(value)) return value.map((item) => formatExportValue(item, indent)).join("\n");

  return Object.entries(value)
    .map(([key, item]) => `${" ".repeat(indent)}${key}: ${formatExportValue(item, indent + 2)}`)
    .join("\n");
};

const buildExportText = (result) => [
  "ATLAS - GLOBAL HEALTH INTELLIGENCE",
  "",
  "QUESTION",
  result.query,
  "",
  "ANSWER",
  result.answer || "No answer returned.",
  "",
  "EVIDENCE",
  ...(result.evidence.length
    ? result.evidence.map((evidence, index) => `\n[${index + 1}] ${formatExportValue(evidence)}`)
    : ["No evidence returned."]),
  "",
  result.elapsed ? `Elapsed: ${result.elapsed}s` : "",
].join("\n");

function ExportActions({ result }) {
  const [isExporting, setIsExporting] = useState(false);

  const downloadPdf = async () => {
    const element = document.getElementById("atlas-export-content");
    if (!element || isExporting) return;

    setIsExporting(true);
    try {
      await html2pdf().set({
        margin: 0.45,
        filename: `atlas-analysis-${new Date().toISOString().slice(0, 10)}.pdf`,
        image: { type: "jpeg", quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, backgroundColor: "#ffffff" },
        jsPDF: { unit: "in", format: "a4", orientation: "portrait" },
        pagebreak: { mode: ["css", "legacy"] },
      }).from(element).save();
    } finally {
      setIsExporting(false);
    }
  };

  const downloadText = () => {
    const blob = new Blob([buildExportText(result)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `atlas-analysis-${new Date().toISOString().slice(0, 10)}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="export-actions" aria-label="Export analysis">
      <button type="button" onClick={downloadPdf} disabled={isExporting}>
        {isExporting ? "Preparing PDF..." : "Save as PDF"}
      </button>
      <button type="button" onClick={downloadText}>Download TXT</button>
    </div>
  );
}

export default function App() {
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const answerBufferRef = useRef("");
  const startTimeRef = useRef(null);

  const sendQuery = async (query) => {
    setIsLoading(true);
    answerBufferRef.current = "";
    startTimeRef.current = Date.now();
    setResult({ query, answer: "", streaming: true, activities: [], evidence: [], elapsed: null });

    const API_URL = import.meta.env.VITE_API_URL;
    const response = await fetch(`${API_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let currentEvent = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith("event:")) {
          currentEvent = line.replace("event:", "").trim();
        } else if (line.startsWith("data:")) {
          const data = JSON.parse(line.replace("data:", "").trim());

          if (currentEvent === "stage") {
            setResult((prev) => ({
              ...prev,
              activities: prev.activities.map((activity, index) => {
                const stageIndex = prev.activities.findIndex((item) => item.name === data.name);
                if (index < stageIndex) return { ...activity, status: "done" };
                if (index === stageIndex) return { ...activity, status: "loading" };
                return { ...activity, status: "pending" };
              }),
            }));
          } else if (currentEvent === "stage_plan") {
            setResult((prev) => ({
              ...prev,
              activities: data.names.map((name) => ({ name, status: "pending" })),
            }));
          } else if (currentEvent === "tool_call") {
            setResult((prev) => ({
              ...prev,
              activities: prev.activities.some((a) => a.name === formatActivityName(data.name))
                ? prev.activities
                : [...prev.activities, { status: "loading", name: formatActivityName(data.name) }],
            }));
          } else if (currentEvent === "tool_result") {
            setResult((prev) => {
              const activities = prev.activities.map((a) =>
                a.status === "loading" ? { ...a, status: "done" } : a
              );
              const evidence = data.result.type !== "error" ? [...prev.evidence, data.result] : prev.evidence;
              return { ...prev, activities, evidence };
            });
          } else if (currentEvent === "answer_token") {
            answerBufferRef.current += data.token;
            const ans = answerBufferRef.current;
            setResult((prev) => ({ ...prev, answer: ans }));
          } else if (currentEvent === "error") {
            setResult((prev) => ({ ...prev, answer: data.message, streaming: false }));
            setIsLoading(false);
          } else if (currentEvent === "done") {
            const elapsed = ((Date.now() - startTimeRef.current) / 1000).toFixed(1);
            setResult((prev) => ({
              ...prev,
              streaming: false,
              elapsed,
              activities: [...prev.activities, { status: "done", name: "Answer generated" }],
            }));
            setIsLoading(false);
          }
        }
      }
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <span className="atlas-logo">Atlas</span>
        <span className="atlas-sub">Global Health Intelligence</span>
      </header>
      <main className={`app-main ${!result ? "app-main--centered" : ""}`}>
        {!result && (
          <EmptyState onSelect={sendQuery}>
            <QueryBar onSend={sendQuery} isLoading={isLoading} />
          </EmptyState>
        )}
        {result && <QueryBar onSend={sendQuery} isLoading={isLoading} />}
        {result && (
          <>
            <div className="result-toolbar">
              <span className="section-label">Analysis</span>
              <ExportActions result={result} />
            </div>
            <div id="atlas-export-content" className="results-layout">
              <div className="results-left">
                <ResultsView result={result} />
              </div>
              {result.evidence.length > 0 && (
                <div className="results-right fade-in">
                  <div className="section-label">Evidence</div>
                  <div className="evidence-tables">
                    {result.evidence.map((ev, i) => (
                      <EvidenceBlock key={i} data={ev} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
