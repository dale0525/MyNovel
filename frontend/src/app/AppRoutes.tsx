import { ProviderConfigPage } from "@/features/provider-config/ProviderConfigPage";
import { WorkbenchPage } from "@/features/workbench/WorkbenchPage";

type RouteMatch = {
  activePath: string;
  element: React.ReactNode;
};

export function routeForPath(pathname: string): RouteMatch {
  const path = normalizePath(pathname);

  if (path === "/settings/provider" || path === "/provider-config") {
    return { activePath: "/settings/provider", element: <ProviderConfigPage /> };
  }

  if (path === "/books/new") {
    return {
      activePath: "/books/new",
      element: (
        <RoutePlaceholder
          eyebrow="Book setup"
          title="开书"
          message="开书页面将在后续任务接入。"
        />
      ),
    };
  }

  if (isBookProjectPath(path)) {
    return {
      activePath: "/books/:id",
      element: (
        <RoutePlaceholder
          eyebrow="Project"
          title="项目"
          message="项目页面将在后续任务接入。"
        />
      ),
    };
  }

  if (path === "/review") {
    return {
      activePath: "/review",
      element: (
        <RoutePlaceholder
          eyebrow="Review"
          title="质量复审"
          message="质量复审页面将在后续任务接入。"
        />
      ),
    };
  }

  return { activePath: "/", element: <WorkbenchPage /> };
}

function RoutePlaceholder({
  eyebrow,
  title,
  message,
}: {
  eyebrow: string;
  title: string;
  message: string;
}) {
  return (
    <section className="workbench-page" aria-labelledby="route-placeholder-title">
      <div className="workbench-hero">
        <p className="eyebrow">{eyebrow}</p>
        <h1 id="route-placeholder-title">{title}</h1>
        <p className="lede">{message}</p>
      </div>
    </section>
  );
}

function normalizePath(pathname: string): string {
  const path = pathname.split(/[?#]/, 1)[0] || "/";
  return path.length > 1 && path.endsWith("/") ? path.slice(0, -1) : path;
}

function isBookProjectPath(path: string): boolean {
  const match = path.match(/^\/books\/([^/]+)$/);
  return Boolean(match && match[1] !== "new");
}
