/** A local transport adapter implements the bounded bridge v1 contract. */
export type ExternalTransportAdapter = {
  id: string;
  displayName: string;
  bridgeOrigin: string;
  accountManagementUrl?: string;
  accountManagementLabel?: string;
};

export function createExternalTransportRegistry(
  adapters: readonly ExternalTransportAdapter[],
): ReadonlyMap<string, ExternalTransportAdapter> {
  const registry = new Map<string, ExternalTransportAdapter>();
  for (const adapter of adapters) {
    if (!/^[a-z][a-z0-9_.-]{1,63}$/.test(adapter.id) || registry.has(adapter.id)) {
      throw new Error("external_transport_adapter_id_invalid_or_duplicate");
    }
    const origin = new URL(adapter.bridgeOrigin);
    if (origin.protocol !== "http:" || origin.hostname !== "127.0.0.1") {
      throw new Error("external_transport_adapter_origin_must_be_loopback");
    }
    registry.set(adapter.id, Object.freeze({ ...adapter }));
  }
  return registry;
}

export const DEFAULT_EXTERNAL_TRANSPORTS: readonly ExternalTransportAdapter[] = Object.freeze([
  {
    id: "chatgpt_local_v1",
    displayName: "ChatGPT local bridge",
    bridgeOrigin: "http://127.0.0.1:8765",
    accountManagementUrl: "https://chatgpt.com/",
    accountManagementLabel: "Manage plan usage in ChatGPT",
  },
]);

export function supportedExternalProfiles<T extends { external_transport_id: string }>(
  profiles: readonly T[],
  adapters: readonly ExternalTransportAdapter[] = DEFAULT_EXTERNAL_TRANSPORTS,
): T[] {
  const ids = new Set(adapters.map(adapter => adapter.id));
  return profiles.filter(profile => ids.has(profile.external_transport_id));
}
