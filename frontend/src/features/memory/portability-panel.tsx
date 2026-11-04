"use client";

import { useState } from "react";

import { authenticatedFetch, getAuthIdentityKey } from "../../lib/auth";

const fieldNames = ["preferred_units", "locale", "response_style", "answer_length"] as const;
type Field = typeof fieldNames[number];
type Profile = { revision: number; fields: { field: Field; value: string }[] };
type Preview = { items: { field: Field; reason: keyof typeof reasons }[]; commit_available: false };
type Capabilities = {
  profile_correction: boolean; profile_export: boolean; import_preview: boolean; download_warning: string;
};

const labels = {
  preferred_units: "Preferred units", locale: "Locale", response_style: "Response style", answer_length: "Answer length",
};
const choices = {
  preferred_units: ["metric", "imperial"],
  response_style: ["concise", "balanced", "detailed"],
  answer_length: ["short", "standard", "expanded"],
};
const reasons = {
  already_current: "Already current",
  revision_conflict: "Profile revision differs",
  foreign_scope: "Archive owner differs",
  source_authority_unproven: "Source authority could not be established",
};

export function PortabilityPanel({ actor }: { actor: string | null }) {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [field, setField] = useState<Field>("preferred_units");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);

  async function request(path: string, body?: string | File) {
    const response = await authenticatedFetch(`/api/memory/control/portability/${path}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
      ...(body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body }),
    });
    if (response.ok) return response;
    const messages: Record<number, string> = {
      401: "Sign in again to use these owner controls.",
      403: "This session cannot use the owner controls.",
      404: "Profile portability is unavailable for this session.",
      409: "The profile changed. Reload it before editing again.",
      413: "Choose a JSON file no larger than 8 KiB.",
      415: "Choose a portable JSON file.",
      422: "The value or portable file is invalid.",
    };
    throw new Error(messages[response.status] ?? "Profile portability is temporarily unavailable.");
  }

  function currentActor() {
    return actor !== null && getAuthIdentityKey() === actor;
  }

  async function run(action: () => Promise<void>, correction = false) {
    if (busy || !currentActor()) return;
    setBusy(true);
    setMessage("");
    try { await action(); }
    catch (error) {
      if (correction) setProfile(null);
      setMessage(`${(error as Error).message}${correction ? " Reload the profile to check the current value." : ""}`);
    }
    finally { setBusy(false); }
  }

  function showProfile(next: Profile) {
    setProfile(next);
    setValue(next.fields.find(item => item.field === field)?.value ?? "");
  }

  async function load() {
    setProfile(null);
    setCapabilities(null);
    setPreview(null);
    const available = await (await request("capabilities")).json() as Capabilities;
    if (!currentActor()) return;
    setCapabilities(available);
    if (available.profile_correction) showProfile(await (await request("profile")).json() as Profile);
  }

  async function correct() {
    if (!profile) return;
    const update = value
      ? { fields: [{ field, value }] }
      : { remove_fields: [field] };
    const next = await (await request("profile", JSON.stringify({
      expected_revision: profile.revision, ...update,
    }))).json() as Profile;
    showProfile(next);
    setPreview(null);
    setMessage("Profile updated. Sharing this profile revision requires fresh grants.");
  }

  async function download() {
    const data = await (await request("export")).blob();
    if (!currentActor()) return;
    const url = URL.createObjectURL(data);
    const link = document.createElement("a");
    link.href = url;
    link.download = "personal-ai-profile.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function assess(file: File) {
    setPreview(null);
    if (file.size > 8192) throw new Error("Choose a JSON file no larger than 8 KiB.");
    setPreview(await (await request("import-preview", file)).json() as Preview);
  }

  return <section aria-label="Profile and portability">
    <h2>Profile and portability</h2>
    <button disabled={busy || !actor} onClick={() => void run(load)}>Load profile controls</button>
    {!actor && <p>Sign in to manage your profile.</p>}
    <p role="status">{message}</p>
    {profile && <form onSubmit={event => { event.preventDefault(); void run(correct, true); }}>
      <fieldset disabled={busy}>
        <legend>Explicit preferences · revision {profile.revision}</legend>
        <label>Preference <select value={field} onChange={event => {
          const selected = event.target.value as Field;
          setField(selected);
          setValue(profile.fields.find(item => item.field === selected)?.value ?? "");
        }}>
          {fieldNames.map(name => <option key={name} value={name}>{labels[name]}</option>)}
        </select></label>
        <label>Value {field === "locale"
          ? <input maxLength={100} placeholder="en-US" value={value} onChange={event => setValue(event.target.value)} />
          : <select value={value} onChange={event => setValue(event.target.value)}>
            <option value="">Unset</option>
            {choices[field].map(option => <option key={option}>{option}</option>)}
          </select>}
        </label>
        <p>Saving a preference invalidates existing profile grants. An empty value removes the preference.</p>
        <button type="submit" disabled={value === (profile.fields.find(item => item.field === field)?.value ?? "")}>
          Save preference
        </button>
      </fieldset>
    </form>}
    {capabilities?.profile_export && <>
      <p>Export includes your explicit profile preferences. {capabilities.download_warning}</p>
      <button disabled={busy} onClick={() => void run(download)}>Download profile JSON</button>
    </>}
    {capabilities?.import_preview && <>
      <p>Preview checks a portable file without changing your data. Applied import is unavailable.</p>
      <label>Preview a portable file <input type="file" accept=".json,application/json" disabled={busy} onChange={event => {
        const file = event.target.files?.[0];
        event.target.value = "";
        if (file) void run(() => assess(file));
      }} /></label>
    </>}
    {preview && (preview.items.length
      ? <ul>{preview.items.map(item => <li key={item.field}>{labels[item.field]} · {reasons[item.reason]}</li>)}</ul>
      : <p>The file contains no preferences.</p>)}
  </section>;
}
