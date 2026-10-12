import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Home from "../../src/app/page";
import type { Message } from "../../src/lib/api/conversations";

const fetchMock = vi.fn();
const conversation = { id: "conversation-1", owner_id: "local", title: "Project ideas", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
const contextCategories = [
  "global_profile", "domain_profile", "domain_current", "domain_history",
  "ai_memory", "conversation", "external_research", "tool_result", "client_context",
];
const sidecarActions = {
  connected_provider_disclosure: { allowed: true, allowed_context_categories: contextCategories, maximum_sensitivity: "sensitive" },
  manual_external_disclosure: { allowed: true, allowed_context_categories: contextCategories, maximum_sensitivity: "sensitive" },
  manual_import_reuse: { allowed: true, maximum_sensitivity: "restricted" },
  copy_allowed: true,
  draft_insert_target_ids: ["personal_ai.message_composer"],
};
function jsonResponse(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
function sseResponse(events: string[]) {
  return new Response(new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode(events.join(""))); controller.close(); } }), { headers: { "Content-Type": "text/event-stream" } });
}
const userMessage = { id: "user-1", conversation_id: conversation.id, owner_id: "local", application_id: "personal_ai", workspace_id: null, role: "user" as const, content: "Hello", status: "completed" as const, created_at: "2026-01-01T00:00:00Z", parent_message_id: null, supersedes_message_id: null, model: null, error_code: null };
const assistantMessage = { ...userMessage, id: "assistant-1", role: "assistant" as const, content: "", status: "streaming" as const, parent_message_id: userMessage.id };

