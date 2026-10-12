import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MutationProposalPanel } from "../../../src/features/chat/continuation-sidecar/MutationProposalPanel";
import { mutationAction, readMutation, type MutationView } from "../../../src/lib/api/mutations";

vi.mock("../../../src/lib/api/mutations", () => ({ readMutation: vi.fn(), mutationAction: vi.fn() }));
const scope = { applicationId: "synthetic", workspaceId: "space" };
function value(state: MutationView["proposal"]["state"] = "validated", available = true): MutationView {
  return {
    binding: "a".repeat(64), apply_available: available,
    proposal: {
      schema_version: "mutation-proposal-view-v1", proposal_id: "proposal-1", revision: 2, state,
      intent: { target: { application_id: "synthetic", workspace_id: "space", entity_type: "note", entity_id: "note-1" },
        operation: { operation_id: "note.rename", version: 1 }, payload: { title: "New title" }, expected_domain_version: "v1", expires_at: "2099-01-01T00:00:00Z" },
      validation: state === "proposed" ? null : { valid: true, preview: "Rename note to New title", expires_at: "2099-01-01T00:00:00Z", code: "valid" },
      confirmation: state === "confirmed" ? { confirmation_id: "confirmation-1", binding: "a".repeat(64) } : null,
      outcome: null, terminal_code: null,
    },
  };
}
beforeEach(() => vi.mocked(readMutation).mockResolvedValue(value()));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

describe("typed mutation sidecar", () => {
  it("reviews, confirms exact binding, then applies with the saved confirmation", async () => {
    vi.mocked(mutationAction).mockResolvedValueOnce(value("confirmed"));
    const applied = value("applied", false);
    applied.proposal.outcome = { state: "applied", code: "committed", post_state: {
      target: applied.proposal.intent.target, domain_version: "v2", reference_id: "domain-receipt-1",
    } };
    vi.mocked(mutationAction).mockResolvedValueOnce(applied);
    render(<MutationProposalPanel proposalId="proposal-1" scope={scope} />);
    const confirm = await screen.findByRole("button", { name: "Confirm change" });
    expect(confirm).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Apply confirmed change" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(confirm);
    await waitFor(() => expect(mutationAction).toHaveBeenCalledWith("proposal-1", "confirm", scope, {
      binding: "a".repeat(64), confirmation_id: expect.any(String),
    }));
    fireEvent.click(await screen.findByRole("button", { name: "Apply confirmed change" }));
    await screen.findByText(/Authoritative result: domain-receipt-1/);
    expect(mutationAction).toHaveBeenLastCalledWith("proposal-1", "apply", scope, {
      confirmation_id: "confirmation-1", binding: "a".repeat(64),
    });
    expect(screen.queryByRole("button", { name: "Apply confirmed change" })).not.toBeInTheDocument();
  });

  it.each(["proposed", "rejected", "expired"] as const)("has no Apply for %s", async state => {
    vi.mocked(readMutation).mockResolvedValue(value(state, false));
    render(<MutationProposalPanel proposalId="proposal-1" scope={scope} />);
    await screen.findByText(`Status: ${state}`);
    expect(screen.queryByRole("button", { name: "Confirm change" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Apply confirmed change" })).not.toBeInTheDocument();
  });

  it("obeys canonical capability/policy availability and expiry", async () => {
    vi.mocked(readMutation).mockResolvedValue(value("validated", false));
    const { unmount } = render(<MutationProposalPanel proposalId="proposal-1" scope={scope} />);
    await screen.findByText("Status: validated");
    expect(screen.queryByRole("button", { name: "Confirm change" })).not.toBeInTheDocument();
    unmount();
    const expired = value("confirmed");
    expired.proposal.validation!.expires_at = "2020-01-01T00:00:00Z";
    vi.mocked(readMutation).mockResolvedValue(expired);
    render(<MutationProposalPanel proposalId="proposal-1" scope={scope} />);
    await screen.findByText("This proposal has expired.");
    expect(screen.queryByRole("button", { name: "Apply confirmed change" })).not.toBeInTheDocument();
  });

  it("reconciles an unknown outcome and never offers Apply", async () => {
    vi.mocked(readMutation).mockResolvedValue(value("uncertain", false));
    vi.mocked(mutationAction).mockResolvedValue(value("uncertain", false));
    render(<MutationProposalPanel proposalId="proposal-1" scope={scope} />);
    fireEvent.click(await screen.findByRole("button", { name: "Reconcile outcome" }));
    await waitFor(() => expect(mutationAction).toHaveBeenCalledWith("proposal-1", "reconcile", scope, undefined));
    expect(screen.queryByRole("button", { name: "Apply confirmed change" })).not.toBeInTheDocument();
  });

  it("fences double click and a lost apply response until status recovery", async () => {
    vi.mocked(readMutation).mockResolvedValue(value("confirmed"));
    let reject!: (reason: Error) => void;
    vi.mocked(mutationAction).mockReturnValue(new Promise((_resolve, fail) => { reject = fail; }));
    render(<MutationProposalPanel proposalId="proposal-1" scope={scope} />);
    const apply = await screen.findByRole("button", { name: "Apply confirmed change" });
    fireEvent.click(apply);
    fireEvent.click(apply);
    expect(mutationAction).toHaveBeenCalledTimes(1);
    reject(new Error("response_lost"));
    await screen.findByRole("alert");
    expect(screen.queryByRole("button", { name: "Apply confirmed change" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reconcile outcome" })).toBeInTheDocument();
  });

  it("hides a denied proposal and a proposal from another workspace", async () => {
    vi.mocked(readMutation).mockRejectedValueOnce(new Error("permission_revoked"));
    const { unmount } = render(<MutationProposalPanel proposalId="proposal-1" scope={scope} />);
    await screen.findByRole("alert");
    expect(screen.queryByText(/Rename note/)).not.toBeInTheDocument();
    unmount();
    vi.mocked(readMutation).mockResolvedValue(value());
    render(<MutationProposalPanel proposalId="proposal-1" scope={{ ...scope, workspaceId: "another" }} />);
    await waitFor(() => expect(readMutation).toHaveBeenLastCalledWith("proposal-1", { ...scope, workspaceId: "another" }));
    expect(screen.queryByText(/Rename note/)).not.toBeInTheDocument();
  });
});
