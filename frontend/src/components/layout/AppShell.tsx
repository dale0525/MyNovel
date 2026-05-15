import type { ReactNode } from "react";

type AppShellProps = {
  activePath: string;
  children: ReactNode;
};

const navItems = [
  { label: "工作台", href: "/", activePaths: ["/"] },
  { label: "开书", href: "/books/new", activePaths: ["/books/new"] },
  { label: "项目", href: "/", activePaths: ["/books/:id"] },
  { label: "章节", href: "/review", activePaths: ["/review"] },
  { label: "可信设定", href: "/review", activePaths: ["/review"] },
  { label: "质量", href: "/review", activePaths: ["/review"] },
  { label: "设置", href: "/settings/provider", activePaths: ["/settings/provider"] },
];

export function AppShell({ activePath, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar">
        <a className="app-shell__brand" href="/">
          <span>MyNovel</span>
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
              href={item.href}
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
