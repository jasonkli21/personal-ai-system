import { readSseFrames } from "../../../lib/sse";
import type { ApplicationScopeRequest } from "../../../lib/api/common";
import type {
  BridgePairing,
  PreparedExternalTurn,
  SignedDispatchGrant,
} from "../../../lib/api/external-turns";
import type { ExternalTransportAdapter } from "../external-transport";

export type BridgeTerminal = {
  status?: string;
  usage?: { input_tokens?: number | null; output_tokens?: number | null } | null;
};

export function validatePairing(value: unknown): BridgePairing {
  if (!value || typeof value !== "object") throw new Error("invalid_pairing");
  const pairing = value as Partial<BridgePairing>;
  if (
    typeof pairing.caller_id !== "string" || typeof pairing.audience !== "string" ||
    typeof pairing.connection_id !== "string" || typeof pairing.connection_revision !== "number" ||
    typeof pairing.expires_at !== "number" || typeof pairing.caller_authorization !== "string"
  ) throw new Error("invalid_pairing");
  return pairing as BridgePairing;
}

function bridgeUrl(path: string, adapter: ExternalTransportAdapter) {
  return `${adapter.bridgeOrigin}${path}`;
}

export function recoveryStorageKey(conversationId: string, scope: ApplicationScopeRequest) {
  return `external-prepare:${scope.applicationId ?? "personal_ai"}:${scope.workspaceId ?? ""}:${conversationId}`;
}

export async function bridgeJson<T>(
  path: string,
  pairing: BridgePairing,
  adapter: ExternalTransportAdapter,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(bridgeUrl(path, adapter), {
    method: "GET",
    mode: "cors",
    credentials: "omit",
    cache: "no-store",
    redirect: "error",
    headers: { "X-Bridge-Authorization": pairing.caller_authorization },
    signal,
  });
  if (!response.ok) throw new Error("bridge_unavailable");
  return response.json() as Promise<T>;
}

export async function bridgeExecute(
  packageValue: PreparedExternalTurn["connected_execution"],
  proof: SignedDispatchGrant,
  pairing: BridgePairing,
  adapter: ExternalTransportAdapter,
  signal: AbortSignal,
  onDelta: (text: string) => void,
) {
  if (!packageValue) throw new Error("prepared_package_missing");
  const startedAt = performance.now();
  const response = await fetch(bridgeUrl("/execute", adapter), {
    method: "POST",
    mode: "cors",
    credentials: "omit",
    cache: "no-store",
    redirect: "error",
    headers: {
      "Content-Type": "application/json",
      "X-Bridge-Authorization": pairing.caller_authorization,
    },
    body: JSON.stringify({ package: packageValue, proof }),
    signal,
  });
  if (!response.ok) throw new Error("bridge_execution_failed");
  let output = "";
  let terminal: BridgeTerminal | null = null;
  for await (const frame of readSseFrames(response, { frameCharacters: 65536, totalBytes: 300000 })) {
    if (!frame.data) continue;
    let event: { kind?: string; delta?: string; metadata?: BridgeTerminal; error?: string };
    try {
      event = JSON.parse(frame.data) as typeof event;
    } catch {
      throw new Error("bridge_protocol_invalid");
    }
    if (event.kind === "delta" && typeof event.delta === "string") {
      output += event.delta;
      if (output.length > 20000) throw new Error("bridge_output_too_large");
      onDelta(event.delta);
    } else if (event.kind === "terminal" && event.metadata) {
      terminal = event.metadata;
      break;
    } else if (event.kind === "interrupted") {
      throw new Error("bridge_execution_interrupted");
    } else {
      throw new Error("bridge_protocol_invalid");
    }
  }
  if (!terminal || terminal.status !== "success" || !output.trim()) {
    throw new Error("bridge_execution_incomplete");
  }
  const elapsed = Math.min(Math.max(Math.round(performance.now() - startedAt), 0), 3_600_000);
  return { text: output, terminal, latencyMs: elapsed };
}
