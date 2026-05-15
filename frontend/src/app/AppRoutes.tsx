import { ProviderConfigPage } from "@/features/provider-config/ProviderConfigPage";
import { WorkbenchPage } from "@/features/workbench/WorkbenchPage";
import { BookWorkspacePage } from "@/features/books/BookWorkspacePage";
import { TrustedStatePage } from "@/features/canon/TrustedStatePage";
import { ChapterPage } from "@/features/chapters/ChapterPage";
import { BlueprintPage } from "@/features/open-book/BlueprintPage";
import { OpenBookPage } from "@/features/open-book/OpenBookPage";

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
      element: <OpenBookPage />,
    };
  }

  const blueprintId = parseBlueprintPath(path);
  if (blueprintId !== null) {
    return {
      activePath: "/books/new",
      element: <BlueprintPage blueprintId={blueprintId} />,
    };
  }

  const trustedStateBookId = parseBookStatePath(path);
  if (trustedStateBookId !== null) {
    return {
      activePath: "/books/:id/state",
      element: <TrustedStatePage bookId={trustedStateBookId} />,
    };
  }

  const chapterId = parseChapterPath(path);
  if (chapterId !== null) {
    return {
      activePath: "/chapters/:id",
      element: <ChapterPage chapterId={chapterId} />,
    };
  }

  const bookId = parseBookProjectPath(path);
  if (bookId !== null) {
    return {
      activePath: "/books/:id",
      element: <BookWorkspacePage bookId={bookId} />,
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

function parseBookProjectPath(path: string): number | null {
  const match = path.match(/^\/books\/(\d+)$/);
  return match ? Number(match[1]) : null;
}

function parseBookStatePath(path: string): number | null {
  const match = path.match(/^\/books\/(\d+)\/state$/);
  return match ? Number(match[1]) : null;
}

function parseChapterPath(path: string): number | null {
  const match = path.match(/^\/chapters\/(\d+)$/);
  return match ? Number(match[1]) : null;
}

function parseBlueprintPath(path: string): number | null {
  const match = path.match(/^\/blueprints\/(\d+)$/);
  return match ? Number(match[1]) : null;
}
