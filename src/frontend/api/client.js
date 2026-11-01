/**
 * HTTP 通信クライアント基盤 (fetch ラッパー)
 */
let mockHandler = null;

export function setApiMock(handler) {
  mockHandler = handler;
}

export function clearApiMock() {
  mockHandler = null;
}

export async function request(url, options = {}) {
  if (mockHandler) {
    const mockResponse = await mockHandler(url, options);
    if (mockResponse !== undefined) {
      return mockResponse;
    }
  }

  const res = await fetch(url, options);
  if (!res.ok) {
    throw new Error(`HTTP Error: ${res.status}`);
  }
  return await res.json();
}
