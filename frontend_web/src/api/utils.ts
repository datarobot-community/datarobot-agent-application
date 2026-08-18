import { isAxiosError } from 'axios';

type ResponsePayload = { detail?: unknown; message?: string };

function getMessageFromResponsePayload(payload: unknown): string | undefined {
  if (typeof payload === 'string' && payload.trim().length > 0) {
    return payload;
  }

  if (!payload || typeof payload !== 'object') {
    return undefined;
  }

  const data = payload as ResponsePayload;
  if (typeof data.message === 'string' && data.message.trim().length > 0) {
    return data.message;
  }

  const detail = data.detail;
  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail;
  }
  if (detail && typeof detail === 'object') {
    const detailMessage = (detail as { message?: string }).message;
    if (typeof detailMessage === 'string' && detailMessage.trim().length > 0) {
      return detailMessage;
    }
  }

  return undefined;
}

/**
 * Extract a user-friendly error message from Axios / API errors.
 */
export function getApiErrorMessage(error: unknown, fallbackMessage = 'Request failed'): string {
  if (!error) {
    return fallbackMessage;
  }

  if (error instanceof Error && 'payload' in error) {
    const payloadMessage = getMessageFromResponsePayload(
      (error as Error & { payload?: unknown }).payload
    );
    if (payloadMessage) {
      return payloadMessage;
    }
  }

  if (isAxiosError(error)) {
    const responseData = error.response?.data as
      | { detail?: unknown; message?: string }
      | string
      | undefined;

    const responseMessage = getMessageFromResponsePayload(responseData);
    if (responseMessage) {
      return responseMessage;
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  if (typeof error === 'string' && error.trim().length > 0) {
    return error;
  }

  return fallbackMessage;
}
