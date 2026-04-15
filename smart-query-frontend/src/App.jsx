import React, { useEffect, useState, useRef } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Spin } from 'antd';
import SmartQueryPage from './pages/SmartQueryPage';
import LoginPage from './pages/LoginPage';
import AdminPage from './pages/AdminPage';
import { getAuthToken, authService } from './services/api';

let _cachedUser = null;
let _cacheExpiry = 0;

async function getCachedUser() {
  const now = Date.now();
  if (_cachedUser && now < _cacheExpiry) return _cachedUser;
  try {
    const result = await authService.getMe();
    _cachedUser = result;
    _cacheExpiry = now + 5 * 60 * 1000;
    return _cachedUser;
  } catch {
    _cachedUser = null;
    _cacheExpiry = 0;
    return null;
  }
}

export function clearAuthCache() {
  _cachedUser = null;
  _cacheExpiry = 0;
}

const AuthGuard = ({ children }) => {
  const location = useLocation();
  const [checking, setChecking] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      const token = getAuthToken();
      if (!token) {
        setAuthenticated(false);
        setChecking(false);
        return;
      }

      const user = await getCachedUser();
      setAuthenticated(!!user);
      setChecking(false);
    };

    checkAuth();
    
    const handleStorageChange = () => {
      const token = getAuthToken();
      if (!token) {
        setAuthenticated(false);
        setChecking(false);
        clearAuthCache();
      }
    };
    
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [location]);

  if (checking) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <Spin size="large" fullscreen tip="验证中..." />
      </div>
    );
  }

  if (!authenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
};

const AdminGuard = ({ children }) => {
  const [checking, setChecking] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    const checkAdmin = async () => {
      const user = await getCachedUser();
      setIsAdmin(user?.data?.is_admin || false);
      setChecking(false);
    };
    checkAdmin();
  }, []);

  if (checking) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="large" tip="验证权限..." />
      </div>
    );
  }

  if (!isAdmin) {
    return <Navigate to="/" replace />;
  }

  return children;
};

const App = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <AuthGuard>
            <SmartQueryPage />
          </AuthGuard>
        }
      />
      <Route
        path="/admin"
        element={
          <AuthGuard>
            <AdminGuard>
              <AdminPage />
            </AdminGuard>
          </AuthGuard>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;
