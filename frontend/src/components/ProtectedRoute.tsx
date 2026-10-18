import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/context/AuthContext";
import { FullPageSpinner } from "@/components/Spinner";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, ready } = useAuth();
  const location = useLocation();

  if (!ready) return <FullPageSpinner label="Restoring session…" />;
  if (!token) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <>{children}</>;
}
