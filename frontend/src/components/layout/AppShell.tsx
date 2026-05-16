import type { ReactNode } from "react";

type AppShellProps = {
  activePath: string;
  currentPath?: string;
  children: ReactNode;
};

const navItems = [
  { label: "工作台", href: "/", activePaths: ["/"] },
  { label: "开书", href: "/books/new", activePaths: ["/books/new"] },
  { label: "导入", href: "/books/import", activePaths: ["/books/import"] },
  { label: "项目", href: "/", activePaths: ["/books/:id"], bookHref: (bookId: number) => `/books/${bookId}` },
  {
    label: "可信设定",
    href: "/",
    activePaths: ["/books/:id/state"],
    bookHref: (bookId: number) => `/books/${bookId}/state`,
  },
  {
    label: "质量",
    href: "/",
    activePaths: ["/books/:id/quality"],
    bookHref: (bookId: number) => `/books/${bookId}/quality`,
  },
  { label: "更新", href: "/updates", activePaths: ["/updates"] },
  { label: "设置", href: "/settings/provider", activePaths: ["/settings/provider"] },
];

export function AppShell({ activePath, currentPath = window.location.pathname, children }: AppShellProps) {
  const currentBookId = parseCurrentBookId(currentPath);
  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar">
        <a className="app-shell__brand" href="/">
          <span>长篇创作</span>
          <strong>创作中枢</strong>
        </a>
        <nav className="app-shell__nav" aria-label="主导航">
          {navItems.map((item) => (
            <a
              className={
                item.activePaths.includes(activePath)
                  ? "app-shell__nav-link is-active"
                  : "app-shell__nav-link"
              }
              href={item.bookHref && currentBookId !== null ? item.bookHref(currentBookId) : item.href}
              key={item.label}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </aside>
      <main className="app-shell__main">{children}</main>
    </div>
  );
}

function parseCurrentBookId(path: string): number | null {
  const match = path.match(/^\/books\/(\d+)(?:\/state|\/quality)?$/);
  return match ? Number(match[1]) : null;
}
