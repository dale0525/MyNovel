import type { ReactNode } from "react";

type AppShellProps = {
  children: ReactNode;
};

const navItems = [
  { label: "工作台", href: "/" },
  { label: "开书", href: "/books/new" },
  { label: "项目", href: "/" },
  { label: "章节", href: "/review" },
  { label: "可信设定", href: "/review" },
  { label: "质量", href: "/review" },
  { label: "设置", href: "/provider-config" },
];

export function AppShell({ children }: AppShellProps) {
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
                item.label === "工作台" ? "app-shell__nav-link is-active" : "app-shell__nav-link"
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
