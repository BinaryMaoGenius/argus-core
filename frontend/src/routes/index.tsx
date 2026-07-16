import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  const [ping, setPing] = useState("Cliquez pour vérifier l’API.");
  const [memoryText, setMemoryText] = useState("Liste les fichiers Python avec os.listdir");
  const [memoryResult, setMemoryResult] = useState("");
  const [recallQuery, setRecallQuery] = useState("list files");
  const [recallResult, setRecallResult] = useState("");
  const [prompt, setPrompt] = useState("Bonjour, donne une réponse courte.");
  const [generateResult, setGenerateResult] = useState("");

  const callPing = async () => {
    const response = await fetch("/ping");
    const data = await response.json();
    setPing(JSON.stringify(data, null, 2));
  };

  const writeMemory = async () => {
    const response = await fetch("/memory/write", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: memoryText, layer: "working" }),
    });
    const data = await response.json();
    setMemoryResult(JSON.stringify(data, null, 2));
  };

  const recallMemory = async () => {
    const response = await fetch(`/memory/recall?q=${encodeURIComponent(recallQuery)}&top_k=5`);
    const data = await response.json();
    setRecallResult(JSON.stringify(data, null, 2));
  };

  const runGenerate = async () => {
    const response = await fetch("/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, model: "qwen2.5-coder:7b" }),
    });
    const data = await response.json();
    setGenerateResult(JSON.stringify(data, null, 2));
  };

  return (
    <main style={{ minHeight: "100vh", background: "#07111f", color: "#f8fafc", padding: "2rem" }}>
      <div style={{ maxWidth: 960, margin: "0 auto", display: "grid", gap: "1rem" }}>
        <section style={{ background: "#111827", padding: "1.5rem", borderRadius: "16px" }}>
          <h1 style={{ marginTop: 0 }}>COS MVP — Démo front-end</h1>
          <p style={{ color: "#cbd5e1" }}>
            Interface simple branchée directement sur l’API FastAPI locale.
          </p>
        </section>

        <section style={{ background: "#111827", padding: "1.5rem", borderRadius: "16px" }}>
          <h2>1. Vérifier l’API</h2>
          <button onClick={callPing} style={{ padding: "0.7rem 1rem", borderRadius: "8px", border: "none", cursor: "pointer", background: "#22c55e", color: "white" }}>
            Tester /ping
          </button>
          <pre style={{ background: "#020617", padding: "1rem", borderRadius: "8px", whiteSpace: "pre-wrap" }}>{ping}</pre>
        </section>

        <section style={{ background: "#111827", padding: "1.5rem", borderRadius: "16px" }}>
          <h2>2. Écrire en mémoire</h2>
          <textarea value={memoryText} onChange={(e) => setMemoryText(e.target.value)} style={{ width: "100%", minHeight: "90px", borderRadius: "8px", padding: "0.75rem", marginBottom: "0.75rem" }} />
          <button onClick={writeMemory} style={{ padding: "0.7rem 1rem", borderRadius: "8px", border: "none", cursor: "pointer", background: "#3b82f6", color: "white" }}>
            Enregistrer
          </button>
          <pre style={{ background: "#020617", padding: "1rem", borderRadius: "8px", whiteSpace: "pre-wrap" }}>{memoryResult}</pre>
        </section>

        <section style={{ background: "#111827", padding: "1.5rem", borderRadius: "16px" }}>
          <h2>3. Chercher dans la mémoire</h2>
          <input value={recallQuery} onChange={(e) => setRecallQuery(e.target.value)} style={{ width: "100%", padding: "0.75rem", borderRadius: "8px", marginBottom: "0.75rem" }} />
          <button onClick={recallMemory} style={{ padding: "0.7rem 1rem", borderRadius: "8px", border: "none", cursor: "pointer", background: "#8b5cf6", color: "white" }}>
            Rechercher
          </button>
          <pre style={{ background: "#020617", padding: "1rem", borderRadius: "8px", whiteSpace: "pre-wrap" }}>{recallResult}</pre>
        </section>

        <section style={{ background: "#111827", padding: "1.5rem", borderRadius: "16px" }}>
          <h2>4. Générer une réponse</h2>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} style={{ width: "100%", minHeight: "70px", borderRadius: "8px", padding: "0.75rem", marginBottom: "0.75rem" }} />
          <button onClick={runGenerate} style={{ padding: "0.7rem 1rem", borderRadius: "8px", border: "none", cursor: "pointer", background: "#f59e0b", color: "white" }}>
            Générer
          </button>
          <pre style={{ background: "#020617", padding: "1rem", borderRadius: "8px", whiteSpace: "pre-wrap" }}>{generateResult}</pre>
        </section>
      </div>
    </main>
  );
}
