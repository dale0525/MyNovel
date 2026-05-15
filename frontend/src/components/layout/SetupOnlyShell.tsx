import type { ReactNode } from "react";

type SetupOnlyShellProps = {
  children: ReactNode;
};

export function SetupOnlyShell({ children }: SetupOnlyShellProps) {
  return (
    <main className="setup-only-shell">
      <section className="setup-only-shell__content" aria-label="模型配置">
        {children}
      </section>
    </main>
  );
}
