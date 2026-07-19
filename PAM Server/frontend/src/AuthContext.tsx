import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import * as api from './api';
import type { User } from './types';

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  }, [navigate]);

  const refresh = useCallback(async () => {
    try {
      const data = await api.refreshToken();
      setUser(data.user);
      setToken(data.token);
    } catch {
      logout();
    }
  }, [logout]);

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');

    if (storedToken && storedUser) {
      setToken(storedToken);
      setUser(JSON.parse(storedUser));

      api.getMe().then((u) => {
        setUser(u);
        localStorage.setItem('user', JSON.stringify(u));
      }).catch(() => {
        refresh();
      }).finally(() => {
        setLoading(false);
      });
    } else {
      setLoading(false);
    }
  }, [refresh]);

  useEffect(() => {
    if (loading) return;

    const publicPaths = ['/login'];
    if (!token && !publicPaths.includes(location.pathname)) {
      navigate('/login');
    }
  }, [token, loading, navigate, location.pathname]);

  const login = useCallback(async (username: string, password: string) => {
    const data = await api.login(username, password);
    setUser(data.user);
    setToken(data.token);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
