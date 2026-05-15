import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { AppShell } from "@/components/layout/AppShell";

afterEach(() => {
  cleanup();
});

test("trusted state nav keeps the current book context", () => {
  render(
    <AppShell activePath="/books/:id/state" currentPath="/books/42/state">
      <div>content</div>
    </AppShell>,
  );

  expect(screen.getByRole("link", { name: "可信设定" })).toHaveAttribute(
    "href",
    "/books/42/state",
  );
});

test("navigation does not expose review placeholder links", () => {
  render(
    <AppShell activePath="/" currentPath="/">
      <div>content</div>
    </AppShell>,
  );

  expect(screen.queryByRole("link", { name: "章节" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "质量" })).toHaveAttribute("href", "/");
  expect(screen.queryByRole("link", { name: "质量复审" })).not.toBeInTheDocument();
});
