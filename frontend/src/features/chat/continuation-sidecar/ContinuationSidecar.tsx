"use client";

import { MutationProposalPanel } from "./MutationProposalPanel";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, type ApplicationScopeRequest } from "../../../lib/api/common";
import type { Message } from "../../../lib/api/conversations";
import {
  externalTurnEndpoints,
  type ApplicationLaunchContext,
  type BridgeConnection,
  type BridgeModel,
  type ContextSourceClass,
  type FederationChoiceOption,
  type FederationContextChoice,
  type PreparedExternalTurn,
  type SidecarActionOptions,
} from "../../../lib/api/external-turns";
import {
  createExternalTransportRegistry,
  DEFAULT_EXTERNAL_TRANSPORTS,
  supportedExternalProfiles,
  type ExternalTransportAdapter,
} from "../external-transport";
import { ContextPackageSummary } from "./ContextPackageSummary";
import { ConnectedProviderPanel } from "./ConnectedProviderPanel";
import { ManualExternalPanel } from "./ManualExternalPanel";
import { RecoveryPanel } from "./RecoveryPanel";
import { bridgeExecute, bridgeJson, recoveryStorageKey, validatePairing } from "./bridge-client";
import { useContinuationSidecar } from "./useContinuationSidecar";
import styles from "./continuation-sidecar.module.css";
import { createMutationCandidate, type MutationOperationRef } from "../../../lib/api/mutations";

type Props = {
  mutationProposalId?: string;
  mutationCandidateOperation?: MutationOperationRef;
  conversationId: string;
  scope?: ApplicationScopeRequest;
  launchContext?: ApplicationLaunchContext;
  draftTargets?: readonly { id: string; label: string }[];
  onDraftInsert?: (targetId: string, text: string) => void;
  transportAdapters?: readonly ExternalTransportAdapter[];
  federationChoices?: readonly FederationChoiceOption[];
  target: Message;
  onClose: () => void;
  onAutomatic: (instruction: string, target: Message, includeTarget: boolean, scope: ApplicationScopeRequest, launchContext: ApplicationLaunchContext, federationContext: FederationContextChoice[]) => void;
  onExternalPrepared?: (messageId: string) => Promise<void>;
  onExternalDelta?: (messageId: string, delta: string) => void;
  onExternalCompleted?: (message: Message) => void;
  onExternalInterrupted?: (messageId: string) => void;
  onSaved: () => void;
};

function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "The request could not be completed. Inspect the conversation before trying again.";
}

const NARROWABLE_SOURCES: { id: ContextSourceClass; label: string }[] = [
  { id: "conversation", label: "Conversation history" },
  { id: "ai_memory", label: "Saved memory" },
  { id: "global_profile", label: "Shared profile" },
  { id: "client_context", label: "Client context" },
  { id: "external_research", label: "Research and evidence" },
  { id: "domain_profile", label: "Domain profile" },
  { id: "domain_current", label: "Current domain context" },
  { id: "domain_history", label: "Domain history" },
  { id: "tool_result", label: "Tool results" },
];

const DEFAULT_SCOPE: ApplicationScopeRequest = { applicationId: "personal_ai" };
const EMPTY_FEDERATION_CHOICES: readonly FederationChoiceOption[] = [];
const noop = () => undefined;

const CONTEXT_CLASSES: ContextSourceClass[] = [
  "global_profile", "domain_profile", "domain_current", "domain_history", "ai_memory",
  "conversation", "external_research", "tool_result", "client_context",
];
const SENSITIVITY_RANK: Record<"public" | "personal" | "sensitive" | "restricted", number> = {
  public: 0,
  personal: 1,
  sensitive: 2,
  restricted: 3,
};

function launchFor(
  conversationId: string,
  scope: ApplicationScopeRequest,
  launchContext?: ApplicationLaunchContext,
): ApplicationLaunchContext {
  return launchContext ?? {
    schema_version: "application-launch-v1",
    application_id: scope.applicationId ?? "personal_ai",
    workspace_id: scope.workspaceId ?? null,
    entity_refs: [],
    view_id: null,
    conversation_id: conversationId,
    client_context: scope.clientContext ?? {},
  };
}
const noopPrepared = async () => undefined;

