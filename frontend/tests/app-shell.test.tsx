import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { AppShell } from "@/components/layout/AppShell";

afterEach(() => {
  cleanup();
});

test("project nav keeps the current book context and trusted state is project-local", () => {
  render(
    <AppShell activePath="/books/:id/chapters/:chapterId" currentPath="/books/42/chapters/8">
      <div>content</div>
    </AppShell>,
  );

  expect(screen.getByRole("link", { name: "项目" })).toHaveAttribute("href", "/books/42");
  expect(screen.queryByRole("link", { name: "可信设定" })).not.toBeInTheDocument();
});

test("navigation does not expose review placeholder links", () => {
  render(
    <AppShell activePath="/" currentPath="/">
      <div>content</div>
    </AppShell>,
  );

  expect(screen.queryByRole("link", { name: "章节" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "质量" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "质量复审" })).not.toBeInTheDocument();
});

test("project nav opens the project chooser when no book is active", () => {
  render(
    <AppShell activePath="/" currentPath="/">
      <div>content</div>
    </AppShell>,
  );

  expect(screen.getByRole("link", { name: "项目" })).toHaveAttribute("href", "/books");
});

test("project nav stays active for project quality tab", () => {
  render(
    <AppShell activePath="/books/:id/quality" currentPath="/books/42/quality">
      <div>content</div>
    </AppShell>,
  );

  expect(screen.getByRole("link", { name: "项目" })).toHaveAttribute("href", "/books/42");
  expect(screen.getByRole("link", { name: "项目" })).toHaveClass("is-active");
});

test("project nav keeps the current book context for project volumes tab", () => {
  render(
    <AppShell activePath="/books/:id/volumes" currentPath="/books/42/volumes">
      <div>content</div>
    </AppShell>,
  );

  expect(screen.getByRole("link", { name: "项目" })).toHaveAttribute("href", "/books/42");
  expect(screen.getByRole("link", { name: "项目" })).toHaveClass("is-active");
});
