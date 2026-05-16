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
  "candidates",
  "central_conflict",
  "chapter_directions",
  "genre",
  "protagonist",
  "reader_promises",
  "selling_points",
  "title",
  "title_options",
  "world",
]);

export function normalizeBlueprintCandidates(content: unknown): BlueprintCandidateView[] {
  const blueprint = fieldEntries(content);
  const titleOptions = listValues(blueprint.title_options);
  const rawCandidates = Array.isArray(blueprint.candidates) ? blueprint.candidates : [];
  const candidateFields = rawCandidates
    .map((candidate) => fieldEntries(candidate))
    .filter((candidate) => Object.keys(candidate).length > 0);

  const orderedCandidates =
    candidateFields.length > 0
      ? orderCandidatesByTitle(titleOptions, candidateFields)
      : [fieldEntries({ title: titleOptions[0] })];

  return orderedCandidates.map((candidate, index) => {
    const merged = { ...blueprint, ...candidate };

    return {
      index,
      title: textValue(merged.title) || titleOptions[index] || `Candidate ${index + 1}`,
      genre: textValue(merged.genre),
      audience: textValue(merged.audience),
      sellingPoints: listValues(merged.selling_points),
      readerPromises: listValues(merged.reader_promises),
      protagonist: summaryValue(merged.protagonist),
      world: summaryValue(merged.world),
      centralConflict: textValue(merged.central_conflict),
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

export function summaryValue(value: unknown): unknown {
  const fields = fieldEntries(value);
  if (Object.keys(fields).length === 1 && "summary" in fields) {
    return textValue(fields.summary);
  }
  return value;
}

export function fieldEntries(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function orderCandidatesByTitle(
  titleOptions: string[],
  candidateFields: Record<string, unknown>[],
): Record<string, unknown>[] {
  if (titleOptions.length === 0) {
    return candidateFields;
  }

  const remaining = [...candidateFields];
  const ordered = titleOptions.flatMap((title) => {
    const matchIndex = remaining.findIndex((candidate) => textValue(candidate.title) === title);
    if (matchIndex === -1) {
      return [];
    }
    const [match] = remaining.splice(matchIndex, 1);
    return [match];
  });

  return [...ordered, ...remaining];
}

function normalizeChapterDirections(value: unknown): ChapterDirectionView[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((item, index) => {
    const fields = fieldEntries(item);
    const number = index + 1;
    if (Object.keys(fields).length > 0) {
      return {
        number,
        title: textValue(fields.title) || defaultChapterTitle(number),
        goal: textValue(fields.goal) || textValue(fields.summary),
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
