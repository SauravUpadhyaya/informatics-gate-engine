import { useCallback, useEffect, useState } from "react";
import {
  DashboardSummary,
  Flag,
  fetchFlags,
  fetchSummary,
  runPipeline,
} from "./api"; // Ensure your api.ts file contains the active fetch methods

type FilterType = "all" | "unbundling" | "upcoding";

function formatCurrency(n: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

function formatPct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}

export default function App() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [selected, setSelected] = useState<Flag | null>(null);
  const [filter, setFilter] = useState<FilterType>("all");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);


  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, f] = await Promise.all([
        fetchSummary(),
        fetchFlags(filter === "all" ? undefined : { flag_type: filter }),
      ]);
      setSummary(s);
      setFlags(f);
    } catch (e) {
      console.error(e);
      setError("Network Sync Error: Could not connect to database pipeline.");
    } finally {
      setLoading(false);
    }
  }, [filter]);


  useEffect(() => {
    loadData();
  }, [loadData]);

  // Executes the real Python data processing loop when clicking the button
  async function handleRunPipeline() {
    setRunning(true);
    setError(null);
    try {
      await runPipeline(); // Triggers POST /api/v1/pipeline/run
      await loadData(); // Reloads fresh database entries instantly
    } catch (e) {
      console.error(e);
      setError("Pipeline execution failed.");
    } finally {
      setRunning(false);
    }
  }
  return (
    <div className="app-shell">
      <header className="header">
        <div>
          <h1>Clinical Pattern Recognition & Decision Support Platform</h1>
          <p>
          
          </p>
        </div>
        <div className="header-actions">
          <button className="btn" onClick={loadData} disabled={loading}>
            Refresh
          </button>
          <button className="btn btn-primary" onClick={handleRunPipeline} disabled={running}>
            {running ? "Running Pipeline…" : "Run Full Pipeline"}
          </button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      {summary && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="label">Total Flags</div>
            <div className="value">{summary.total_flags}</div>
            <div className="sub">{summary.open_flags} open for review</div>
          </div>
          <div className="stat-card risk">
            <div className="label">Financial Risk Blocked</div>
            <div className="value">{formatCurrency(summary.total_financial_risk)}</div>
            <div className="sub">Estimated savings if pre-adjudicated</div>
          </div>
          <div className="stat-card">
            <div className="label">Unbundling</div>
            <div className="value">{summary.unbundling_count}</div>
            <div className="sub">NCCI PTP violations</div>
          </div>
          <div className="stat-card">
            <div className="label">Upcoding</div>
            <div className="value">{summary.upcoding_count}</div>
            <div className="sub">Complexity anomalies</div>
          </div>
          <div className="stat-card">
            <div className="label">Avg Confidence</div>
            <div className="value">{formatPct(summary.avg_confidence)}</div>
            <div className="sub">Across all flagged claims</div>
          </div>
        </div>
      )}

      <div className={`layout-split ${selected ? "has-detail" : ""}`}>
        <div className="panel">
          <div className="panel-header">
            <h2>Flagged Claims Queue</h2>
            <div className="filters">
              {(["all", "unbundling", "upcoding"] as FilterType[]).map((f) => (
                <button
                  key={f}
                  className={`chip ${filter === f ? "active" : ""}`}
                  onClick={() => setFilter(f)}
                >
                  {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="loading">Loading real claims lines from DB…</div>
          ) : flags.length === 0 ? (
            <div className="empty-state">
              <p>No flags yet. Click <strong>Run Full Pipeline</strong> to execute your real Python analysis models.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Claim ID</th>
                    <th>Type</th>
                    <th>Patient</th>
                    <th>Service Date</th>
                    <th>Financial Risk</th>
                    <th>Confidence</th>
                    <th>Rule</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {flags.map((flag) => (
                    <tr
                      key={flag.id}
                      className={selected?.id === flag.id ? "selected" : ""}
                      onClick={() => setSelected(flag)}
                      style={{ cursor: "pointer" }}
                    >
                      <td className="mono">{flag.clm_id}</td>
                      <td>
                        <span className={`badge ${flag.flag_type}`}>{flag.flag_type}</span>
                      </td>
                      <td className="mono">{flag.desynpuf_id}</td>
                      <td>{flag.service_date}</td>
                      <td>{formatCurrency(flag.financial_risk)}</td>
                      <td>
                        <div className="confidence-bar">
                          <div className="confidence-track">
                            <div className="confidence-fill" style={{ width: `${flag.confidence_score * 100}%` }} />
                          </div>
                          <span>{formatPct(flag.confidence_score)}</span>
                        </div>
                      </td>
                      <td className="mono" style={{ fontSize: "0.75rem" }}>{flag.rule_id}</td>
                   {/* 📁 Inside frontend/src/App.tsx — Locate your select block inside the table mapping loop: */}
<td>
  <select 
    className="status-select" 
    value={flag.status} 
    onChange={(e) => {
      // 🛠️ FIXED: Adds interactive state change hook to satisfy React & TypeScript parameters cleanly
      setFlags(prevFlags => 
        prevFlags.map(f => f.id === flag.id ? { ...f, status: e.target.value } : f)
      );
    }}
  >
    <option value="open">Open</option>
    <option value="reviewed">Reviewed</option>
    <option value="blocked">Blocked</option>
    <option value="dismissed">Dismissed</option>
  </select>
</td>

                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {selected && (
          <div className="detail-panel">
            <h3>Claim Detail — {selected.clm_id}</h3>
            <div className="detail-grid">
              <div className="detail-item">
                <div className="k">Violation Type</div>
                <div className="v">
                  <span className={`badge ${selected.flag_type}`}>{selected.flag_type}</span>
                </div>
              </div>
              <div className="detail-item">
                <div className="k">Financial Risk</div>
                <div className="v">{formatCurrency(selected.financial_risk)}</div>
              </div>
              <div className="detail-item">
                <div className="k">Confidence Score</div>
                <div className="v">{formatPct(selected.confidence_score)}</div>
              </div>
              <div className="detail-item">
                <div className="k">Violated Codes</div>
                <div className="v mono">{selected.violated_codes.join(" + ")}</div>
              </div>
            </div>
            
            <p style={{ color: "var(--muted)", marginBottom: 20 }}>{selected.rule_description}</p>

            {/* 🏥 REAL TIME OPERATIONAL AUDIT PANEL */}
            <div style={{
              background: "rgba(30, 41, 59, 0.5)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "0.5rem",
              padding: "1.25rem",
              marginBottom: "1.5rem"
            }}>
              <h4 style={{ color: "#38bdf8", marginTop: 0, marginBottom: "1rem", fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Operational Audit Evidence
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.5rem" }}>
                  <span style={{ color: "var(--muted)" }}>Compliance Vector</span>
                  <span style={{ color: "#f59e0b", fontWeight: "bold" }}>
                    {selected.flag_type === "upcoding" ? "Statistical Deviation" : "Deterministic Rule Match"}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "0.5rem" }}>
                  <span style={{ color: "var(--muted)" }}>Triggered Identifier Reference</span>
                  <span style={{ color: "#38bdf8", fontWeight: "bold", fontFamily: "monospace" }}>{selected.rule_id}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem" }}>
                  <span style={{ color: "var(--muted)" }}>Pre-Payment Adjudication Action</span>
                  <span style={{ color: "#ef4444", fontWeight: "bold" }}>
                    {selected.flag_type === "upcoding" ? "FREEZE_FUNDS" : "DENY_PAYMENT"}
                  </span>
                </div>
              </div>
            </div>

            <h3 style={{ fontSize: "0.85rem", color: "var(--muted)" }}>Evidence Payload (JSON)</h3>
            <pre className="evidence-pre">
              {JSON.stringify(selected.evidence || selected, null, 2)}
            </pre>
          </div>
        )}
      </div>
      <ChatbotOverlay activeClaim={selected} />
    </div>
  );
}

// 📁 Paste this at the absolute bottom of frontend/src/App.tsx (Outside your App component)
function ChatbotOverlay({ activeClaim }: { activeClaim: any }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<{ sender: "user" | "bot"; text: string }[]>([
    { sender: "bot", text: "Hello! I am your Cotiviti Intelligence Assistant. I parse medical records, compute overpayment exposure variations, and cross-verify provider claims. Ask me questions." }
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSendMessage() {
    if (!input.trim() || sending) return;
    const userText = input;
    setMessages(prev => [...prev, { sender: "user", text: userText }]);
    setInput("");
    setSending(true);

    try {
      // 🛠️ CROSS-REPOSITORY LANELINK GETWAY: Network fetch target routes to port 8001!
      const response = await fetch("http://localhost:8001/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userText,
          claim_context: activeClaim || { clm_id: "NONE_SELECTED", flag_type: "general" }
        })
      });
      const data = await response.json();
      setMessages(prev => [...prev, { sender: "bot", text: data.response }]);
    } catch (err) {
      setMessages(prev => [...prev, { sender: "bot", text: "⚠️ Connection Error: Failed to communicate with your local LangGraph repository server on port 8001." }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div style={{ position: "fixed", bottom: "24px", right: "24px", zIndex: 9999, fontFamily: "sans-serif" }}>
      {/* TRIGGER FLOATING BALL BUTTON */}
      {!isOpen && (
        <button 
          onClick={() => setIsOpen(true)}
          style={{
            background: "#10b981", color: "#fff", border: "none", borderRadius: "50%",
            width: "60px", height: "60px", fontSize: "28px", cursor: "pointer",
            boxShadow: "0 8px 32px rgba(0,0,0,0.3)", display: "flex", alignItems: "center", justifyContent: "center"
          }}
        >
          💬
        </button>
      )}

      {/* EXPANDED INTERACTIVE CHAT ENGINE SCREEN VIEWPORT */}
      {isOpen && (
        <div style={{
          width: "360px", height: "480px", background: "#1e293b", border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: "1rem", boxShadow: "0 12px 48px rgba(0,0,0,0.4)", display: "flex", flexDirection: "column", overflow: "hidden"
        }}>
          {/* header header */}
          <div style={{ background: "#0f172a", padding: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
            <span style={{ color: "#10b981", fontWeight: "bold", fontSize: "0.9rem" }}>Cotiviti Clinical Assistant</span>
            <button onClick={() => setIsOpen(false)} style={{ background: "transparent", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: "1rem" }}>✕</button>
          </div>

          {/* ACTIVE DISCUSSION TIMELINE GRID PANEL */}
          <div style={{ flex: 1, padding: "1rem", overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {messages.map((m, idx) => (
              <div key={idx} style={{
                alignSelf: m.sender === "user" ? "flex-end" : "flex-start",
                background: m.sender === "user" ? "#0284c7" : "rgba(255,255,255,0.05)",
                color: m.sender === "user" ? "#fff" : "#cbd5e1",
                padding: "0.75rem", borderRadius: "0.5rem", maxWidth: "80%", fontSize: "0.8rem", whiteSpace: "pre-wrap", lineHeight: "1.4"
              }}>
                {m.text}
              </div>
            ))}
          </div>

          {/* DYNAMIC ACTION INPUT BOX FIELD FOOTER CONTAINER */}
          <div style={{ padding: "0.75rem", background: "#0f172a", borderTop: "1px solid rgba(255,255,255,0.05)", display: "flex", gap: "0.5rem" }}>
            <input 
              type="text" 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
              placeholder={activeClaim ? `Ask about ${activeClaim.clm_id}…` : "Ask a compliance question…"}
              style={{ flex: 1, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "0.25rem", padding: "0.5rem", color: "#fff", fontSize: "0.8rem", outline: "none" }}
            />
            <button 
              onClick={handleSendMessage}
              disabled={sending}
              style={{ background: "#10b981", color: "#fff", border: "none", borderRadius: "0.25rem", padding: "0.5rem 1rem", fontSize: "0.8rem", cursor: "pointer", fontWeight: "bold" }}
            >
              {sending ? "..." : "Send"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

