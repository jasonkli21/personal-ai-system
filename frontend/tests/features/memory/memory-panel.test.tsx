import { fireEvent, render, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MemoryPanel } from "../../../src/features/memory/memory-panel";
import { authenticatedFetch } from "../../../src/lib/auth";

vi.mock("../../../src/lib/auth", () => ({ authenticatedFetch: vi.fn() }));
const fetcher = vi.mocked(authenticatedFetch);
const memory = { id: "memory-one", title: "Historical validation", kind: "procedure", historical_content: "Untrusted historical advice.", project: { project_id: "project-a", revision: "rev-a", branch: "main" }, authority: "tool_receipt_verified", verification: "verified", state_version: 3, expires_at: "tomorrow", source_ids: ["source-a"] };
const proposal = { id: "proposal-one", status: "pending", version: 0, expires_at: "tomorrow", content: { title: "Layout", claim: "Use the compact layout." } };
function response(value: unknown) { return Promise.resolve({ ok: true, json: async () => value } as Response); }
function inspect() {
  fetcher.mockImplementationOnce(() => response({ status: "found", items: [memory] }));
  fetcher.mockImplementationOnce(() => response({ status: "found", proposals: [proposal] }));
  fireEvent.click(screen.getByRole("button", { name: "Inspect memory" }));
  return screen.findByText("Historical validation");
}
afterEach(() => { cleanup(); vi.resetAllMocks(); });

describe("memory controls", () => {
  it("requires explicit forget confirmation, reports committed result and clears content", async () => {
    render(<MemoryPanel />);
    await inspect();
    expect(screen.getByRole("button", { name: "Forget" })).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    fetcher.mockImplementationOnce(() => response({ status: "applied" }));
    fireEvent.click(screen.getByRole("button", { name: "Forget" }));
    await screen.findByText(/Forgotten for future use/);
    expect(screen.queryByText("Historical validation")).not.toBeInTheDocument();
    const body = JSON.parse(fetcher.mock.calls[2][1]?.body as string);
    expect(body.expected_version).toBe(3);
    expect(body.confirm).toBe(true);
    expect(body.operation_id).toBeTruthy();
  });

  it("keeps the exact operation identity after unknown commit and transport failures", async () => {
    render(<MemoryPanel />);
    await inspect();
    fireEvent.click(screen.getByRole("checkbox"));
    fetcher.mockImplementationOnce(() => response({ status: "unknown_commit" }));
    fireEvent.click(screen.getByRole("button", { name: "Forget" }));
    await screen.findByRole("button", { name: "Reconcile original operation" });
    expect(screen.queryByText(/Forgotten for future use/)).not.toBeInTheDocument();
    fetcher.mockRejectedValueOnce(new Error("offline"));
    fireEvent.click(screen.getByRole("button", { name: "Reconcile original operation" }));
    await screen.findByText(/Outcome unknown/);
    expect(fetcher.mock.calls[2][1]?.body).toBe(fetcher.mock.calls[3][1]?.body);
    fetcher.mockImplementationOnce(() => response({ status: "applied", replayed: true }));
    fireEvent.click(screen.getByRole("button", { name: "Reconcile original operation" }));
    await screen.findByText(/Forgotten for future use/);
    expect(fetcher.mock.calls[4][1]?.body).toBe(fetcher.mock.calls[2][1]?.body);
  });

  it("reviews as unverified without displaying a saved claim", async () => {
    render(<MemoryPanel />);
    await inspect();
    fetcher.mockImplementationOnce(() => response({ status: "reviewed" }));
    fireEvent.click(screen.getByRole("button", { name: "Mark reviewed" }));
    await screen.findByText("Memory operation: reviewed.");
    expect(screen.queryByText(/saved/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Decision revision is unavailable/)).toBeInTheDocument();
  });

  it("fails closed on stale or unavailable inspection", async () => {
    render(<MemoryPanel />);
    fetcher.mockImplementationOnce(() => response({ status: "temporarily_unavailable", items: [] }));
    fetcher.mockImplementationOnce(() => response({ status: "found", proposals: [proposal] }));
    fireEvent.click(screen.getByRole("button", { name: "Inspect memory" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/inspection is unavailable/));
    expect(screen.queryByText("Unverified suggestion: Layout")).not.toBeInTheDocument();
  });
});
