import { describe, it, expect, vi } from "vitest";

vi.mock("@components/Layout/MainLayout", () => ({ default: () => null }));
vi.mock("@pages/Login/LoginPage", () => ({ default: () => null }));
vi.mock("@pages/Dashboard/DashboardPage", () => ({ default: () => null }));
vi.mock("@pages/Documents/DocumentListPage", () => ({ default: () => null }));
vi.mock("@pages/Documents/DocumentDetailPage", () => ({ default: () => null }));
vi.mock("@pages/Annotation/AnnotationWorkspace", () => ({ default: () => null }));
vi.mock("@pages/KnowledgeGraph/GraphExplorer", () => ({ default: () => null }));
vi.mock("@pages/KnowledgeGraph/GraphRAGPage", () => ({ default: () => null }));
vi.mock("@pages/Tasks/TaskListPage", () => ({ default: () => null }));
vi.mock("@pages/Settings/ProfilePage", () => ({ default: () => null }));
vi.mock("@pages/Settings/OperationLogsPage", () => ({ default: () => null }));
vi.mock("@pages/Settings/RolePermissionPage", () => ({ default: () => null }));
vi.mock("@pages/Statistics/WorkloadPage", () => ({ default: () => null }));
vi.mock("@pages/NotFound/NotFoundPage", () => ({ default: () => null }));
vi.mock("./guards", () => ({
  authGuard: (el: any) => el,
  roleGuard: (el: any) => el,
  permGuard: (el: any) => el,
}));

import { router } from "./index";

describe("router 路由配置", () => {
  it("定义登录、根路由与通配 404 路由", () => {
    const flatPaths = (router.routes as any[]).flatMap((r: any) => [
      r.path,
      ...(r.children?.map((c: any) => c.path) || []),
    ]);
    expect(flatPaths).toContain("/login");
    expect(flatPaths).toContain("/");
    expect(flatPaths).toContain("*");
  });
});
