import { ProviderConfigPage } from "@/features/provider-config/ProviderConfigPage";
import { WorkbenchPage } from "@/features/workbench/WorkbenchPage";
import { BookWorkspacePage } from "@/features/books/BookWorkspacePage";
import { ImportBookPage } from "@/features/books/ImportBookPage";
import { ChapterPage } from "@/features/chapters/ChapterPage";
import { BlueprintPage } from "@/features/open-book/BlueprintPage";
import { OpenBookPage } from "@/features/open-book/OpenBookPage";
import { UpdatesPage } from "@/features/updates/UpdatesPage";

type RouteMatch = {
  activePath: string;
  element: React.ReactNode;
};

export function routeForPath(pathname: string): RouteMatch {
  const path = normalizePath(pathname);

  if (path === "/settings/provider" || path === "/provider-config") {
    return {
      activePath: "/settings/provider",
      element: <ProviderConfigPage loadExistingConfig />,
    };
  }

  if (path === "/books/new") {
    return {
      activePath: "/books/new",
      element: <OpenBookPage />,
    };
  }

  if (path === "/books") {
    return {
      activePath: "/books",
      element: <WorkbenchPage />,
    };
  }

  if (path === "/books/import") {
    return {
      activePath: "/books/import",
      element: <ImportBookPage />,
    };
  }

  if (path === "/updates") {
    return {
      activePath: "/updates",
      element: <UpdatesPage />,
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
      element: <BookWorkspacePage bookId={trustedStateBookId} view="state" />,
    };
  }

  const bookSettingsId = parseBookSettingsPath(path);
  if (bookSettingsId !== null) {
    return {
      activePath: "/books/:id/settings",
      element: <BookWorkspacePage bookId={bookSettingsId} view="settings" />,
    };
  }

  const bookVolumesId = parseBookVolumesPath(path);
  if (bookVolumesId !== null) {
    return {
      activePath: "/books/:id/chapters",
      element: <BookWorkspacePage bookId={bookVolumesId} view="chapters" />,
    };
  }

  const bookChaptersId = parseBookChaptersPath(path);
  if (bookChaptersId !== null) {
    return {
      activePath: "/books/:id/chapters",
      element: <BookWorkspacePage bookId={bookChaptersId} view="chapters" />,
    };
  }

  const bookChapterIds = parseBookChapterPath(path);
  if (bookChapterIds !== null) {
    return {
      activePath: "/books/:id/chapters/:chapterId",
      element: (
        <BookWorkspacePage
          bookId={bookChapterIds.bookId}
          chapterId={bookChapterIds.chapterId}
          view="chapters"
        />
      ),
    };
  }

  const chapterId = parseChapterPath(path);
  if (chapterId !== null) {
    return {
      activePath: "/chapters/:id",
      element: <ChapterPage chapterId={chapterId} />,
    };
  }

  const qualityBookId = parseBookQualityPath(path);
  if (qualityBookId !== null) {
    return {
      activePath: "/books/:id/quality",
      element: <BookWorkspacePage bookId={qualityBookId} view="quality" />,
    };
  }

  const bookId = parseBookProjectPath(path);
  if (bookId !== null) {
    return {
      activePath: "/books/:id",
      element: <BookWorkspacePage bookId={bookId} />,
    };
  }

  return { activePath: "/", element: <WorkbenchPage /> };
}

function normalizePath(pathname: string): string {
  const path = pathname.split(/[?#]/, 1)[0] || "/";
  return path.length > 1 && path.endsWith("/") ? path.slice(0, -1) : path;
}

function parseBookProjectPath(path: string): number | null {
  const match = path.match(/^\/books\/(\d+)$/);
  return match ? Number(match[1]) : null;
}

function parseBookSettingsPath(path: string): number | null {
  const match = path.match(/^\/books\/(\d+)\/settings$/);
  return match ? Number(match[1]) : null;
}

function parseBookVolumesPath(path: string): number | null {
  const match = path.match(/^\/books\/(\d+)\/volumes$/);
  return match ? Number(match[1]) : null;
}

function parseBookChaptersPath(path: string): number | null {
  const match = path.match(/^\/books\/(\d+)\/chapters$/);
  return match ? Number(match[1]) : null;
}

function parseBookChapterPath(path: string): { bookId: number; chapterId: number } | null {
  const match = path.match(/^\/books\/(\d+)\/chapters\/(\d+)$/);
  return match ? { bookId: Number(match[1]), chapterId: Number(match[2]) } : null;
}

function parseBookStatePath(path: string): number | null {
  const match = path.match(/^\/books\/(\d+)\/state$/);
  return match ? Number(match[1]) : null;
}

function parseBookQualityPath(path: string): number | null {
  const match = path.match(/^\/books\/(\d+)\/quality$/);
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
