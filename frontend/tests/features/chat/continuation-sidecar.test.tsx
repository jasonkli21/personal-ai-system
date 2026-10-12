import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ContinuationSidecar } from "../../../src/features/chat/continuation-sidecar/ContinuationSidecar";
import type { Message } from "../../../src/lib/api/conversations";
import type { PreparedExternalTurn } from "../../../src/lib/api/external-turns";

const target: Message = {
  id: "answer-1",
  conversation_id: "conversation-1",
  owner_id: "local",
  application_id: "personal_ai",
  workspace_id: null,
  role: "assistant",
  content: "Earlier response",
  status: "completed",
  created_at: "2026-10-10T00:00:00Z",
  parent_message_id: "user-1",
  supersedes_message_id: null,
  model: "gemini-fixture",
  error_code: null,
};

const prepared: PreparedExternalTurn = {
  message_id: "reservation-1",
  reservation_id: "reservation-1",
  mode: "manual_external",
  provider_id: null,
  model_id: null,
  package_fingerprint: "a".repeat(64),
  context_package: {
    schema_version: "context-package-v2",
    messages: [{ role: "user", content: "Continue from this answer." }],
    included_sources: [{ category: "conversation_history", item_count: 1, sensitivity: ["personal"], authority: ["user_owned"] }],
    excluded_sources: [],
    selected_message_count: 1,
    input_tokens: 42,
    counter_kind: "estimated",
    effective_sensitivity: "personal",
    maximum_sensitivity: "sensitive",
    policy_version: "personal-ai-context-policy-v2",
    expires_at: "2026-10-11T00:00:00Z",
    fingerprint: "a".repeat(64),
  },
  portable_prompt: "user:\nContinue from this answer.",
  connected_execution: null,
};

