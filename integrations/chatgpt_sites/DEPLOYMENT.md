# Deployment and operations

## Develop and review in PAS

1. Obtain approval before editing the PAS repository. Start from the current remote `main` in a clean checkout. Copy this source into `integrations/chatgpt_sites/` on a dedicated integration branch. Review the owning repository instructions and leave existing working trees and private inference routes intact.
2. Run `CI=true pnpm install --frozen-lockfile --ignore-scripts`, `pnpm test`, `pnpm build`, and the status preview. Review the test assertions, both tool schemas, the built Worker, and `git diff --check`. Have a separate reviewer check data origin, error output, tool annotations, permissions, the lockfile, and the built source diff.
3. Review the staged file inventory and scan for private records, credentials, logs, environment values, and deployment metadata. Record a reviewed PAS commit only when it exists. GitHub pushes require their own approval and do not by themselves deploy the Site.

## Transfer reviewed source into Sites

1. Use the current Sites-enabled Codex session and the existing owner-private Site. Read its actual access policy. Open its separate Sites-managed source checkout with the supported credential and source workflow from the Sites skill. Pass scoped credentials in memory through the helper's hidden stdin. Use a fresh scratch directory if the Sites source repository already has commits.
2. Reconcile the reviewed integration files with the currently hosted project's source. Apply the reviewed tree in that checkout or make the approved edits through the Site's edit flow and export again. Compare the portable files byte-for-byte. A separate PAS GitHub commit and Sites-managed commit can have different IDs while the portable files match.
3. The Sites-managed repository needs a tracked `.openai/hosting.json` with the platform-issued project ID and the `mcp` capability. Bind that manifest only in the Sites checkout. A GitHub change adds the template only. Do not copy credentials, account identifiers, or the bound manifest into PAS. Stage the bound manifest only in the Sites-managed checkout because the portable ignore rules exclude it.
4. Run the locked tests and build from the prepared source, then use the Sites source helper to commit, push to the Sites-managed branch, and package the build from the matching tree. Obtain approval before the source push. Save that commit and its matching archive as an unpublished Site version. Review the returned preview when available and retain the bundle digest in private evidence. A Site source push is distinct from a push to PAS GitHub.
5. Obtain owner approval for the private deployment and for plugin installation or any account-linking interaction. Some builds can automatically connect the owner's plugin during publish. Recheck owner-only access, deploy the exact saved version through Sites, verify deployment success and inspect the MCP connection details. Check that the published access settings are still owner-only.
6. Export all available source through Sites-enabled Codex. Where a Sites-managed source checkout is provided, export the exact committed tree from that checkout. Exclude the bound manifest and platform-generated bindings from the portable copy, and report any platform-generated or service-side artifacts unavailable for export. Compare portable file checksums and record the Sites-managed commit, saved Site version, deploy state, export digest, bundle digest and PAS review SHA. Record runtime configuration revision separately. A manual PAS GitHub-to-Sites transfer is the supported target process. Personal automatic GitHub sync, direct personal GitHub import, and GitHub-triggered deployment remain unverified in this handoff.

## Plugin test on web and iPhone

Use the generated install card after approved private publication. If the card is absent, use **Plugins → Personal → Created by you → PAS Personal Context** and select **Install** or **Connect** if offered. Check that its tool list contains only `search` and `fetch`, both read-only. Run in fresh ordinary web Chat and then Work on the same account. Mention the plugin and prompt it to run `search("harbor")`, then `fetch` with the returned selector. Ask for the activity on day 2. Expect **Park walk, 14:00**. Expand or otherwise verify the tool calls. An answer alone is insufficient evidence.

Ask for an itinerary suggestion and verify that there is no write tool. Run a Health query and inspect the empty result. Use a fresh selector for the positive check. Capture the client and tool trace without recording tokens or unrelated conversation. If a fetch fails after a valid in-window search, record the failure and hosting routing as a compatibility investigation. Avoid masking it with retries.

On iPhone, update ChatGPT, use the same personal account, fully close the desktop app, and start a fresh iPhone chat. Look for the plugin in the attachment or mention menu or **Plugins → Personal**, then send the web test prompt. Capture the app version and both tool calls if available. If the plugin or tool trace is missing, record exactly which control is unavailable and the result visible on the device.

## Roll back and disconnect

For the synthetic release, remove the plugin from the personal Plugins list and unpublish or disable the Site if required. For a later verified PAS connection, first revoke its PAS source and recipient grants and enrollment as appropriate. Verify subsequent reads fail. Disconnect the account and rotate any affected credentials through their owner. Prior tool output already in a chat remains governed by ChatGPT conversation retention.

Restore only an earlier reviewed and privately deployable Sites code version after approval. Check the current access policy and runtime configuration before and after rollback. Verify plugin discovery and the prior release's synthetic tests again. If a known safe version is unavailable, leave the Site disabled until source and configuration can be reconciled. Sites code rollback does not restore uploaded files or databases. This component uses neither.

[ChatGPT Sites documentation](https://help.openai.com/en/articles/20001339-creating-and-using-chatgpt-sites) · [Site-hosted plugins](https://help.openai.com/en/articles/20001547-hosting-a-plugin-with-chatgpt-sites)
