import type { ReactNode } from "react";

type AppShellProps = {
  children: ReactNode;
};

const navItems = ["工作台", "开书", "项目", "章节", "可信设定", "质量", "设置"];

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
              className={item === "工作台" ? "app-shell__nav-link is-active" : "app-shell__nav-link"}
              href={item === "工作台" ? "/" : "#"}
              key={item}
            >
              {item}
            </a>
          ))}
        </nav>
      </aside>
      <main className="app-shell__main">{children}</main>
    </div>
  );
}
