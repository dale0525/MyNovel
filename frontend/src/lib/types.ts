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
