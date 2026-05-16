export type ChapterDirectionView = {
  number: number;
  title: string;
  goal: string;
};

export type BlueprintCandidateView = {
  index: number;
  title: string;
  genre: string;
  audience: string;
  sellingPoints: string[];
  readerPromises: string[];
  protagonist: unknown;
  world: unknown;
  centralConflict: string;
  chapterDirections: ChapterDirectionView[];
  extras: Record<string, unknown>;
};

const knownFields = new Set([
  "audience",
  "book_title",
  "candidates",
  "central_conflict",
  "chapter_directions",
  "genre",
  "premise",
  "protagonist",
  "reader_promises",
  "selected_title",
  "selling_points",
  "title",
  "title_option",
  "title_options",
  "world",
]);

const titleFields = ["title", "selected_title", "title_option", "book_title"];
const summaryFields = ["summary", "name", "identity", "role", "goal", "flaw", "rules"];

export function normalizeBlueprintCandidates(content: unknown): BlueprintCandidateView[] {
  const blueprint = recordValue(content);
  const titleOptions = listValues(blueprint.title_options);
  const rawCandidates = Array.isArray(blueprint.candidates) ? blueprint.candidates : [];
  const candidateFields = rawCandidates
    .map((candidate) => recordValue(candidate))
    .filter((candidate) => Object.keys(candidate).length > 0);

  const orderedCandidates =
    titleOptions.length > 0
      ? candidatesForTitles(titleOptions, candidateFields)
      : candidatesWithoutTitleOptions(blueprint, candidateFields);

  return orderedCandidates.map((candidate, index) => {
    const merged = { ...blueprint, ...candidate };
    const optionTitle = titleOptions[index];
    const title = optionTitle || titleValue(candidate) || titleValue(blueprint);

    return {
      index,
      title,
      genre: textValue(merged.genre),
      audience: textValue(merged.audience),
      sellingPoints: listValues(merged.selling_points),
      readerPromises: listValues(merged.reader_promises),
      protagonist: merged.protagonist ?? "",
      world: merged.world ?? "",
      centralConflict: textValue(merged.central_conflict) || textValue(merged.premise),
      chapterDirections: normalizeChapterDirections(merged.chapter_directions),
      extras: extrasFor(blueprint, candidate),
    };
  });
}

export function textValue(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

export function listValues(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => textValue(item)).filter(Boolean);
  }
  const text = textValue(value);
  return text ? [text] : [];
}

export function summaryValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => summaryValue(item)).filter(Boolean).join(" / ");
  }

  const text = textValue(value);
  if (text) {
    return text;
  }

  const fields = recordValue(value);
  if (Object.keys(fields).length === 0) {
    return "";
  }

  const preferredSummary = summaryFields
    .map((field) => summaryValue(fields[field]))
    .filter(Boolean)
    .join(" / ");
  if (preferredSummary) {
    return preferredSummary;
  }

  return Object.values(fields).map((entryValue) => summaryValue(entryValue)).filter(Boolean).join(" / ");
}

export function fieldEntries(value: unknown): Array<[string, string]> {
  const fields = recordValue(value);
  const orderedKeys = [
    ...summaryFields.filter((field) => field in fields),
    ...Object.keys(fields).filter((field) => !summaryFields.includes(field)),
  ];
  return orderedKeys
    .map((key): [string, string] => [key, summaryValue(fields[key])])
    .filter(([, entryValue]) => entryValue.length > 0);
}

function recordValue(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function candidatesForTitles(
  titleOptions: string[],
  candidateFields: Record<string, unknown>[],
): Record<string, unknown>[] {
  const titleOptionSet = new Set(titleOptions);
  const usedIndexes = new Set<number>();

  return titleOptions.map((title, index) => {
    const titleMatchIndex = candidateFields.findIndex((candidate, candidateIndex) => {
      return !usedIndexes.has(candidateIndex) && titleValue(candidate) === title;
    });
    if (titleMatchIndex !== -1) {
      usedIndexes.add(titleMatchIndex);
      return candidateFields[titleMatchIndex];
    }

    const indexMatch = candidateFields[index];
    if (!indexMatch || usedIndexes.has(index)) {
      return {};
    }

    const indexMatchTitle = titleValue(indexMatch);
    if (indexMatchTitle && titleOptionSet.has(indexMatchTitle) && indexMatchTitle !== title) {
      return {};
    }

    usedIndexes.add(index);
    return indexMatch ?? {};
  });
}

function candidatesWithoutTitleOptions(
  blueprint: Record<string, unknown>,
  candidateFields: Record<string, unknown>[],
): Record<string, unknown>[] {
  if (candidateFields.length > 0) {
    return candidateFields.filter((candidate) => titleValue(candidate));
  }

  return titleValue(blueprint) ? [{}] : [];
}

function titleValue(fields: Record<string, unknown>): string {
  for (const field of titleFields) {
    const title = textValue(fields[field]);
    if (title) {
      return title;
    }
  }
  return "";
}

function normalizeChapterDirections(value: unknown): ChapterDirectionView[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((item, index) => {
    const fields = recordValue(item);
    const number = index + 1;
    if (Object.keys(fields).length > 0) {
      return {
        number,
        title: textValue(fields.title) || defaultChapterTitle(number),
        goal:
          textValue(fields.goal) ||
          textValue(fields.direction) ||
          textValue(fields.summary) ||
          textValue(fields.title),
      };
    }

    return {
      number,
      title: defaultChapterTitle(number),
      goal: textValue(item),
    };
  });
}

function defaultChapterTitle(number: number): string {
  return `第 ${String(number).padStart(2, "0")} 章`;
}

function extrasFor(
  blueprint: Record<string, unknown>,
  candidate: Record<string, unknown>,
): Record<string, unknown> {
  return {
    ...unknownFields(blueprint),
    ...unknownFields(candidate),
  };
}

function unknownFields(fields: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(fields).filter(([key]) => !knownFields.has(key)),
  );
}