describe("Home", () => {
  afterEach(cleanup);
  beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal("fetch", fetchMock); });
  it("renders an empty state with a new conversation action", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [] }));
    render(<Home />);
    expect(await screen.findByRole("heading", { name: "Start a conversation" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "New conversation" })).not.toHaveLength(0);
  });
  it("renders a loaded conversation list and selects a conversation", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [conversation] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [{ id: "message-1", conversation_id: conversation.id, owner_id: "local", role: "user", content: "Hello", status: "completed", created_at: "2026-01-01T00:00:00Z", parent_message_id: null, supersedes_message_id: null, model: null, error_code: null }] }));
    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    expect(await screen.findByText("Hello")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Project ideas" })).toHaveAttribute("aria-current", "page");
  });
  it("shows a recoverable API error", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ error: { message: "Service unavailable" } }, 503));
    render(<Home />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Service unavailable");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
  it("creates and opens a conversation", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [] }));
    fetchMock.mockResolvedValueOnce(jsonResponse(conversation, 201));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [] }));
    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "New conversation" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Project ideas" })).toBeInTheDocument());
  });
  it("accumulates deltas and replaces the streamed message with the completed response", async () => {
    const completed = { ...assistantMessage, content: "Hello there", status: "completed" as const };
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [conversation] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [] }));
    fetchMock.mockResolvedValueOnce(sseResponse([
      `event: message.created\ndata: ${JSON.stringify({ message: userMessage })}\n\n`,
      `event: message.created\ndata: ${JSON.stringify({ message: assistantMessage })}\n\n`,
      `event: response.delta\ndata: ${JSON.stringify({ message_id: assistantMessage.id, delta: "Hello " })}\n\n`,
      `event: response.delta\ndata: ${JSON.stringify({ message_id: assistantMessage.id, delta: "there" })}\n\n`,
      `event: response.completed\ndata: ${JSON.stringify({ message: completed })}\n\n`,
    ]));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [userMessage, completed] }));
    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    fireEvent.change(await screen.findByLabelText("Message"), { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Hello there")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/conversations/conversation-1/messages", expect.objectContaining({ method: "POST" }));
  });
  it("renders stream errors and prevents duplicate submissions while pending", async () => {
    let finishStream: (() => void) | undefined;
    const pendingStream = new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode(`event: message.created\ndata: ${JSON.stringify({ message: assistantMessage })}\n\n`)); finishStream = () => controller.enqueue(new TextEncoder().encode(`event: response.error\ndata: ${JSON.stringify({ message_id: assistantMessage.id, code: "provider_error", message: "The response failed safely." })}\n\n`)); } });
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [conversation] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [] }));
    fetchMock.mockResolvedValueOnce(new Response(pendingStream, { headers: { "Content-Type": "text/event-stream" } }));
    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    fireEvent.change(await screen.findByLabelText("Message"), { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("button", { name: "Sending…" })).toBeDisabled();
    await waitFor(() => expect(screen.getByRole("button", { name: "New conversation" })).toBeDisabled());
    finishStream?.();
    expect(await screen.findByRole("alert")).toHaveTextContent("The response failed safely.");
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeDisabled());
  });
  it("regenerates completed assistant messages", async () => {
    const completed = { ...assistantMessage, content: "New answer", status: "completed" as const };
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [conversation] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [userMessage, { ...assistantMessage, content: "Old answer", status: "completed" }] }));
    fetchMock.mockResolvedValueOnce(sseResponse([`event: response.completed\ndata: ${JSON.stringify({ message: completed })}\n\n`]));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [userMessage, completed] }));
    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    fireEvent.click(await screen.findByRole("button", { name: "Regenerate" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/conversations/conversation-1/messages/assistant-1/regenerate", expect.objectContaining({ method: "POST" })));
  });
  it("retries a failed response through its parent user message", async () => {
    const failed = { ...assistantMessage, content: "Partial", status: "failed" as const, error_code: "llm_timeout" };
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [conversation] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [userMessage, failed] }));
    fetchMock.mockResolvedValueOnce(sseResponse([]));
    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    fireEvent.click(await screen.findByRole("button", { name: "Retry response" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/conversations/conversation-1/messages/user-1/edit-and-retry",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ content: "Hello" }) }),
    ));
  });
  it("removes a superseded branch even when its replacement stream fails", async () => {
    const oldAnswer = { ...assistantMessage, content: "Old answer", status: "completed" as const };
    const descendant = { ...userMessage, id: "user-2", content: "Follow up", parent_message_id: oldAnswer.id };
    const replacement = { ...assistantMessage, id: "assistant-2", supersedes_message_id: oldAnswer.id };
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [conversation] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [userMessage, oldAnswer, descendant] }));
    fetchMock.mockResolvedValueOnce(sseResponse([
      `event: message.created\ndata: ${JSON.stringify({ message: replacement })}\n\n`,
      `event: response.delta\ndata: ${JSON.stringify({ message_id: replacement.id, delta: "Partial replacement" })}\n\n`,
      `event: response.error\ndata: ${JSON.stringify({ message_id: replacement.id, code: "llm_timeout", message: "Retry safely." })}\n\n`,
    ]));
    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    fireEvent.click(await screen.findByRole("button", { name: "Regenerate" }));
    expect(await screen.findByText("Partial replacement")).toBeInTheDocument();
    expect(screen.queryByText("Old answer")).not.toBeInTheDocument();
    expect(screen.queryByText("Follow up")).not.toBeInTheDocument();
  });
  it("edits a user message and retries it", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [conversation] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [userMessage] }));
    fetchMock.mockResolvedValueOnce(sseResponse([]));
    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    fireEvent.click(await screen.findByRole("button", { name: "Edit and retry" }));
    fireEvent.change(screen.getByLabelText("Edit message"), { target: { value: "Updated question" } });
    fireEvent.click(screen.getByRole("button", { name: "Retry edited message" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/conversations/conversation-1/messages/user-1/edit-and-retry", expect.objectContaining({ method: "POST" })));
  });

  it("preserves partial text and offers retry when the stream ends prematurely", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [conversation] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [] }));
    fetchMock.mockResolvedValueOnce(sseResponse([
      `event: message.created\ndata: ${JSON.stringify({ message: userMessage })}\n\n`,
      `event: message.created\ndata: ${JSON.stringify({ message: assistantMessage })}\n\n`,
      `event: response.delta\ndata: ${JSON.stringify({ message_id: assistantMessage.id, delta: "Partial answer" })}\n\n`,
    ]));
    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    fireEvent.change(await screen.findByLabelText("Message"), { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Partial answer")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("interrupted");
    expect(await screen.findByRole("button", { name: "Retry response" })).toBeEnabled();
  });

  it("renders connected deltas in the shared conversation view and clears them after interruption", async () => {
    const completedTarget = { ...assistantMessage, content: "Earlier response", status: "completed" as const };
    const pendingExternal = {
      ...assistantMessage,
      id: "reservation-1",
      content: "",
      status: "pending" as const,
      parent_message_id: "external-user-1",
    };
    const failedExternal = { ...pendingExternal, status: "failed" as const, error_code: "bridge_execution_interrupted" };
    let canonicalMessages: Message[] = [userMessage, completedTarget];
    const pairing = {
      caller_id: "caller-1",
      audience: "audience-1",
      connection_id: "connection-1",
      connection_revision: 1,
      expires_at: Math.floor(Date.now() / 1000) + 300,
      caller_authorization: "a".repeat(48),
    };
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/conversations") return jsonResponse({ conversations: [conversation] });
      if (url === `/api/conversations/${conversation.id}`) return jsonResponse({ conversation, messages: canonicalMessages });
      if (url === "/api/conversations/execution-options") return jsonResponse({
        modes: ["automatic", "manual_external", "connected_provider"],
        sidecar: sidecarActions,
        explicit_profiles: [{
          endpoint: { endpoint_profile_id: "chatgpt-plan", profile_version: 1 },
          provider_id: "openai_chatgpt_plan",
          external_transport_id: "chatgpt_local_v1",
          capabilities: ["streaming"],
          maximum_sensitivity: "sensitive",
        }],
      });
      if (url === "http://127.0.0.1:8765/connection") return jsonResponse({
        connection_id: "connection-1",
        state: "connected",
        plan_permission: true,
        revision: 1,
        remote_revocation: "unknown",
        account_label: "Local account",
        usage: { state: "unknown", observed_at: null },
        recovery: { reconnect: "local_operator", switch_account: "local_operator_new_pairing", manage_usage: "provider_account_ui" },
      });
      if (url === "http://127.0.0.1:8765/models") return jsonResponse({ models: [{ slug: "gpt-fixture", display_name: "Fixture" }] });
      if (url === `/api/conversations/${conversation.id}/external-turns/preview`) return jsonResponse({
        selected_message_count: 1,
        planned_sources: [],
        excluded_sources: [],
      });
      if (url === `/api/conversations/${conversation.id}/external-turns/prepare`) {
        canonicalMessages = [userMessage, completedTarget, pendingExternal];
        return jsonResponse({
          message_id: "reservation-1",
          reservation_id: "reservation-1",
          mode: "connected_provider",
          provider_id: "openai_chatgpt_plan",
          model_id: "gpt-fixture",
          package_fingerprint: "a".repeat(64),
          context_package: {
            schema_version: "context-package-v2",
            messages: [{ role: "user", content: "Continue from this answer." }],
            included_sources: [],
            excluded_sources: [],
            selected_message_count: 1,
            input_tokens: 42,
            counter_kind: "estimated",
            effective_sensitivity: "personal",
            maximum_sensitivity: "sensitive",
            policy_version: "personal-ai-context-policy-v2",
            expires_at: "2026-10-12T00:00:00Z",
            fingerprint: "a".repeat(64),
          },
          portable_prompt: null,
          connected_execution: {
            owner_id: "local",
            application_id: "personal_ai",
            workspace_id: null,
            conversation_id: conversation.id,
            reservation_id: "reservation-1",
            branch_digest: "b".repeat(64),
            source_authority_digest: "c".repeat(64),
            provider_id: "openai_chatgpt_plan",
            model_id: "gpt-fixture",
            execution_profile: {
              endpoint: { endpoint_profile_id: "chatgpt-plan", profile_version: 1 },
              endpoint_id: "endpoint-fixture",
              deployment_id: "deployment-fixture",
              serializer_id: "serializer-fixture",
              runtime_id: "runtime-fixture",
              external_transport_id: "chatgpt_local_v1",
            },
            connection_id: "connection-1",
            connection_revision: 1,
            messages: [{ role: "user", content: "Continue from this answer." }],
            effective_sensitivity: "personal",
            maximum_sensitivity: "sensitive",
            policy_version: "personal-ai-context-policy-v2",
            max_output_bytes: 80000,
            max_output_chars: 20000,
            timeout_seconds: 120,
          },
        });
      }
      if (url === `/api/conversations/${conversation.id}/external-turns/reservation-1/dispatch`) {
        return jsonResponse({ proof: { claims: {}, signature: "fixture" } });
      }
      if (url === "http://127.0.0.1:8765/execute") {
        const signal = init?.signal as AbortSignal;
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify({ kind: "delta", delta: "partial answer" })}\n\n`));
            signal.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")), { once: true });
          },
        });
        return new Response(stream, { headers: { "Content-Type": "text/event-stream" } });
      }
      if (url === `/api/conversations/${conversation.id}/external-turns/reservation-1/fail`) {
        canonicalMessages = [userMessage, completedTarget, failedExternal];
        return jsonResponse(failedExternal);
      }
      throw new Error(`Unexpected request ${init?.method ?? "GET"} ${url}`);
    });

    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    fireEvent.click(await screen.findByRole("button", { name: "Continue with…" }));
    fireEvent.change(await screen.findByRole("combobox", { name: "Execution mode" }), { target: { value: "connected_provider" } });
    fireEvent.change(screen.getByLabelText("Temporary pairing response"), { target: { value: JSON.stringify(pairing) } });
    fireEvent.click(screen.getByRole("button", { name: "Verify local connection" }));
    await screen.findByText(/account-visible model/i);
    fireEvent.click(screen.getByRole("button", { name: "Preview bounded context" }));
    await screen.findByText("Bounded context preview");
    fireEvent.click(screen.getByLabelText("I reviewed this bounded preview"));
    fireEvent.click(screen.getByRole("button", { name: "Prepare and review exact package" }));
    await screen.findByText(/Estimated 42 tokens/);
    fireEvent.click(screen.getByLabelText("I reviewed the exact prepared messages and source summary"));
    fireEvent.click(screen.getByRole("button", { name: "Send through local bridge" }));

    expect(await screen.findByText("partial answer")).toBeInTheDocument();
    expect(screen.queryByLabelText("Transient connected output")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel connected execution" }));
    await waitFor(() => expect(screen.queryByText("partial answer")).not.toBeInTheDocument());
  });

  it("aborts an active request when the chat unmounts", async () => {
    let signal: AbortSignal | undefined;
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [conversation] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [] }));
    fetchMock.mockImplementationOnce((_url, init) => {
      signal = init.signal;
      return Promise.resolve(new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(`event: message.created\ndata: ${JSON.stringify({ message: assistantMessage })}\n\n`));
          signal!.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")), { once: true });
        },
      })));
    });
    const view = render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    fireEvent.change(await screen.findByLabelText("Message"), { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("button", { name: "Sending…" });
    view.unmount();
    expect(signal?.aborted).toBe(true);
  });
  it("reloads a persisted user after preparation overflow and keeps edit-and-retry available", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [conversation] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ error: { code: "context_message_too_large", message: "Edit it to a shorter message and retry." } }, 422));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [userMessage] }));
    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    fireEvent.change(await screen.findByLabelText("Message"), { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Edit it to a shorter message and retry.");
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit and retry" })).toBeEnabled();
    expect(screen.queryByText("Thinking…")).not.toBeInTheDocument();
  });

  it("blocks old-conversation actions while opening another conversation and clears its editor", async () => {
    const other = { ...conversation, id: "conversation-2", title: "Other conversation" };
    let finishOpening!: (response: Response) => void;
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [conversation, other] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [userMessage] }));
    fetchMock.mockImplementationOnce(() => new Promise<Response>(resolve => { finishOpening = resolve; }));
    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    fireEvent.click(await screen.findByRole("button", { name: "Edit and retry" }));
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Draft" } });
    fireEvent.click(screen.getByRole("button", { name: "Other conversation" }));
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Retry edited message" })).toBeDisabled();
    fireEvent.submit(screen.getByLabelText("Message").closest("form")!);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    finishOpening(jsonResponse({ conversation: other, messages: [] }));
    await screen.findByRole("heading", { name: "Other conversation" });
    expect(screen.queryByLabelText("Edit message")).not.toBeInTheDocument();
  });

  it("does not submit Enter while an input-method composition is active", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversations: [conversation] }));
    fetchMock.mockResolvedValueOnce(jsonResponse({ conversation, messages: [] }));
    render(<Home />);
    fireEvent.click(await screen.findByRole("button", { name: "Project ideas" }));
    const composer = await screen.findByLabelText("Message");
    fireEvent.change(composer, { target: { value: "Composing" } });
    fireEvent.keyDown(composer, { key: "Enter", isComposing: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(composer).toHaveValue("Composing");
  });

});
