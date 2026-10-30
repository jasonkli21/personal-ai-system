import { fireEvent, render, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MemoryPanel } from "../../../src/features/memory/memory-panel";
import { authenticatedFetch, getAuthIdentityKey } from "../../../src/lib/auth";

vi.mock("../../../src/lib/auth", () => ({
  authenticatedFetch: vi.fn(),
  getAuthIdentityKey: vi.fn(() => "https://issuer|actor-a"),
  subscribeAuth: vi.fn(() => () => undefined),
}));
const fetcher = vi.mocked(authenticatedFetch);
const memory = { id: "11111111-1111-4111-8111-111111111111", title: "Historical validation", kind: "procedure", historical_content: "Untrusted historical advice.", project: { project_id: "project-a", revision: "rev-a", branch: "main" }, authority: "tool_receipt_verified", verification: "verified", state_version: 3, expires_at: "tomorrow", source_ids: ["source-a"] };
const proposal = { id: "22222222-2222-4222-8222-222222222222", status: "pending", version: 0, expires_at: "tomorrow", content: { title: "Layout", claim: "Use the compact layout." } };
function response(value: unknown) { return Promise.resolve({ ok: true, json: async () => value } as Response); }
function inspect() {
  fetcher.mockImplementationOnce(() => response({ status: "found", items: [memory] }));
  fetcher.mockImplementationOnce(() => response({ status: "found", proposals: [proposal] }));
  fireEvent.click(screen.getByRole("button", { name: "Inspect memory" }));
  return screen.findByText("Historical validation");
}
afterEach(() => { cleanup(); sessionStorage.clear(); vi.clearAllMocks(); });

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

  it("restores the same opaque operation after reload and clears it on actor change", async () => {
    render(<MemoryPanel />);
    await inspect();
    fireEvent.click(screen.getByRole("checkbox"));
    fetcher.mockImplementationOnce(() => response({ status: "unknown_commit" }));
    fireEvent.click(screen.getByRole("button", { name: "Forget" }));
    await screen.findByRole("button", { name: "Reconcile original operation" });
    const saved = sessionStorage.getItem("memory-control.pending-operation.v1");
    expect(saved).toBeTruthy();
    expect(saved).not.toContain("historical_content");
    expect(saved).not.toContain("Untrusted historical advice.");

    const originalBody = fetcher.mock.calls[2][1]?.body;
    cleanup();
    render(<MemoryPanel />);
    await screen.findByRole("button", { name: "Reconcile original operation" });
    fetcher.mockImplementationOnce(() => response({ status: "applied", replayed: true }));
    fireEvent.click(screen.getByRole("button", { name: "Reconcile original operation" }));
    await screen.findByText(/Forgotten for future use/);
    expect(fetcher.mock.calls[3][1]?.body).toBe(originalBody);
    expect(sessionStorage.getItem("memory-control.pending-operation.v1")).toBeNull();

    cleanup();
    fetcher.mockReset();
    vi.mocked(getAuthIdentityKey).mockReturnValue("https://issuer|actor-a");
    render(<MemoryPanel />);
    await inspect();
    fetcher.mockImplementationOnce(() => response({ status: "unknown_commit" }));
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Forget" }));
    await screen.findByRole("button", { name: "Reconcile original operation" });
    vi.mocked(getAuthIdentityKey).mockReturnValue("https://issuer|actor-b");
    cleanup();
    render(<MemoryPanel />);
    await waitFor(() => expect(screen.queryByRole("button", { name: "Reconcile original operation" })).toBeNull());
    expect(sessionStorage.getItem("memory-control.pending-operation.v1")).toBeNull();
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
