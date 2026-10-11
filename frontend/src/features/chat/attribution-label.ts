import type { TurnAttribution } from "../../lib/api";

function producer(attribution: TurnAttribution) {
  return [attribution.provider_id, attribution.model_id].filter(Boolean).join(" / ");
}

/** Present canonical producer origin and its separately recorded observation trust. */
export function attributionLabel(attribution: TurnAttribution): string {
  const identity = producer(attribution);
  if (attribution.execution_origin === "automatic_managed") {
    return `Personal AI automatic · server-observed${identity ? ` · ${identity}` : ""}`;
  }
  if (attribution.execution_origin === "connected_local") {
    return `Connected local provider · ${identity || "provider/model unavailable"} · client-reported`;
  }
  if (attribution.execution_origin === "manual_import" || attribution.fact_source === "user_declared") {
    return `Manual external · ${identity || "provider/model undeclared"} · user-declared, unverified`;
  }
  if (attribution.fact_source === "server_observed") {
    return `Personal AI automatic · server-observed${identity ? ` · ${identity}` : ""}`;
  }
  return `Connected provider · ${identity || "provider/model unavailable"} · client-reported`;
}
