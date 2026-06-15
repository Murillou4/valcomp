import Constants from 'expo-constants';

const extra = Constants.expoConfig?.extra as
  | {
      apiBaseUrl?: string;
    }
  | undefined;

export const apiBaseUrl =
  process.env.EXPO_PUBLIC_API_BASE_URL ||
  extra?.apiBaseUrl ||
  'http://127.0.0.1:8000';

let currentAccessToken = '';

export function setAccessToken(token: string | null | undefined) {
  currentAccessToken = token ?? '';
}

type RequestOptions = {
  token?: string;
  body?: unknown;
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = options.token ?? currentAccessToken;
  if (!token) {
    throw new Error('Entre na sua conta Valcomp para continuar.');
  }
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: options.method ?? (options.body ? 'POST' : 'GET'),
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  return parseResponse<T>(response);
}

export async function publicApiRequest<T>(
  path: string,
  options: Omit<RequestOptions, 'token'> = {},
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: options.method ?? (options.body ? 'POST' : 'GET'),
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  return parseResponse<T>(response);
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      payload?.error?.message ||
      payload?.detail?.message ||
      payload?.detail ||
      'Servidor Valcomp indisponivel. Tente novamente em alguns instantes.';
    throw new Error(message);
  }
  return payload as T;
}
