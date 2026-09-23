import { createBrowserRouter, Navigate } from "react-router-dom";
import MainLayout from "@components/Layout/MainLayout";
import LoginPage from "@pages/Login/LoginPage";
import DashboardPage from "@pages/Dashboard/DashboardPage";
import DocumentListPage from "@pages/Documents/DocumentListPage";
import DocumentDetailPage from "@pages/Documents/DocumentDetailPage";
import AnnotationWorkspace from "@pages/Annotation/AnnotationWorkspace";
import ActiveLearningPage from "@pages/Annotation/ActiveLearningPage";
import GraphExplorer from "@pages/KnowledgeGraph/GraphExplorer";
import GraphRAGPage from "@pages/KnowledgeGraph/GraphRAGPage";
import MultiAgentPage from "@pages/KnowledgeGraph/MultiAgentPage";
import CitationGraphPage from "@pages/KnowledgeGraph/CitationGraphPage";
import PaperRetrievalPage from "@pages/Research/PaperRetrievalPage";
import WritingAssistantPage from "@pages/Research/WritingAssistantPage";
import DeduplicationPage from "@pages/Documents/DeduplicationPage";
import TaskListPage from "@pages/Tasks/TaskListPage";
import ProfilePage from "@pages/Settings/ProfilePage";
import OperationLogsPage from "@pages/Settings/OperationLogsPage";
import RolePermissionPage from "@pages/Settings/RolePermissionPage";
import WorkloadPage from "@pages/Statistics/WorkloadPage";
import NotFoundPage from "@pages/NotFound/NotFoundPage";
import { authGuard, permGuard } from "./guards";

export const router = createBrowserRouter(
  [
    { path: "/login", element: <LoginPage /> },
    {
      path: "/",
      element: <MainLayout />,
      children: [
        { index: true, element: <Navigate to="/home" replace /> },
        { path: "home", element: authGuard(<DashboardPage />) },
        { path: "dashboard", element: authGuard(<DashboardPage />) },
        {
          path: "documents",
          children: [
            { index: true, element: authGuard(<DocumentListPage />) },
            { path: ":id", element: authGuard(<DocumentDetailPage />) },
          ],
        },
        { path: "annotation/:documentId", element: authGuard(<AnnotationWorkspace />) },
        {
          path: "active-learning",
          element: permGuard(<ActiveLearningPage />, "annotation:read"),
        },
        { path: "knowledge-graph", element: authGuard(<GraphExplorer />) },
        { path: "knowledge-graph/rag", element: authGuard(<GraphRAGPage />) },
        { path: "multi-agent", element: authGuard(<MultiAgentPage />) },
        { path: "citation-graph", element: authGuard(<CitationGraphPage />) },
        { path: "paper-retrieval", element: authGuard(<PaperRetrievalPage />) },
        { path: "writing-assistant", element: authGuard(<WritingAssistantPage />) },
        { path: "deduplication", element: authGuard(<DeduplicationPage />) },
        { path: "tasks", element: authGuard(<TaskListPage />) },
        { path: "settings/profile", element: authGuard(<ProfilePage />) },
        {
          path: "settings/roles",
          element: permGuard(<RolePermissionPage />, "system:role:manage"),
        },
        { path: "operation-logs", element: permGuard(<OperationLogsPage />, "system:audit:read") },
        { path: "statistics", element: authGuard(<WorkloadPage />) },
      ],
    },
    { path: "*", element: <NotFoundPage /> },
  ],
  {
    future: {
      v7_fetcherPersist: true,
      v7_normalizeFormMethod: true,
      v7_partialHydration: true,
      v7_relativeSplatPath: true,
      v7_skipActionErrorRevalidation: true,
    },
  },
);