export function ContinuationSidecar({ mutationProposalId, mutationCandidateOperation, conversationId, scope = DEFAULT_SCOPE, launchContext, draftTargets = [], onDraftInsert, transportAdapters = DEFAULT_EXTERNAL_TRANSPORTS, federationChoices = EMPTY_FEDERATION_CHOICES, target, onClose, onAutomatic, onExternalPrepared = noopPrepared, onExternalDelta = noop, onExternalCompleted = noop, onExternalInterrupted = noop, onSaved }: Props) {
  const {
    options, setOptions,
    mode, setMode,
    instruction, setInstruction,
    includeTarget, setIncludeTarget,
    excludedSources, setExcludedSources,
    selectedFederationChoiceIds, setSelectedFederationChoiceIds,
    preview, setPreview,
    previewReviewed, setPreviewReviewed,
    finalPackageReviewed, setFinalPackageReviewed,
    recovery, setRecovery,
    recoveryKey, setRecoveryKey,
    prepared, setPrepared,
    providerLabel, setProviderLabel,
    modelLabel, setModelLabel,
    importText, setImportText,
    pairingText, setPairingText,
    pairing, setPairing,
    bridgeConnection, setBridgeConnection,
    bridgeModels, setBridgeModels,
    selectedModel, setSelectedModel,
    selectedProfile, setSelectedProfile,
    savedCompletion, setSavedCompletion,
    busy, setBusy,
    status, setStatus,
    error, setError,
    copied, setCopied,
  } = useContinuationSidecar();
  const transportRegistry = useMemo(
    () => createExternalTransportRegistry(transportAdapters),
    [transportAdapters],
  );
  const sidecar = useRef<HTMLElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const bridgeRequest = useRef<AbortController | null>(null);
  const preparedRef = useRef<PreparedExternalTurn | null>(null);
  const candidateRequestPending = useRef(false);
  const [candidateProposalId, setCandidateProposalId] = useState<string | null>(null);
  const [candidateBusy, setCandidateBusy] = useState(false);
  const [candidateError, setCandidateError] = useState<string | null>(null);
  const effectiveLaunch = useMemo(
    () => launchFor(conversationId, scope, launchContext),
    [conversationId, scope, launchContext],
  );
  const requestScope = useMemo(
    () => ({ ...scope, clientContext: effectiveLaunch.client_context }),
    [scope, effectiveLaunch],
  );
  const actionOptions: SidecarActionOptions | null = options?.sidecar ?? null;
  const federationChoiceById = useMemo(
    () => new Map(federationChoices.map(option => [option.id, option])),
    [federationChoices],
  );
  const selectedFederationChoices = selectedFederationChoiceIds
    .map(id => federationChoiceById.get(id))
    .filter((option): option is FederationChoiceOption => option !== undefined);
  const selectedFederationContext = selectedFederationChoices.map(option => option.choice);

  useEffect(() => {
    setSelectedFederationChoiceIds(current => {
      const next = current.filter(id => federationChoiceById.has(id)).slice(0, 4);
      return next.length === current.length && next.every((id, index) => id === current[index])
        ? current
        : next;
    });
  }, [federationChoiceById]);

  useEffect(() => {
    let cancelled = false;
    void externalTurnEndpoints.executionOptions(undefined, requestScope).then(value => {
      if (cancelled) return;
      setOptions(value);
      setMode(
        value.modes.includes("manual_external")
          && value.sidecar.manual_external_disclosure.allowed
          && value.sidecar.copy_allowed
          ? "manual_external"
          : "automatic",
      );
      setSelectedProfile(supportedExternalProfiles(value.explicit_profiles, transportAdapters)[0]?.endpoint.endpoint_profile_id ?? "");
      setStatus("Choose how to continue. Automatic and manual modes work without the local bridge.");
    }).catch(failure => {
      if (!cancelled) {
        setError(errorMessage(failure));
        setStatus("Execution options could not be loaded.");
      }
    });
    heading.current?.focus();
    return () => { cancelled = true; };
  }, [requestScope, transportAdapters]);

  useEffect(() => {
    const key = recoveryStorageKey(conversationId, scope);
    const idempotencyKey = window.sessionStorage.getItem(key);
    if (!idempotencyKey) return;
    setRecoveryKey(idempotencyKey);
    void externalTurnEndpoints.reconcileExternal(conversationId, idempotencyKey, undefined, requestScope)
      .then(result => {
        if (["not_found", "not_external", "cancelled", "completed"].includes(result.state)) {
          window.sessionStorage.removeItem(key);
          setRecoveryKey(null);
          setRecovery(null);
          if (result.state === "completed" && result.message_id) {
            onExternalInterrupted(result.message_id);
            setStatus("The earlier preparation already completed. The canonical conversation was refreshed.");
          } else if (result.state === "cancelled") {
            setStatus("The earlier preparation was canceled. Review context again before starting fresh.");
          }
        } else {
          setRecovery(result);
          setStatus("Recovered canonical status for an earlier prepare request.");
        }
      })
      .catch(() => setStatus("Checking whether an earlier prepare request committed…"));
  }, [conversationId, requestScope, onExternalInterrupted]);

  useEffect(() => () => {
    bridgeRequest.current?.abort();
    const current = preparedRef.current;
    if (current) {
      void externalTurnEndpoints.abandonExternal(conversationId, current.message_id, current.package_fingerprint, undefined, requestScope).catch(() => undefined);
    }
  }, [conversationId, requestScope]);

  useEffect(() => {
    const element = sidecar.current;
    if (!element) return;
    const container = element;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(container.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary',
      ));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === heading.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !container.contains(document.activeElement))) {
        event.preventDefault();
        first.focus();
      }
    }
    element.addEventListener("keydown", onKeyDown);
    return () => element.removeEventListener("keydown", onKeyDown);
  }, [busy, onClose]);

  // The transport discriminator selects the narrow adapter. Provider identity remains data.
  const profiles = supportedExternalProfiles(options?.explicit_profiles ?? [], transportAdapters);
  const selectedProfileOption = profiles.find(profile => profile.endpoint.endpoint_profile_id === selectedProfile);
  const selectedTransport = selectedProfileOption
    ? transportRegistry.get(selectedProfileOption.external_transport_id)
    : undefined;
  const connectedAvailable = !!options?.modes.includes("connected_provider")
    && !!actionOptions?.connected_provider_disclosure.allowed && profiles.length > 0;
  const manualAvailable = !!options?.modes.includes("manual_external")
    && !!actionOptions?.manual_external_disclosure.allowed && !!actionOptions.copy_allowed;
  const manualImportTarget = target.attribution?.execution_origin === "manual_import";
  const targetSensitivity = target.execution?.effective_sensitivity;
  const manualTargetPolicy = actionOptions?.manual_import_reuse;
  const manualTargetDenied = manualImportTarget && (
    !manualTargetPolicy?.allowed
    || !targetSensitivity
    || SENSITIVITY_RANK[targetSensitivity] > SENSITIVITY_RANK[manualTargetPolicy.maximum_sensitivity]
  );
  const includeTargetEffective = includeTarget && !manualTargetDenied;
  const currentDisclosure = mode === "connected_provider"
    ? actionOptions?.connected_provider_disclosure
    : actionOptions?.manual_external_disclosure;
  const policyExcludedSources = CONTEXT_CLASSES.filter(
    source => !currentDisclosure?.allowed_context_categories.includes(source),
  );
  const permittedDraftTargets = draftTargets.filter(
    item => actionOptions?.draft_insert_target_ids.includes(item.id),
  );

  async function discardPrepared() {
    bridgeRequest.current?.abort();
    bridgeRequest.current = null;
    if (prepared) {
      try {
        await externalTurnEndpoints.abandonExternal(conversationId, prepared.message_id, prepared.package_fingerprint, undefined, requestScope);
      } catch {
        // A stale or already terminal reservation cannot be reused; preparation will revalidate.
      }
      onExternalInterrupted(prepared.message_id);
    }
    preparedRef.current = null;
    setPrepared(null);
    setSavedCompletion(null);
    setFinalPackageReviewed(false);
    setImportText("");
    setError(null);
    setStatus("Prepared turn discarded. Prepare a fresh turn after reviewing context.");
  }

  function submitAutomatic(event: FormEvent) {
    event.preventDefault();
    if (!instruction.trim() || busy) return;
    onAutomatic(instruction.trim(), target, includeTargetEffective, requestScope, effectiveLaunch, selectedFederationContext);
  }

  function requestFor(modeChoice: "manual_external" | "connected_provider", idempotencyKey: string) {
    let choice: Parameters<typeof externalTurnEndpoints.prepareExternal>[1]["choice"];
      if (modeChoice === "manual_external") choice = { mode: "manual_external" };
    else {
      if (!pairing || !bridgeConnection || !selectedModel || !selectedProfile) throw new Error("Connect an eligible local bridge account and choose a model.");
      if (bridgeConnection.usage?.state === "limit") throw new Error("The local account reports a current usage limit. Manage or refresh usage before sending.");
      const profile = profiles.find(item => item.endpoint.endpoint_profile_id === selectedProfile);
      if (!profile || !transportRegistry.has(profile.external_transport_id) || pairing.connection_id !== bridgeConnection.connection_id || pairing.connection_revision !== bridgeConnection.revision) {
        throw new Error("The local account changed. Refresh its connection and choose again.");
      }
      choice = {
        mode: "connected_provider",
        endpoint: profile.endpoint,
        model_id: selectedModel,
        connection_id: pairing.connection_id,
        connection_revision: pairing.connection_revision,
        caller_id: pairing.caller_id,
        audience: pairing.audience,
      };
    }
    return {
      content: instruction.trim(),
      idempotency_key: idempotencyKey,
      choice,
      candidate_message_ids: includeTargetEffective ? [target.id] : [],
      launch_context: effectiveLaunch,
      excluded_source_classes: [...new Set([...excludedSources, ...policyExcludedSources])],
      ...(selectedFederationContext.length > 0 ? { federation_context: selectedFederationContext } : {}),
    };
  }

  async function previewTurn(event: FormEvent) {
    event.preventDefault();
    if (!instruction.trim() || busy || prepared || mode === "automatic") return;
    setBusy(true);
    setError(null);
    setStatus("Previewing the authorized planner selection. This does not create a reservation.");
    try {
      const request = requestFor(mode, crypto.randomUUID());
      const next = await externalTurnEndpoints.previewExternal(conversationId, request, undefined, requestScope);
      setPreview(next);
      setPreviewReviewed(false);
      setStatus("Preview ready. It is advisory; canonical preparation will replan and reauthorize.");
    } catch (failure) {
      setError(errorMessage(failure));
      setStatus("Context preview could not be created.");
    } finally {
      setBusy(false);
    }
  }

  async function prepareTurn(event: FormEvent) {
    event.preventDefault();
    if (!instruction.trim() || busy || prepared || !preview || !previewReviewed || recovery) return;
    setBusy(true);
    setError(null);
    setStatus("Preparing and revalidating the canonical context package…");
    const storageKey = recoveryStorageKey(conversationId, scope);
    const idempotencyKey = crypto.randomUUID();
    window.sessionStorage.setItem(storageKey, idempotencyKey);
    setRecoveryKey(idempotencyKey);
    try {
      const request = requestFor(mode as "manual_external" | "connected_provider", idempotencyKey);
      const next = await externalTurnEndpoints.prepareExternal(conversationId, request, undefined, requestScope);
      window.sessionStorage.removeItem(storageKey);
      setRecoveryKey(null);
      setRecovery(null);
      preparedRef.current = next;
      setPrepared(next);
      setFinalPackageReviewed(false);
      await onExternalPrepared(next.message_id);
      setStatus("Canonical package prepared. Review the exact messages and sources before copying, importing or dispatching.");
    } catch (failure) {
      setError(errorMessage(failure));
      setStatus("The prepare response may have been lost. Checking the canonical reservation before allowing another attempt.");
      try {
        const result = await externalTurnEndpoints.reconcileExternal(conversationId, idempotencyKey, undefined, requestScope);
        if (result.state === "not_found") {
          window.sessionStorage.removeItem(storageKey);
          setRecoveryKey(null);
        } else {
          setRecovery(result);
        }
      } catch {
        // Retain the unguessable key for deterministic reconciliation after reload.
      }
    } finally {
      setBusy(false);
    }
  }

  async function abandonRecoveredPreparation() {
    if (!recoveryKey || busy) return;
    setBusy(true);
    try {
      await externalTurnEndpoints.abandonExternalByKey(conversationId, recoveryKey, undefined, requestScope);
      window.sessionStorage.removeItem(recoveryStorageKey(conversationId, scope));
      setRecovery(null);
      setRecoveryKey(null);
      setPreview(null);
      setPreviewReviewed(false);
      setStatus("The ambiguous prepared reservation was canceled. Review the context again before starting a fresh preparation.");
    } catch (failure) {
      setError(errorMessage(failure));
      setStatus("The canonical reservation changed. Reconcile again or reopen the conversation.");
    } finally {
      setBusy(false);
    }
  }

  async function importManual(event: FormEvent) {
    event.preventDefault();
    if (!prepared || !importText.trim() || busy) return;
    setBusy(true);
    setError(null);
    setStatus("Importing your response into this conversation…");
    try {
      const completed = await externalTurnEndpoints.importManual(conversationId, prepared.message_id, {
        package_fingerprint: prepared.package_fingerprint,
        text: importText.trim(),
        ...(providerLabel.trim() ? { provider_label: providerLabel.trim() } : {}),
        ...(modelLabel.trim() ? { model_label: modelLabel.trim() } : {}),
      }, undefined, requestScope);
      onExternalCompleted(completed);
      preparedRef.current = null;
      setPrepared(null);
      setImportText("");
      setStatus("Imported as a user-supplied manual external response. Provider and model labels are unverified.");
      onSaved();
    } catch (failure) {
      setError(errorMessage(failure));
      setStatus("The reservation may be stale or the response was not saved. Reopen the conversation to inspect canonical state.");
    } finally {
      setBusy(false);
    }
  }

  async function connectBridge(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (!selectedTransport) throw new Error("external_transport_unavailable");
      const parsed = validatePairing(JSON.parse(pairingText));
      if (parsed.expires_at * 1000 <= Date.now()) throw new Error("This local pairing has expired. Pair again from the local bridge.");
      setPairing(parsed);
      setPairingText("");
      const connection = await bridgeJson<BridgeConnection>("/connection", parsed, selectedTransport);
      if (
        connection.state !== "connected" ||
        connection.connection_id !== parsed.connection_id || connection.revision !== parsed.connection_revision
      ) throw new Error("The paired account is disconnected or changed. Reconnect locally and pair again.");
      setBridgeConnection(connection);
      if (!connection.plan_permission) {
        setBridgeModels([]);
        setSelectedModel("");
        setStatus("This local account has no plan-use permission yet. Use the recovery controls below, then pair the updated connection.");
        return;
      }
      const modelsResult = await bridgeJson<{ models: BridgeModel[] }>("/models", parsed, selectedTransport);
      setBridgeModels(modelsResult.models);
      setSelectedModel(modelsResult.models[0]?.slug ?? "");
      setStatus(`Connected to ${connection.account_label}. The local runtime still checks model compatibility and disclosure policy at send time.`);
    } catch {
      setPairing(null);
      setBridgeConnection(null);
      setBridgeModels([]);
      setError("The local bridge could not be verified. Check its origin, pairing expiry, connection status and browser loopback access.");
      setStatus("Connected mode is unavailable. Manual external copy/import remains available.");
    } finally {
      setBusy(false);
    }
  }

  async function refreshBridge() {
    if (!pairing) return;
    if (!selectedTransport) return;
    setBusy(true);
    setError(null);
    try {
      const connection = await bridgeJson<BridgeConnection>("/connection", pairing, selectedTransport);
      if (connection.revision !== pairing.connection_revision || connection.state !== "connected") {
        if (prepared) await discardPrepared();
        setPairing(null);
        setBridgeConnection(null);
        setBridgeModels([]);
        throw new Error("The account changed; pair this origin with the current connection again.");
      }
      if (!connection.plan_permission) {
        if (prepared) await discardPrepared();
        setBridgeConnection(connection);
        setBridgeModels([]);
        setSelectedModel("");
        setStatus("Plan-use permission is not enabled for this local account. Use the recovery controls below, then pair again.");
        return;
      }
      const modelsResult = await bridgeJson<{ models: BridgeModel[] }>("/models", pairing, selectedTransport);
      if (prepared && !modelsResult.models.some(model => model.slug === selectedModel)) {
        await discardPrepared();
        setSelectedModel(modelsResult.models[0]?.slug ?? "");
        throw new Error("The selected model disappeared. The prepared package was discarded; choose a current model and prepare again.");
      }
      setBridgeConnection(connection);
      setBridgeModels(modelsResult.models);
      setStatus(`Refreshed ${connection.account_label} and its account-visible model list.`);
    } catch (failure) {
      setError(
        failure instanceof Error && (failure.message.includes("changed") || failure.message.includes("disappeared"))
          ? failure.message
          : "The local bridge could not be refreshed.",
      );
    } finally {
      setBusy(false);
    }
  }

  function prepareBridgeRepair() {
    bridgeRequest.current?.abort();
    setPairing(null);
    setBridgeConnection(null);
    setBridgeModels([]);
    setSelectedModel("");
    setPairingText("");
    setStatus("Reconnect or enable plan use in the local bridge terminal, then pair this browser again.");
  }

  async function markConnectedInterrupted(turn: PreparedExternalTurn) {
    try {
      await externalTurnEndpoints.failExternal(conversationId, turn.message_id, turn.package_fingerprint, undefined, requestScope);
    } catch {
      try { await externalTurnEndpoints.abandonExternal(conversationId, turn.message_id, turn.package_fingerprint, undefined, requestScope); } catch { /* Canonical state may already be terminal. */ }
    }
    preparedRef.current = null;
    setPrepared(null);
    onExternalInterrupted(turn.message_id);
  }

  async function saveConnectedOutput(
    turn: PreparedExternalTurn,
    completion: { text: string; latencyMs: number; inputTokens?: number; outputTokens?: number },
  ) {
    setBusy(true);
    setError(null);
    setStatus("Saving the completed connected response through the shared turn finalizer…");
    try {
      const completed = await externalTurnEndpoints.completeConnected(conversationId, turn.message_id, {
        package_fingerprint: turn.package_fingerprint,
        text: completion.text,
        latency_ms: completion.latencyMs,
        ...(completion.inputTokens !== undefined ? { input_tokens: completion.inputTokens } : {}),
        ...(completion.outputTokens !== undefined ? { output_tokens: completion.outputTokens } : {}),
      }, undefined, requestScope);
      onExternalCompleted(completed);
      preparedRef.current = null;
      setPrepared(null);
      setSavedCompletion(null);
      setFinalPackageReviewed(false);
      setStatus("Completed response saved with connected-local and client-reported attribution.");
      onSaved();
    } catch (failure) {
      setSavedCompletion(completion);
      setError(errorMessage(failure));
      setStatus("The provider response is still transient here. Retry saving this same response; do not send it again.");
    } finally {
      setBusy(false);
    }
  }

  async function sendConnected() {
    if (!prepared?.connected_execution || !pairing || busy) return;
    if (bridgeConnection?.usage?.state === "limit") {
      setError("The local account reports a current usage limit. Manage or refresh usage before requesting a dispatch grant.");
      setStatus("Connected dispatch is paused while the local usage limit is active.");
      return;
    }
    const connectedExecution = prepared.connected_execution;
    const adapter = transportRegistry.get(connectedExecution.execution_profile.external_transport_id ?? "");
    const profile = profiles.find(item => item.endpoint.endpoint_profile_id === selectedProfile);
    if (!adapter || !profile || profile.external_transport_id !== adapter.id || !bridgeConnection || bridgeConnection.revision !== pairing.connection_revision) {
      setError("The selected account or execution profile changed. Discard this package and prepare again.");
      return;
    }
    setBusy(true);
    setError(null);
    const controller = new AbortController();
    bridgeRequest.current = controller;
    const turn = prepared;
    try {
      setStatus("Requesting a short-lived dispatch grant…");
      const { proof } = await externalTurnEndpoints.dispatchExternal(conversationId, turn.message_id, connectedExecution, controller.signal, requestScope);
      setStatus("Sending the authorized package to the paired local bridge…");
      const result = await bridgeExecute(connectedExecution, proof, pairing, adapter, controller.signal, delta => {
        onExternalDelta(turn.message_id, delta);
        setStatus("Receiving transient output from the local bridge…");
      });
      if (bridgeRequest.current === controller) bridgeRequest.current = null;
      const completion = {
        text: result.text,
        latencyMs: result.latencyMs,
        ...(typeof result.terminal.usage?.input_tokens === "number" ? { inputTokens: result.terminal.usage.input_tokens } : {}),
        ...(typeof result.terminal.usage?.output_tokens === "number" ? { outputTokens: result.terminal.usage.output_tokens } : {}),
      };
      setSavedCompletion(completion);
      await saveConnectedOutput(turn, completion);
    } catch (failure) {
      if (controller.signal.aborted) {
        setStatus("Connected execution was cancelled. Shared-view partial output was cleared and the send is recorded as uncertain.");
      } else {
        setError("The local bridge did not return a complete response. Transient output was cleared; the external effect may be uncertain.");
        setStatus(errorMessage(failure));
      }
      await markConnectedInterrupted(turn);
    } finally {
      if (bridgeRequest.current === controller) bridgeRequest.current = null;
      setBusy(false);
    }
  }

  async function copyText(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setError("Clipboard access is unavailable. Select the prepared text and copy it manually.");
    }
  }

  function insertIntoDraft(targetId: string, text: string) {
    if (!onDraftInsert || !text.trim()) return;
    if (!permittedDraftTargets.some(targetValue => targetValue.id === targetId)) return;
    onDraftInsert(targetId, text);
    setStatus(`Inserted text into the ${targetId} draft. No domain record was changed.`);
  }

  function submit(event: FormEvent) {
    if (mode === "automatic") submitAutomatic(event);
    else if (!preview) void previewTurn(event);
    else void prepareTurn(event);
  }

  async function prepareMutationCandidate() {
    if (!mutationCandidateOperation || candidateRequestPending.current) return;
    candidateRequestPending.current = true;
    setCandidateBusy(true);
    setCandidateError(null);
    const key = [
      "personal-ai-mutation-candidate-v1",
      requestScope.applicationId ?? "personal_ai",
      requestScope.workspaceId ?? "",
      conversationId,
      target.id,
      mutationCandidateOperation.operation_id,
      mutationCandidateOperation.version,
    ].join(":");
    let idempotencyKey = crypto.randomUUID();
    try {
      const previousProposalId = window.sessionStorage.getItem(`${key}:proposal`);
      if (previousProposalId) {
        setCandidateProposalId(previousProposalId);
        candidateRequestPending.current = false;
        setCandidateBusy(false);
        return;
      }
      idempotencyKey = window.sessionStorage.getItem(`${key}:idempotency`) ?? idempotencyKey;
      window.sessionStorage.setItem(`${key}:idempotency`, idempotencyKey);
    } catch {
      // The server still resolves and checks the canonical output handle.
    }
    try {
      const result = await createMutationCandidate({
        idempotency_key: idempotencyKey,
        output: { conversation_id: conversationId, message_id: target.id },
        operation: mutationCandidateOperation,
      }, requestScope);
      const id = result.proposal.proposal_id;
      setCandidateProposalId(id);
      try { window.sessionStorage.setItem(`${key}:proposal`, id); } catch { /* optional recovery hint */ }
    } catch (failure) {
      setCandidateError(errorMessage(failure));
    } finally {
      candidateRequestPending.current = false;
      setCandidateBusy(false);
    }
  }

  const activeMutationProposalId = mutationProposalId ?? candidateProposalId;
  const canPrepareMutationCandidate = !!mutationCandidateOperation
    && target.role === "assistant"
    && target.status === "completed"
    && target.application_id === (requestScope.applicationId ?? "personal_ai")
    && target.workspace_id === (requestScope.workspaceId ?? null)
    && !activeMutationProposalId;

  return <aside ref={sidecar} className={styles.sidecar} role="dialog" aria-modal="true" aria-labelledby="continuation-heading">
    <div className={styles.header}>
      <div>
        <p className={styles.eyebrow}>Continue a completed turn</p>
        <h2 ref={heading} id="continuation-heading" tabIndex={-1}>Choose an execution mode</h2>
      </div>
      <button type="button" onClick={onClose} aria-label="Close continuation sidecar" disabled={busy}>Close</button>
    </div>
    <p className={styles.status} role="status">{status}</p>
    {error && <p className={styles.error} role="alert">{error}</p>}

    <label htmlFor="execution-mode">Execution mode</label>
    <select id="execution-mode" value={mode} disabled={busy || !!prepared} onChange={event => { setMode(event.target.value as typeof mode); setPreview(null); setPreviewReviewed(false); }}>
      <option value="automatic">Personal AI · automatic</option>
      {manualAvailable && <option value="manual_external">Manual external model · copy/import</option>}
      {connectedAvailable && <option value="connected_provider">Connected provider · local bridge</option>}
    </select>

    {mode === "connected_provider" && <section className={styles.bridge} aria-labelledby="bridge-heading">
      <h3 id="bridge-heading">{selectedTransport?.displayName ?? "Local connected runtime"}</h3>
      <p>Credentials remain in the local runtime. Pairing authorizes this browser origin and one connection revision; the short-lived caller capability is held only in page memory.</p>
      {bridgeConnection ? <>
        <p><strong>{bridgeConnection.account_label}</strong> · {bridgeConnection.usage?.state ?? "usage unknown"} · plan-use permission {bridgeConnection.plan_permission ? "granted" : "not granted"}</p>
        <div className={styles.recovery}>
          {bridgeConnection.recovery.manage_usage === "provider_account_ui" && selectedTransport?.accountManagementUrl && <a href={selectedTransport.accountManagementUrl} target="_blank" rel="noopener noreferrer">{selectedTransport.accountManagementLabel ?? `Manage usage for ${selectedTransport.displayName}`}</a>}
          {bridgeConnection.recovery.reconnect === "local_operator" && <details>
            <summary>Reconnect this local account</summary>
            <p>In the terminal running the local bridge, run <code>reauth {bridgeConnection.connection_id}</code>. Then pair the updated connection for this browser origin.</p>
            {!bridgeConnection.plan_permission && <p>To grant plan-use permission, run <code>enable-usage {bridgeConnection.connection_id}</code> and complete the provider consent step.</p>}
            <button type="button" disabled={busy || !!prepared} onClick={prepareBridgeRepair}>Pair again after local recovery</button>
          </details>}
        </div>
        <label htmlFor="connected-model">Account-visible model</label>
        <select id="connected-model" value={selectedModel} disabled={busy || !!prepared || !bridgeConnection.plan_permission} onChange={event => setSelectedModel(event.target.value)}>
          {bridgeModels.map(model => <option key={model.slug} value={model.slug}>{model.display_name} ({model.slug})</option>)}
        </select>
        <label htmlFor="connected-profile">Registered execution profile</label>
        <select id="connected-profile" value={selectedProfile} disabled={busy || !!prepared} onChange={event => setSelectedProfile(event.target.value)}>
          {profiles.map(profile => <option key={profile.endpoint.endpoint_profile_id} value={profile.endpoint.endpoint_profile_id}>{profile.endpoint.endpoint_profile_id} v{profile.endpoint.profile_version} · max {profile.maximum_sensitivity}</option>)}
        </select>
        <button type="button" disabled={busy || !pairing} onClick={() => void refreshBridge()}>Refresh account and models</button>
        <p className={styles.note}>Account/model visibility is local bridge observation. The runtime independently checks compatibility, plan-only gates and context sensitivity before sending.</p>
      </> : <form onSubmit={connectBridge} className={styles.form}>
        <p>Start the loopback bridge with this exact origin allowlisted, then run <code>pair {typeof window === "undefined" ? "YOUR_EXACT_ORIGIN" : window.location.origin} CONNECTION_UUID</code> in its local terminal. Paste the returned pairing JSON here.</p>
        <label htmlFor="bridge-pairing">Temporary pairing response</label>
        <textarea id="bridge-pairing" value={pairingText} onChange={event => setPairingText(event.target.value)} autoComplete="off" spellCheck={false} disabled={busy} />
        <button type="submit" disabled={busy || !pairingText.trim()}>Verify local connection</button>
      </form>}
    </section>}

    <form className={styles.form} onSubmit={submit}>
      <label htmlFor="continuation-instruction">What should happen next?</label>
      <textarea id="continuation-instruction" value={instruction} onChange={event => { setInstruction(event.target.value); setPreview(null); setPreviewReviewed(false); }} maxLength={20000} disabled={busy || !!prepared} />
      <label className={styles.checkboxLabel} htmlFor="include-selected-answer">
        <input id="include-selected-answer" type="checkbox" checked={includeTargetEffective} disabled={busy || !!prepared || manualTargetDenied} onChange={event => { setIncludeTarget(event.target.checked); setPreview(null); setPreviewReviewed(false); }} />
        Include this completed turn as a context candidate
      </label>
      {manualTargetDenied && <p className={styles.note} role="status">This imported turn is excluded by the application’s manual reuse policy.</p>}
      {federationChoices.length > 0 && <fieldset className={styles.form} disabled={busy || !!prepared || !!recovery}>
        <legend>Shared context from other apps</legend>
        <p className={styles.note}>Personal AI rechecks each selected grant and source permission when it builds the context.</p>
        {federationChoices.map(option => <label className={styles.checkboxLabel} key={option.id}>
          <input
            type="checkbox"
            checked={selectedFederationChoiceIds.includes(option.id)}
            disabled={!selectedFederationChoiceIds.includes(option.id) && selectedFederationChoiceIds.length >= 4}
            onChange={event => {
              setSelectedFederationChoiceIds(current => event.target.checked
                ? [...current, option.id]
                : current.filter(id => id !== option.id));
              setPreview(null);
              setPreviewReviewed(false);
            }}
          />
          Include {option.categoryLabel}
        </label>)}
        {selectedFederationChoices.length > 0 && <p className={styles.note} role="status">
          Included shared context: {selectedFederationChoices.map(option => option.categoryLabel).join(", ")}
        </p>}
      </fieldset>}
      {mode !== "automatic" && <fieldset className={styles.form} disabled={busy || !!prepared}>
        <legend>Narrow sources for this external turn</legend>
        <p className={styles.note}>These controls only omit sources from the shared authorized planner. They cannot force a source into the package.</p>
        {NARROWABLE_SOURCES.map(source => <label className={styles.checkboxLabel} key={source.id}>
          <input type="checkbox" checked={policyExcludedSources.includes(source.id) || excludedSources.includes(source.id)} disabled={policyExcludedSources.includes(source.id)} onChange={event => {
            setExcludedSources(current => event.target.checked
              ? [...current, source.id]
              : current.filter(item => item !== source.id));
            setPreview(null);
            setPreviewReviewed(false);
          }} />
          Omit {source.label}{policyExcludedSources.includes(source.id) ? " · blocked by application policy" : ""}
        </label>)}
      </fieldset>}
      {!prepared && !recovery && <button type="submit" disabled={busy || !instruction.trim() || (mode === "connected_provider" && (!pairing || !selectedModel || !selectedProfile || bridgeConnection?.usage?.state === "limit")) || (mode !== "automatic" && !!preview && !previewReviewed)}>
        {mode === "automatic" ? "Continue with Personal AI" : preview ? "Prepare and review exact package" : "Preview bounded context"}
      </button>}
    </form>

    {preview && !prepared && <section className={styles.context} aria-labelledby="context-preview-heading">
      <h3 id="context-preview-heading">Bounded context preview</h3>
      <p>Planner-only estimate; no reservation or source retrieval was performed. Canonical preparation will reauthorize and rebuild it.</p>
      <p>{preview.selected_message_count} direct conversation messages selected.</p>
      <ul className={styles.sources}>
        {preview.planned_sources.map((item, index) => <li key={`${item.category}-${item.operation}-${index}`}>
          {item.category}: {item.operation} · up to {item.max_results} results · {item.fields.join(", ") || "registered fields"}
        </li>)}
        {preview.excluded_sources.map((item, index) => <li key={`excluded-${item.category}-${item.reason}-${index}`}>
          {item.category}: omitted ({item.reason})
        </li>)}
      </ul>
      <label className={styles.checkboxLabel}>
        <input type="checkbox" checked={previewReviewed} onChange={event => setPreviewReviewed(event.target.checked)} />
        I reviewed this bounded preview
      </label>
      <button type="button" disabled={busy} onClick={() => { setPreview(null); setPreviewReviewed(false); }}>Change preview selection</button>
    </section>}

    {recovery && recoveryKey && <RecoveryPanel result={recovery} onAbandon={() => void abandonRecoveredPreparation()} busy={busy} />}

    {prepared && <>
      <ContextPackageSummary packageValue={prepared.context_package} />
      <label className={styles.checkboxLabel}>
        <input type="checkbox" checked={finalPackageReviewed} disabled={busy} onChange={event => setFinalPackageReviewed(event.target.checked)} />
        I reviewed the exact prepared messages and source summary
      </label>
      {mode === "manual_external" && <ManualExternalPanel
        portablePrompt={prepared.portable_prompt ?? ""}
        finalPackageReviewed={finalPackageReviewed}
        copyAllowed={!!actionOptions?.copy_allowed}
        copied={copied}
        onCopy={() => void copyText(prepared.portable_prompt ?? "")}
        importText={importText}
        onImportTextChange={setImportText}
        providerLabel={providerLabel}
        onProviderLabelChange={setProviderLabel}
        modelLabel={modelLabel}
        onModelLabelChange={setModelLabel}
        busy={busy}
        onImport={importManual}
        draftTargets={permittedDraftTargets}
        onInsertDraft={onDraftInsert ? insertIntoDraft : undefined}
      />}
      {mode === "connected_provider" && <ConnectedProviderPanel
        savedCompletion={savedCompletion}
        busy={busy}
        pairing={pairing}
        finalPackageReviewed={finalPackageReviewed}
        bridgeConnection={bridgeConnection}
        draftTargets={permittedDraftTargets}
        onInsertDraft={onDraftInsert ? insertIntoDraft : undefined}
        onRetrySave={() => {
          if (savedCompletion) void saveConnectedOutput(prepared, savedCompletion);
        }}
        onSend={() => void sendConnected()}
        canCancelExecution={busy && !!bridgeRequest.current}
        onCancelExecution={() => bridgeRequest.current?.abort()}
      />}
      <div className={styles.actions}>
        <button type="button" disabled={busy} onClick={() => void discardPrepared()}>Discard prepared turn</button>
        <button type="button" disabled={busy} onClick={() => void discardPrepared()}>Discard and prepare again</button>
      </div>
    </>}
    {canPrepareMutationCandidate && <section aria-label="Prepare typed domain proposal">
      <h3>Typed domain change</h3>
      <p>Use the registered domain operation to prepare a reviewable change from this completed response.</p>
      {candidateError && <p role="alert">{candidateError}</p>}
      <button type="button" disabled={candidateBusy} onClick={() => void prepareMutationCandidate()}>
        {candidateBusy ? "Preparing proposal…" : "Prepare typed proposal"}
      </button>
    </section>}
    {activeMutationProposalId && <MutationProposalPanel key={activeMutationProposalId} proposalId={activeMutationProposalId} scope={requestScope} />}
  </aside>;
}
