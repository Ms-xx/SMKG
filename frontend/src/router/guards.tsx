/* eslint-disable react-refresh/only-export-components */
import { Navigate } from "react-router-dom";
import { useAuthStore } from "@store/authStore";

const RequireAuth = ({ children }: { children: React.ReactElement }) => {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
};

const RequireRole = ({
  children,
  allowedRoles,
}: {
  children: React.ReactElement;
  allowedRoles: string[];
}) => {
  const user = useAuthStore((s) => s.user);
  if (!user || !allowedRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
};

const RequirePermission = ({
  children,
  permission,
}: {
  children: React.ReactElement;
  permission: string;
}) => {
  const user = useAuthStore((s) => s.user);
  const permissions = useAuthStore((s) => s.permissions);
  // 等待 fetchUser 异步加载用户与权限，避免加载瞬间误判
  if (!user) {
    return null;
  }
  if (user.role !== "admin" && !permissions.includes("all") && !permissions.includes(permission)) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
};

export const authGuard = (element: React.ReactElement) => {
  return <RequireAuth>{element}</RequireAuth>;
};

export const roleGuard = (element: React.ReactElement, allowedRoles: string[]) => {
  return <RequireRole allowedRoles={allowedRoles}>{element}</RequireRole>;
};

export const permGuard = (element: React.ReactElement, permission: string) => {
  return (
    <RequireAuth>
      <RequirePermission permission={permission}>{element}</RequirePermission>
    </RequireAuth>
  );
};
