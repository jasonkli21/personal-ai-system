import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { PortabilityPanel } from "../../../src/features/memory/portability-panel";
import { authenticatedFetch } from "../../../src/lib/auth";

const identity = vi.hoisted(() => ({ key: "owner" }));
vi.mock("../../../src/lib/auth", () => ({
  authenticatedFetch: vi.fn(),
  getAuthIdentityKey: () => identity.key,
}));
const fetcher = vi.mocked(authenticatedFetch);
afterEach(() => { cleanup(); fetcher.mockReset(); identity.key = "owner"; vi.useRealTimers(); vi.restoreAllMocks(); });

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

it("uploads the exact selected file to preview and never calls an import writer", async () => {
  render(<PortabilityPanel actor="owner" />);
  reply({ profile_correction: false, profile_export: false, import_preview: true,
    download_warning: "Copies cannot be recalled." });
  fireEvent.click(screen.getByRole("button", { name: "Load profile controls" }));
  await screen.findByText(/Applied import is unavailable/);
  const file = new File(["{\"sample\":true}"], "profile.json", { type: "application/json" });
  reply({ items: [], commit_available: false });
  fireEvent.change(screen.getByLabelText("Preview a portable file"), { target: { files: [file] } });
  expect(await screen.findByText("The file contains no preferences.")).toBeVisible();
  expect(fetcher.mock.calls[1][0]).toBe("/api/memory/control/portability/import-preview");
  expect(fetcher.mock.calls[1][1]).toMatchObject({ method: "POST", body: file });
  expect(fetcher.mock.calls.some(([url]) => String(url).endsWith("/import"))).toBe(false);
});

it("downloads the returned bytes and revokes the Blob URL", async () => {
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const create = vi.fn((blob: Blob) => {
    expect(blob).toBeInstanceOf(Blob);
    return "blob:profile-copy";
  });
  const revoke = vi.fn();
  vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: revoke });
  render(<PortabilityPanel actor="owner" />);
  reply({ profile_correction: false, profile_export: true, import_preview: false,
    download_warning: "Copies cannot be recalled." });
  fireEvent.click(screen.getByRole("button", { name: "Load profile controls" }));
  await screen.findByRole("button", { name: "Download profile JSON" });
  const bytes = new Blob(["{\"format\":\"personal-ai-memory-export/v1\"}"], { type: "application/json" });
  fetcher.mockResolvedValueOnce({ ok: true, status: 200, blob: async () => bytes } as Response);
  fireEvent.click(screen.getByRole("button", { name: "Download profile JSON" }));
  await vi.waitFor(() => expect(click).toHaveBeenCalledOnce());
  expect(create).toHaveBeenCalledWith(bytes);
  const reader = new FileReader();
  const content = new Promise<string>(resolve => { reader.onload = () => resolve(String(reader.result)); });
  reader.readAsText(create.mock.calls[0][0] as Blob);
  expect(await content).toBe("{\"format\":\"personal-ai-memory-export/v1\"}");
  expect(revoke).not.toHaveBeenCalled();
  await new Promise(resolve => setTimeout(resolve, 1100));
  expect(revoke).toHaveBeenCalledWith("blob:profile-copy");
});

it("suppresses a profile response when the authenticated owner changes mid-load", async () => {
  let finish!: (value: Response) => void;
  render(<PortabilityPanel actor="owner" />);
  reply({ profile_correction: true, profile_export: true, import_preview: true,
    download_warning: "Copies cannot be recalled." });
  fetcher.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  fireEvent.click(screen.getByRole("button", { name: "Load profile controls" }));
  await screen.findByText(/Applied import is unavailable/);
  identity.key = "another-owner";
  finish({ ok: true, status: 200, json: async () => ({ revision: 4,
    fields: [{ field: "preferred_units", value: "imperial" }] }) } as Response);
  await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  expect(screen.queryByRole("button", { name: "Save preference" })).toBeNull();
});

it.each([413, 422, 503])("shows a bounded server error for HTTP %i", async status => {
  render(<PortabilityPanel actor="owner" />);
  reply({ profile_correction: false, profile_export: false, import_preview: true,
    download_warning: "Copies cannot be recalled." });
  fireEvent.click(screen.getByRole("button", { name: "Load profile controls" }));
  await screen.findByText(/Applied import is unavailable/);
  const file = new File(["{}"], "profile.json", { type: "application/json" });
  reply({}, status);
  fireEvent.change(screen.getByLabelText("Preview a portable file"), { target: { files: [file] } });
  expect(await screen.findByRole("status")).toHaveTextContent(
    status === 413 ? "Choose a JSON file no larger than 8 KiB."
      : status === 422 ? "The value or portable file is invalid."
      : "Profile portability is temporarily unavailable.",
  );
});
