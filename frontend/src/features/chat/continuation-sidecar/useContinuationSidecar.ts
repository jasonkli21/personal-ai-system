"use client";

import { useState } from "react";

import type {
  BridgeConnection,
  BridgeModel,
  BridgePairing,
  ContextPreview,
  ContextSourceClass,
  ExecutionOptions,
  ExternalTurnReconciliation,
  PreparedExternalTurn,
} from "../../../lib/api/external-turns";

export function useContinuationSidecar() {
  const [options, setOptions] = useState<ExecutionOptions | null>(null);
  const [mode, setMode] = useState<"automatic" | "manual_external" | "connected_provider">("automatic");
  const [instruction, setInstruction] = useState("Continue from this answer.");
  const [includeTarget, setIncludeTarget] = useState(true);
  const [excludedSources, setExcludedSources] = useState<ContextSourceClass[]>([]);
  const [selectedFederationChoiceIds, setSelectedFederationChoiceIds] = useState<string[]>([]);
  const [preview, setPreview] = useState<ContextPreview | null>(null);
  const [previewReviewed, setPreviewReviewed] = useState(false);
  const [finalPackageReviewed, setFinalPackageReviewed] = useState(false);
  const [recovery, setRecovery] = useState<ExternalTurnReconciliation | null>(null);
  const [recoveryKey, setRecoveryKey] = useState<string | null>(null);
  const [prepared, setPrepared] = useState<PreparedExternalTurn | null>(null);
  const [providerLabel, setProviderLabel] = useState("");
  const [modelLabel, setModelLabel] = useState("");
  const [importText, setImportText] = useState("");
  const [pairingText, setPairingText] = useState("");
  const [pairing, setPairing] = useState<BridgePairing | null>(null);
  const [bridgeConnection, setBridgeConnection] = useState<BridgeConnection | null>(null);
  const [bridgeModels, setBridgeModels] = useState<BridgeModel[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedProfile, setSelectedProfile] = useState("");
  const [savedCompletion, setSavedCompletion] = useState<{
    text: string; latencyMs: number; inputTokens?: number; outputTokens?: number;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Loading available execution modes…");
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  return {
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
  };
}
