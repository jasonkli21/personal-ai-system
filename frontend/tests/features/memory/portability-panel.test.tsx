import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { PortabilityPanel } from "../../../src/features/memory/portability-panel";
import { authenticatedFetch } from "../../../src/lib/auth";

vi.mock("../../../src/lib/auth", () => ({
  authenticatedFetch: vi.fn(),
  getAuthIdentityKey: () => "owner",
}));
const fetcher = vi.mocked(authenticatedFetch);
afterEach(() => { cleanup(); fetcher.mockReset(); });

function reply(payload: unknown, status = 200) {
  fetcher.mockResolvedValueOnce({
    ok: status === 200, status, json: async () => payload,
  } as Response);
}

it("negotiates capabilities, submits the loaded revision and requires a reload after conflict", async () => {
  render(<PortabilityPanel actor="owner" />);
  reply({ profile_correction: true, profile_export: true, import_preview: true,
    download_warning: "Downloaded copies cannot be recalled." });
  reply({ revision: 7, fields: [{ field: "preferred_units", value: "metric" }] });
  fireEvent.click(screen.getByRole("button", { name: "Load profile controls" }));
  expect(await screen.findByLabelText("Value")).toHaveValue("metric");
  expect(screen.getByText(/Downloaded copies cannot be recalled/)).toBeVisible();
  expect(screen.getByText(/Applied import is unavailable/)).toBeVisible();
  fireEvent.change(screen.getByLabelText("Value"), { target: { value: "imperial" } });
  reply({}, 409);
  fireEvent.click(screen.getByRole("button", { name: "Save preference" }));
  expect(await screen.findByText(/The profile changed/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Save preference" })).toBeNull();
  expect(JSON.parse(fetcher.mock.calls[2][1]?.body as string)).toEqual({
    expected_revision: 7, fields: [{ field: "preferred_units", value: "imperial" }],
  });
});
