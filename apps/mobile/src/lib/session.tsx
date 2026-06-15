import * as SecureStore from 'expo-secure-store';
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { Platform } from 'react-native';

import { apiRequest, publicApiRequest, setAccessToken } from '@/lib/api';

const STORAGE_KEY = 'valcomp.auth.session.v1';

export type AuthSession = {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number | null;
  expires_at?: number | null;
};

export type AppUser = {
  id: string;
  email?: string | null;
};

export type AppProfile = {
  user_id: string;
  display_name?: string;
  avatar_url?: string;
  preferences?: Record<string, unknown>;
};

export type AuthResponse = {
  user: AppUser;
  session?: AuthSession | null;
  profile?: AppProfile | null;
  email_confirmation_required?: boolean;
  message?: string;
};

type StoredAuth = {
  user: AppUser;
  session: AuthSession;
  profile?: AppProfile | null;
};

type VerifyResponse = {
  valid: boolean;
  user: AppUser;
  profile?: AppProfile | null;
};

type AuthContextValue = {
  loading: boolean;
  session: AuthSession | null;
  user: AppUser | null;
  profile: AppProfile | null;
  signIn: (email: string, password: string) => Promise<AuthResponse>;
  signUp: (email: string, password: string, displayName: string) => Promise<AuthResponse>;
  signOut: () => Promise<void>;
  refreshSession: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<AuthSession | null>(null);
  const [user, setUser] = useState<AppUser | null>(null);
  const [profile, setProfile] = useState<AppProfile | null>(null);

  const clearSession = useCallback(async () => {
    await removeStoredAuth();
    setAccessToken(null);
    setSession(null);
    setUser(null);
    setProfile(null);
  }, []);

  const applyResponse = useCallback(async (response: AuthResponse) => {
    if (!response.session?.access_token) {
      setUser(response.user);
      setProfile(response.profile ?? null);
      return;
    }
    const stored: StoredAuth = {
      user: response.user,
      session: response.session,
      profile: response.profile ?? null,
    };
    await writeStoredAuth(stored);
    setAccessToken(response.session.access_token);
    setSession(response.session);
    setUser(response.user);
    setProfile(response.profile ?? null);
  }, []);

  const refreshWithToken = useCallback(
    async (refreshToken: string) => {
      const response = await publicApiRequest<AuthResponse>('/auth/refresh', {
        method: 'POST',
        body: { refresh_token: refreshToken },
      });
      if (!response.session?.access_token) {
        throw new Error('Sessao expirada. Entre novamente.');
      }
      await applyResponse(response);
    },
    [applyResponse],
  );

  const refreshSession = useCallback(async () => {
    if (!session?.refresh_token) {
      throw new Error('Sessao expirada. Entre novamente.');
    }
    await refreshWithToken(session.refresh_token);
  }, [refreshWithToken, session]);

  useEffect(() => {
    let active = true;
    async function hydrate() {
      try {
        const stored = await readStoredAuth();
        if (!stored?.session.access_token) {
          return;
        }
        setAccessToken(stored.session.access_token);
        if (active) {
          setSession(stored.session);
          setUser(stored.user);
          setProfile(stored.profile ?? null);
        }
        try {
          const verified = await apiRequest<VerifyResponse>('/auth/session/verify');
          if (active) {
            setUser(verified.user);
            setProfile(verified.profile ?? null);
          }
        } catch {
          if (stored.session.refresh_token) {
            await refreshWithToken(stored.session.refresh_token);
          } else {
            await clearSession();
          }
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    hydrate();
    return () => {
      active = false;
    };
  }, [clearSession, refreshWithToken]);

  const value = useMemo<AuthContextValue>(
    () => ({
      loading,
      session,
      user,
      profile,
      signIn: async (email: string, password: string) => {
        const response = await publicApiRequest<AuthResponse>('/auth/login', {
          method: 'POST',
          body: { email, password },
        });
        await applyResponse(response);
        return response;
      },
      signUp: async (email: string, password: string, displayName: string) => {
        const response = await publicApiRequest<AuthResponse>('/auth/signup', {
          method: 'POST',
          body: { email, password, display_name: displayName },
        });
        await applyResponse(response);
        return response;
      },
      signOut: clearSession,
      refreshSession,
    }),
    [applyResponse, clearSession, loading, profile, refreshSession, session, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider.');
  }
  return context;
}

async function readStoredAuth(): Promise<StoredAuth | null> {
  const raw = await readItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as StoredAuth;
  } catch {
    await removeStoredAuth();
    return null;
  }
}

async function writeStoredAuth(value: StoredAuth) {
  await writeItem(STORAGE_KEY, JSON.stringify(value));
}

async function removeStoredAuth() {
  await deleteItem(STORAGE_KEY);
}

async function readItem(key: string) {
  if (Platform.OS === 'web') {
    return globalThis.localStorage?.getItem(key) ?? null;
  }
  return SecureStore.getItemAsync(key);
}

async function writeItem(key: string, value: string) {
  if (Platform.OS === 'web') {
    globalThis.localStorage?.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function deleteItem(key: string) {
  if (Platform.OS === 'web') {
    globalThis.localStorage?.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}
