export interface HealthResponse {
  status: "ok";
  service: string;
}

export async function getHealth(signal: AbortSignal): Promise<HealthResponse> {
  const response = await fetch("/api/v1/health", { signal });
  if (!response.ok) {
    throw new Error(`API returned HTTP ${response.status}`);
  }
  const data: unknown = await response.json();
  if (
    typeof data !== "object" ||
    data === null ||
    !("status" in data) ||
    data.status !== "ok" ||
    !("service" in data) ||
    typeof data.service !== "string"
  ) {
    throw new Error("The API returned an unexpected health response.");
  }
  return { status: data.status, service: data.service };
}

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Non-JSON error body (e.g. proxy error page); fall through to the status text.
  }
  return `Request failed with HTTP ${response.status}`;
}

export async function segmentImage(file: File, signal: AbortSignal): Promise<Blob> {
  const form = new FormData();
  form.append("file", file, file.name);
  const response = await fetch("/api/v1/segment", { method: "POST", body: form, signal });
  if (!response.ok) {
    throw new ApiError(await errorDetail(response), response.status);
  }
  const mask = await response.blob();
  if (mask.type !== "image/png") {
    throw new ApiError("The server returned an unexpected response.", response.status);
  }
  return mask;
}

export async function generateModel(file: File, signal: AbortSignal): Promise<ArrayBuffer> {
  const form = new FormData();
  form.append("file", file, file.name);
  const response = await fetch("/api/v1/generate-3d", { method: "POST", body: form, signal });
  if (!response.ok) {
    throw new ApiError(await errorDetail(response), response.status);
  }
  if (response.headers.get("content-type") !== "model/gltf-binary") {
    throw new ApiError("The server returned an unexpected response.", response.status);
  }
  return response.arrayBuffer();
}
