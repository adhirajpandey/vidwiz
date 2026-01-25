import React from 'react';
import { Navigate } from 'react-router-dom';
import { isAuthenticated } from '../lib/authUtils';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const isAuth = isAuthenticated();
  return isAuth ? children : <Navigate to="/login" />;
};

export default ProtectedRoute;
