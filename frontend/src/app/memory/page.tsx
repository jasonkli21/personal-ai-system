import { MemoryPanel } from "../../features/memory/memory-panel";

export const dynamic = "force-dynamic";

export default function MemoryPage() {
  return <main style={{ maxWidth: "48rem", margin: "2rem auto", padding: "0 1rem" }}>
    <h1>Project memory</h1>
    <p>Historical knowledge is advisory. Pending suggestions are unverified. Reviewing a suggestion does not admit it as knowledge.</p>
    {process.env.MEMORY_USER_MANAGEMENT_ENABLED === "true"
      ? <MemoryPanel /> : <p>Memory controls are unavailable.</p>}
  </main>;
}
