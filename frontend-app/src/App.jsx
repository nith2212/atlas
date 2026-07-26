import { useState, useRef } from "react";
import QueryBar from "./components/QueryBar";
import ResultsView from "./components/ResultsView";
import EmptyState from "./components/EmptyState";
import "./App.css";

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

    const response = await fetch("http://localhost:8000/query", {
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

          if (currentEvent === "tool_call") {
            setResult((prev) => ({
              ...prev,
              activities: [...prev.activities, { status: "loading", name: data.name }],
            }));
          } else if (currentEvent === "tool_result") {
            setResult((prev) => {
              const activities = prev.activities.map((a, i) =>
                i === prev.activities.length - 1 ? { ...a, status: "done" } : a
              );
              // data.result is now a typed object — store directly
              const evidence = data.result.type !== "error" ? [...prev.evidence, data.result] : prev.evidence;
              return { ...prev, activities, evidence };
            });
          } else if (currentEvent === "answer_token") {
            answerBufferRef.current += data.token;
            const ans = answerBufferRef.current;
            setResult((prev) => ({ ...prev, answer: ans }));
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
        {!result && <EmptyState onSelect={sendQuery} />}
        <QueryBar onSend={sendQuery} isLoading={isLoading} />
        {result && <ResultsView result={result} />}
      </main>
    </div>
  );
}
