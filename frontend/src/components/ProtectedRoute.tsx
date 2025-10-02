
import React from 'react';
import { Navigate } from 'react-router-dom';

const getToken = () => {
  return localStorage.getItem('token');
};

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const isAuth = getToken();
  return isAuth ? children : <Navigate to="/login" />;
};

export default ProtectedRoute;
