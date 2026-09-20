import { Outlet } from "react-router-dom";
import { useEffect } from "react";
import { useAuthStore } from "@store/authStore";

export default function App() {
  const fetchUser = useAuthStore((s) => s.fetchUser);
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    if (token) {
      fetchUser();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <Outlet />;
}
