/** Shared request scope and HTTP error contracts. */
export type ApplicationScopeRequest = {
  /** App IDs are extensible; the backend registry remains the authority. */
  applicationId?: string;
  workspaceId?: string | null;
  requestId?: string;
  capabilities?: string[];
  clientContext?: Record<string, string | number | boolean | null>;
};

export function applicationScopeHeaders(scope: ApplicationScopeRequest = {}): Record<string, string> {
  const headers: Record<string, string> = {
    "X-Application-ID": scope.applicationId ?? "personal_ai",
    "X-Request-ID": scope.requestId ?? crypto.randomUUID(),
  };
  if (scope.workspaceId) headers["X-Workspace-ID"] = scope.workspaceId;
  if (scope.capabilities?.length) headers["X-Client-Capabilities"] = scope.capabilities.join(",");
  if (scope.clientContext && Object.keys(scope.clientContext).length) {
    headers["X-Client-Context"] = JSON.stringify(scope.clientContext);
  }
  return headers;
}

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}