const connectedPrepared: PreparedExternalTurn = {
  ...prepared,
  mode: "connected_provider",
  provider_id: "openai_chatgpt_plan",
  model_id: "gpt-5-fixture",
  connected_execution: {
    owner_id: "local",
    application_id: "personal_ai",
    workspace_id: null,
    conversation_id: "conversation-1",
    reservation_id: "reservation-1",
    branch_digest: "b".repeat(64),
    source_authority_digest: "c".repeat(64),
    provider_id: "openai_chatgpt_plan",
    model_id: "gpt-5-fixture",
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
};

const preview = {
  selected_message_count: 1,
  planned_sources: [{ category: "conversation_history", operation: "read", fields: ["content"], max_results: 1 }],
  excluded_sources: [],
};

const contextCategories = [
  "global_profile", "domain_profile", "domain_current", "domain_history",
  "ai_memory", "conversation", "external_research", "tool_result", "client_context",
];

function executionOptions(
  modes: string[],
  explicitProfiles: unknown[] = [],
  policyOverrides: Record<string, unknown> = {},
) {
  return {
    modes,
    explicit_profiles: explicitProfiles,
    sidecar: {
      connected_provider_disclosure: {
        allowed: true,
        allowed_context_categories: contextCategories,
        maximum_sensitivity: "sensitive",
      },
      manual_external_disclosure: {
        allowed: true,
        allowed_context_categories: contextCategories,
        maximum_sensitivity: "sensitive",
      },
      manual_import_reuse: { allowed: true, maximum_sensitivity: "restricted" },
      copy_allowed: true,
      draft_insert_target_ids: ["host.edit_draft"],
      ...policyOverrides,
    },
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("continuation sidecar", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    Reflect.deleteProperty(navigator, "clipboard");
    window.sessionStorage.clear();
  });

  it("keeps manual copy/import available without the local bridge and labels imported facts", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(executionOptions(["automatic", "manual_external", "connected_provider"])))
      .mockResolvedValueOnce(jsonResponse(preview))
      .mockResolvedValueOnce(jsonResponse(prepared))
      .mockResolvedValueOnce(jsonResponse({ ...target, id: "reservation-1", content: "Imported result" }));
    vi.stubGlobal("fetch", fetchMock);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    const onSaved = vi.fn();
    const onDraftInsert = vi.fn();
    const onExternalCompleted = vi.fn();

    render(<ContinuationSidecar
      conversationId="conversation-1"
      scope={{ applicationId: "synthetic_app", workspaceId: "workspace-1" }}
      draftTargets={[
        { id: "host.edit_draft", label: "host editor" },
        { id: "host.undeclared", label: "unauthorized" },
      ]}
      onDraftInsert={onDraftInsert}
      target={target}
      onClose={vi.fn()}
      onAutomatic={vi.fn()}
      onExternalCompleted={onExternalCompleted}
      onSaved={onSaved}
    />);

    expect(await screen.findByRole("combobox", { name: "Execution mode" })).toHaveValue("manual_external");
    fireEvent.change(screen.getByLabelText("What should happen next?"), { target: { value: "Compare the earlier answer with current constraints." } });
    fireEvent.click(screen.getByLabelText("Omit Saved memory"));
    fireEvent.click(screen.getByRole("button", { name: "Preview bounded context" }));
    expect(await screen.findByText("Bounded context preview")).toBeInTheDocument();
    const previewCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/external-turns/preview"));
    expect(JSON.parse(String(previewCall?.[1]?.body))).toMatchObject({
      excluded_source_classes: ["ai_memory"],
      launch_context: {
        schema_version: "application-launch-v1",
        application_id: "synthetic_app",
        workspace_id: "workspace-1",
        entity_refs: [],
        view_id: null,
        conversation_id: "conversation-1",
        client_context: {},
      },
    });
    fireEvent.click(screen.getByLabelText("I reviewed this bounded preview"));
    fireEvent.click(screen.getByRole("button", { name: "Prepare and review exact package" }));
    expect(await screen.findByText(/Estimated 42 tokens/)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("I reviewed the exact prepared messages and source summary"));
    fireEvent.click(screen.getByRole("button", { name: "Copy prepared prompt" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("user:\nContinue from this answer."));

    fireEvent.change(screen.getByLabelText("Paste the external response"), { target: { value: "Imported text from a separate model" } });
    fireEvent.click(screen.getByRole("button", { name: "Insert response into host editor draft" }));
    expect(onDraftInsert).toHaveBeenCalledWith("host.edit_draft", "Imported text from a separate model");
    expect(screen.queryByRole("button", { name: "Insert response into unauthorized draft" })).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
    fireEvent.change(screen.getByLabelText("Provider label (optional, user-declared)"), { target: { value: "Example Provider" } });
    fireEvent.click(screen.getByRole("button", { name: "Import response into conversation" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    expect(onExternalCompleted).toHaveBeenCalledWith({
      ...target,
      id: "reservation-1",
      content: "Imported result",
    });
    expect(fetchMock).toHaveBeenNthCalledWith(4, "/api/conversations/conversation-1/external-turns/reservation-1/import", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        package_fingerprint: "a".repeat(64),
        text: "Imported text from a separate model",
        provider_label: "Example Provider",
      }),
    }));
    expect(fetchMock.mock.calls.some(([url]) => String(url).startsWith("http://127.0.0.1:8765"))).toBe(false);
    const apiCalls = fetchMock.mock.calls.filter(([url]) => String(url).startsWith("/api/"));
    expect(apiCalls.length).toBe(4);
    for (const [, init] of apiCalls) {
      const headers = new Headers(init?.headers as HeadersInit);
      expect(headers.get("X-Application-ID")).toBe("synthetic_app");
      expect(headers.get("X-Workspace-ID")).toBe("workspace-1");
    }
  });

  it("disables an explicitly selected manual turn above the reuse sensitivity ceiling", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(executionOptions(
      ["automatic", "manual_external"],
      [],
      { manual_import_reuse: { allowed: true, maximum_sensitivity: "personal" } },
    )));
    vi.stubGlobal("fetch", fetchMock);
    const importedTarget: Message = {
      ...target,
      attribution: {
        fact_source: "user_declared",
        execution_origin: "manual_import",
        provider_id: null,
        model_id: null,
        recorded_at: "2026-10-10T00:00:00Z",
        model_verified: false,
      },
      execution: { effective_sensitivity: "sensitive" },
    };

    render(<ContinuationSidecar
      conversationId="conversation-1"
      scope={{ applicationId: "synthetic_app", workspaceId: "workspace-1" }}
      target={importedTarget}
      onClose={vi.fn()}
      onAutomatic={vi.fn()}
      onSaved={vi.fn()}
    />);

    const include = screen.getByLabelText("Include this completed turn as a context candidate");
    await waitFor(() => expect(include).toBeDisabled());
    expect(screen.getByText(
      "This imported turn is excluded by the application’s manual reuse policy.",
    )).toBeInTheDocument();
  });

  it("uses the shared automatic continuation callback without preparing an external reservation", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(executionOptions(["automatic", "manual_external"])));
    vi.stubGlobal("fetch", fetchMock);
    const onAutomatic = vi.fn();
    render(<ContinuationSidecar
      conversationId="conversation-1"
      target={target}
      onClose={vi.fn()}
      onAutomatic={onAutomatic}
      onSaved={vi.fn()}
    />);
    fireEvent.change(await screen.findByRole("combobox", { name: "Execution mode" }), { target: { value: "automatic" } });
    fireEvent.change(screen.getByLabelText("What should happen next?"), { target: { value: "Extend this answer" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue with Personal AI" }));
    expect(onAutomatic).toHaveBeenCalledWith(
      "Extend this answer",
      target,
      true,
      { applicationId: "personal_ai", clientContext: {} },
      {
        schema_version: "application-launch-v1",
        application_id: "personal_ai",
        workspace_id: null,
        entity_refs: [],
        view_id: null,
        conversation_id: "conversation-1",
        client_context: {},
      },
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps manual external mode hidden when application policy denies disclosure", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(executionOptions(
      ["automatic", "manual_external"],
      [],
      {
        manual_external_disclosure: {
          allowed: false,
          allowed_context_categories: ["conversation"],
          maximum_sensitivity: "personal",
        },
        copy_allowed: false,
      },
    )));
    vi.stubGlobal("fetch", fetchMock);
    const onAutomatic = vi.fn();
    render(<ContinuationSidecar
      conversationId="conversation-1"
      scope={{ applicationId: "finance", workspaceId: "workspace-1" }}
      target={target}
      onClose={vi.fn()}
      onAutomatic={onAutomatic}
      onSaved={vi.fn()}
    />);

    const mode = await screen.findByRole("combobox", { name: "Execution mode" });
    expect(mode).toHaveValue("automatic");
    expect(screen.queryByRole("option", { name: /Manual external model/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continue with Personal AI" }));
    expect(onAutomatic).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("discards a connected package when its account-visible model disappears", async () => {
    const profile = {
      endpoint: { endpoint_profile_id: "chatgpt-plan", profile_version: 1 },
      provider_id: "openai_chatgpt_plan",
      external_transport_id: "chatgpt_local_v1",
      capabilities: ["streaming"],
      maximum_sensitivity: "sensitive",
    };
    const pairing = {
      caller_id: "caller-1",
      audience: "audience-1",
      connection_id: "connection-1",
      connection_revision: 1,
      expires_at: Math.floor(Date.now() / 1000) + 300,
      caller_authorization: "a".repeat(48),
    };
    const connection = {
      connection_id: "connection-1",
      state: "connected",
      plan_permission: true,
      revision: 1,
      remote_revocation: "unknown",
      account_label: "ChatGPT account · 12345678",
      usage: { state: "unknown", observed_at: null },
      recovery: {
        reconnect: "local_operator",
        switch_account: "local_operator_new_pairing",
        manage_usage: "provider_account_ui",
      },
    };
    let modelRefreshes = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/conversations/execution-options") {
        return jsonResponse(executionOptions(["automatic", "manual_external", "connected_provider"], [profile]));
      }
      if (url === "/api/conversations/conversation-1/external-turns/preview") return jsonResponse(preview);
      if (url === "http://127.0.0.1:8765/connection") return jsonResponse(connection);
      if (url === "http://127.0.0.1:8765/models") {
        modelRefreshes += 1;
        return jsonResponse({ models: modelRefreshes === 1 ? [{ slug: "gpt-5-fixture", display_name: "Fixture" }] : [] });
      }
      if (url === "/api/conversations/conversation-1/external-turns/prepare") return jsonResponse(connectedPrepared);
      if (url === "/api/conversations/conversation-1/external-turns/reservation-1/abandon") return jsonResponse(target);
      throw new Error(`Unexpected request ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ContinuationSidecar
      conversationId="conversation-1"
      target={target}
      onClose={vi.fn()}
      onAutomatic={vi.fn()}
      onSaved={vi.fn()}
    />);

    fireEvent.change(await screen.findByRole("combobox", { name: "Execution mode" }), { target: { value: "connected_provider" } });
    fireEvent.change(screen.getByLabelText("Temporary pairing response"), { target: { value: JSON.stringify(pairing) } });
    fireEvent.click(screen.getByRole("button", { name: "Verify local connection" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/Connected to ChatGPT account · 12345678/);

    fireEvent.click(screen.getByRole("button", { name: "Preview bounded context" }));
    await screen.findByText("Bounded context preview");
    fireEvent.click(screen.getByLabelText("I reviewed this bounded preview"));
    fireEvent.click(screen.getByRole("button", { name: "Prepare and review exact package" }));
    expect(await screen.findByText(/Estimated 42 tokens/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh account and models" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/selected model disappeared/i);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/conversations/conversation-1/external-turns/reservation-1/abandon",
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("shows local recovery steps when the paired account lacks plan-use permission", async () => {
    const pairing = {
      caller_id: "caller-1",
      audience: "audience-1",
      connection_id: "connection-1",
      connection_revision: 1,
      expires_at: Math.floor(Date.now() / 1000) + 300,
      caller_authorization: "a".repeat(48),
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/conversations/execution-options") {
        return jsonResponse(executionOptions(["automatic", "manual_external", "connected_provider"], [{
          endpoint: { endpoint_profile_id: "chatgpt-plan", profile_version: 1 },
          provider_id: "openai_chatgpt_plan",
          external_transport_id: "chatgpt_local_v1",
          capabilities: ["streaming"],
          maximum_sensitivity: "sensitive",
        }]));
      }
      if (url === "http://127.0.0.1:8765/connection") return jsonResponse({
        connection_id: "connection-1",
        state: "connected",
        plan_permission: false,
        revision: 1,
        remote_revocation: "unknown",
        account_label: "ChatGPT account · 12345678",
        usage: { state: "unknown", observed_at: null },
        recovery: {
          reconnect: "local_operator",
          switch_account: "local_operator_new_pairing",
          manage_usage: "provider_account_ui",
        },
      });
      throw new Error(`Unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ContinuationSidecar
      conversationId="conversation-1"
      target={target}
      onClose={vi.fn()}
      onAutomatic={vi.fn()}
      onSaved={vi.fn()}
    />);

    fireEvent.change(await screen.findByRole("combobox", { name: "Execution mode" }), { target: { value: "connected_provider" } });
    fireEvent.change(screen.getByLabelText("Temporary pairing response"), { target: { value: JSON.stringify(pairing) } });
    fireEvent.click(screen.getByRole("button", { name: "Verify local connection" }));
    await waitFor(() => expect(screen.getByLabelText("Temporary pairing response")).toHaveValue(""));
    expect(await screen.findByRole("link", { name: "Manage plan usage in ChatGPT" })).toHaveAttribute("href", "https://chatgpt.com/");
    fireEvent.click(screen.getByText("Reconnect this local account"));
    expect(screen.getByText(/enable-usage connection-1/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pair again after local recovery" }));
    expect(screen.getByLabelText("Temporary pairing response")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("blocks connected preparation while the local bridge reports a current usage limit", async () => {
    const pairing = {
      caller_id: "caller-1",
      audience: "audience-1",
      connection_id: "connection-1",
      connection_revision: 1,
      expires_at: Math.floor(Date.now() / 1000) + 300,
      caller_authorization: "a".repeat(48),
    };
    const profile = {
      endpoint: { endpoint_profile_id: "fixture-local", profile_version: 1 },
      provider_id: "fixture_provider",
      external_transport_id: "fixture_local_v1",
      capabilities: ["streaming"],
      maximum_sensitivity: "sensitive",
    };
    const transportAdapters = [{
      id: "fixture_local_v1",
      displayName: "Synthetic local provider",
      bridgeOrigin: "http://127.0.0.1:8765",
    }] as const;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/conversations/execution-options") {
        return jsonResponse(executionOptions(["automatic", "connected_provider"], [profile]));
      }
      if (url === "http://127.0.0.1:8765/connection") return jsonResponse({
        connection_id: "connection-1",
        state: "connected",
        plan_permission: true,
        revision: 1,
        remote_revocation: "unknown",
        account_label: "Local account",
        usage: { state: "limit", observed_at: new Date().toISOString() },
        recovery: { reconnect: "local_operator", switch_account: "local_operator_new_pairing", manage_usage: "provider_account_ui" },
      });
      if (url === "http://127.0.0.1:8765/models") return jsonResponse({ models: [{ slug: "model-1", display_name: "Model 1" }] });
      throw new Error(`Unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ContinuationSidecar
      conversationId="conversation-1"
      transportAdapters={transportAdapters}
      target={target}
      onClose={vi.fn()}
      onAutomatic={vi.fn()}
      onSaved={vi.fn()}
    />);

    fireEvent.change(await screen.findByRole("combobox", { name: "Execution mode" }), { target: { value: "connected_provider" } });
    fireEvent.change(screen.getByLabelText("Temporary pairing response"), { target: { value: JSON.stringify(pairing) } });
    fireEvent.click(screen.getByRole("button", { name: "Verify local connection" }));
    expect(await screen.findByText((_content, element) =>
      element?.tagName === "P" && element.textContent?.includes("Local account") === true && element.textContent.includes("limit"),
    )).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview bounded context" })).toBeDisabled();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/external-turns/dispatch"))).toBe(false);
  });

  it("reconciles an ambiguous prepare after reload and cancels by its retained idempotency key", async () => {
    const key = "10000000-0000-4000-8000-000000000001";
    window.sessionStorage.setItem("external-prepare:personal_ai::conversation-1", key);
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/conversations/execution-options") {
        return jsonResponse(executionOptions(["automatic", "manual_external"]));
      }
      if (url === `/api/conversations/conversation-1/external-turns/requests/${key}`) {
        return jsonResponse({
          state: "prepared",
          message_id: "reservation-1",
          package_fingerprint: "a".repeat(64),
          mode: "manual_external",
          expires_at: "2026-10-11T00:00:00Z",
        });
      }
      if (url === `/api/conversations/conversation-1/external-turns/requests/${key}/abandon`) {
        expect(init?.method).toBe("POST");
        return jsonResponse(target);
      }
      throw new Error(`Unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ContinuationSidecar
      conversationId="conversation-1"
      target={target}
      onClose={vi.fn()}
      onAutomatic={vi.fn()}
      onSaved={vi.fn()}
    />);

    expect(await screen.findByText("Canonical state: prepared")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel this prepared reservation and start fresh" }));
    await waitFor(() => expect(window.sessionStorage.getItem("external-prepare:personal_ai::conversation-1")).toBeNull());
    expect(await screen.findByRole("status")).toHaveTextContent(/canceled/i);
  });

  it("keeps canceled connected output transient and lets the user switch back to automatic", async () => {
    const pairing = {
      caller_id: "caller-1",
      audience: "audience-1",
      connection_id: "connection-1",
      connection_revision: 1,
      expires_at: Math.floor(Date.now() / 1000) + 300,
      caller_authorization: "a".repeat(48),
    };
    const profile = {
      endpoint: { endpoint_profile_id: "chatgpt-plan", profile_version: 1 },
      provider_id: "openai_chatgpt_plan",
      external_transport_id: "chatgpt_local_v1",
      capabilities: ["streaming"],
      maximum_sensitivity: "sensitive",
    };
    const connection = {
      connection_id: "connection-1",
      state: "connected",
      plan_permission: true,
      revision: 1,
      remote_revocation: "unknown",
      account_label: "ChatGPT account · 12345678",
      usage: { state: "unknown", observed_at: null },
      recovery: {
        reconnect: "local_operator",
        switch_account: "local_operator_new_pairing",
        manage_usage: "provider_account_ui",
      },
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/conversations/execution-options") return jsonResponse({
        ...executionOptions(["automatic", "manual_external", "connected_provider"], [profile]),
      });
      if (url === "/api/conversations/conversation-1/external-turns/preview") return jsonResponse(preview);
      if (url === "http://127.0.0.1:8765/connection") return jsonResponse(connection);
      if (url === "http://127.0.0.1:8765/models") return jsonResponse({ models: [{ slug: "gpt-5-fixture", display_name: "Fixture" }] });
      if (url === "/api/conversations/conversation-1/external-turns/prepare") return jsonResponse(connectedPrepared);
      if (url === "/api/conversations/conversation-1/external-turns/reservation-1/dispatch") return jsonResponse({ proof: { claims: {}, signature: "fixture" } });
      if (url === "http://127.0.0.1:8765/execute") {
        const signal = init?.signal;
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify({ kind: "delta", delta: "partial answer" })}\n\n`));
            signal?.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")), { once: true });
          },
        });
        return new Response(stream, { headers: { "Content-Type": "text/event-stream" } });
      }
      if (url === "/api/conversations/conversation-1/external-turns/reservation-1/fail") return jsonResponse(target);
      throw new Error(`Unexpected request ${init?.method ?? "GET"} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const onAutomatic = vi.fn();
    const onExternalDelta = vi.fn();
    render(<ContinuationSidecar
      conversationId="conversation-1"
      target={target}
      onClose={vi.fn()}
      onAutomatic={onAutomatic}
      onSaved={vi.fn()}
      onExternalDelta={onExternalDelta}
    />);

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
    await waitFor(() => expect(onExternalDelta).toHaveBeenCalledWith("reservation-1", "partial answer"));
    fireEvent.click(screen.getByRole("button", { name: "Cancel connected execution" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "/api/conversations/conversation-1/external-turns/reservation-1/fail",
      expect.objectContaining({ method: "POST" }),
    ));

    fireEvent.change(screen.getByRole("combobox", { name: "Execution mode" }), { target: { value: "automatic" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue with Personal AI" }));
    expect(onAutomatic).toHaveBeenCalledWith(
      "Continue from this answer.",
      target,
      true,
      { applicationId: "personal_ai", clientContext: {} },
      {
        schema_version: "application-launch-v1",
        application_id: "personal_ai",
        workspace_id: null,
        entity_refs: [],
        view_id: null,
        conversation_id: "conversation-1",
        client_context: {},
      },
    );
  });
});
