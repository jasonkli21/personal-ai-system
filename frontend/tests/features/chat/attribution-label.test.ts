import { describe, expect, it } from "vitest";

import { attributionLabel } from "../../../src/features/chat/attribution-label";
import type { TurnAttribution } from "../../../src/lib/api";

function attribution(overrides: Partial<TurnAttribution>): TurnAttribution {
  return {
    mode: "connected_provider",
    fact_source: "server_observed",
    execution_origin: "automatic_managed",
    provider_id: "gemini",
    model_id: "gemini-fixture",
    recorded_at: "2026-10-11T00:00:00Z",
    model_verified: false,
    ...overrides,
  };
}

describe("attribution labels", () => {
  it("labels automatic managed turns as server observed", () => {
    expect(attributionLabel(attribution({}))).toBe("Personal AI automatic · server-observed · gemini / gemini-fixture");
  });

  it("labels local connected turns as client reported", () => {
    expect(attributionLabel(attribution({
      fact_source: "client_reported",
      execution_origin: "connected_local",
      provider_id: "openai_chatgpt_plan",
      model_id: "gpt-fixture",
    }))).toContain("Connected local provider · openai_chatgpt_plan / gpt-fixture · client-reported");
  });

  it("labels manual imports as user declared and unverified", () => {
    expect(attributionLabel(attribution({
      mode: "manual_external",
      fact_source: "user_declared",
      execution_origin: "manual_import",
      provider_id: null,
      model_id: null,
    }))).toContain("Manual external · provider/model undeclared · user-declared, unverified");
  });
});
