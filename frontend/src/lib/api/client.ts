import { authenticatedFetch } from "../auth";
import { readSseFrames, SseError } from "../sse";
import { ApiError, applicationScopeHeaders, type ApplicationScopeRequest } from "./common";
import type { Message, ResponseErrorEvent, StreamHandlers } from "./conversations";

type ErrorPayload = { error?: { message?: string } };
type MessageCreatedEvent = { message: Message };
type ResponseDeltaEvent = { message_id: string; delta: string };
type ResponseCompletedEvent = { message: Message };
type ResponseErrorPayload = ResponseErrorEvent;

export async function request<T>(path: string, init?: RequestInit, scope?: ApplicationScopeRequest): Promise<T> {
  let response: Response;
  try {
    response = await authenticatedFetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...applicationScopeHeaders(scope), ...init?.headers },
    });
  } catch {
    throw new ApiError("Unable to reach the Personal AI service. Please try again.");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ErrorPayload;
    throw new ApiError(body.error?.message ?? "The request could not be completed. Please try again.", response.status);
  }
  return response.json() as Promise<T>;
}

export async function streamRequest(path: string, init: RequestInit, handlers: StreamHandlers, scope?: ApplicationScopeRequest): Promise<void> {
  let response: Response;
  try {
    response = await authenticatedFetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...applicationScopeHeaders(scope), ...init.headers },
    });
  } catch {
    throw new ApiError("Unable to reach the Personal AI service. Please try again.");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ErrorPayload;
    throw new ApiError(body.error?.message ?? "The request could not be completed. Please try again.", response.status);
  }
  if (!response.body) throw new ApiError("The response stream could not be read. Please try again.");

  let terminal = false;
  const consume = (event: string, data: string) => {
    if (!event || !data) return;
    try {
      switch (event) {
        case "message.created": {
          const payload = JSON.parse(data) as MessageCreatedEvent;
          if (!payload.message || typeof payload.message.id !== "string") throw new Error("Invalid message");
          handlers.onMessageCreated(payload.message);
          break;
        }
        case "response.delta": {
          const payload = JSON.parse(data) as ResponseDeltaEvent;
          if (typeof payload.message_id !== "string" || typeof payload.delta !== "string") throw new Error("Invalid delta");
          handlers.onDelta(payload.message_id, payload.delta);
          break;
        }
        case "response.completed": {
          const payload = JSON.parse(data) as ResponseCompletedEvent;
          if (!payload.message || typeof payload.message.id !== "string" || payload.message.role !== "assistant" || payload.message.status !== "completed" || typeof payload.message.content !== "string") throw new Error("Invalid completion");
          handlers.onCompleted(payload.message);
          terminal = true;
          break;
        }
        case "response.error": {
          const payload = JSON.parse(data) as ResponseErrorPayload;
          if (typeof payload.message_id !== "string" || typeof payload.code !== "string" || typeof payload.message !== "string") throw new Error("Invalid error");
          handlers.onError(payload);
          terminal = true;
          break;
        }
      }
    } catch {
      throw new ApiError("The response stream could not be read. Please try again.");
    }
  };

  try {
    for await (const frame of readSseFrames(response, { frameCharacters: 131072, totalBytes: 4 * 1024 * 1024 })) {
      consume(frame.event, frame.data);
      if (terminal) return;
    }
    throw new ApiError("The response was interrupted. Please retry.");
  } catch (error) {
    if (error instanceof SseError && error.kind === "incomplete") {
      throw new ApiError("The response was interrupted. Please retry.");
    }
    throw error instanceof ApiError ? error : new ApiError("The response stream could not be read. Please try again.");
  }
}
