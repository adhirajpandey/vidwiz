
import { Navigate } from 'react-router-dom';

const getToken = () => {
  return localStorage.getItem('token');
};

const ProtectedRoute = ({ children }: { children: JSX.Element }) => {
  const isAuth = getToken();
  return isAuth ? children : <Navigate to="/login" />;
};

export default ProtectedRoute;
