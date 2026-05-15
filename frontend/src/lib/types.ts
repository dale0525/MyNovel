export type BootstrapPayload = {
  providerConfigured: boolean;
  initialRoute: string;
  message: string | null;
};

export type BookPayload = {
  id: number | null;
  title: string;
  genre: string;
  audience: string;
  status: string;
  premise: string | null;
};

export type BooksPayload = {
  books: BookPayload[];
};

export type BlueprintPayload = {
  id: number | null;
  parentId: number | null;
  idea: string;
  version: number;
  status: "pending" | "running" | "succeeded" | "failed";
  instruction: string | null;
  content: Record<string, unknown>;
  parseError: string | null;
  errorMessage: string | null;
};

export type BlueprintResponse = {
  blueprint: BlueprintPayload;
};
