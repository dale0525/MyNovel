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
