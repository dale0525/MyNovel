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

export type ChapterPayload = {
  id: number | null;
  bookId: number;
  number: number;
  title: string;
  status: string;
  summary: string;
  wordCount: number;
  reviewerNote: string | null;
  updatedAt: string | null;
};

export type ChapterDetailPayload = ChapterPayload & {
  plan: Record<string, unknown>;
  contextPackage: Record<string, unknown>;
  draftText: string;
  revisedText: string;
  finalText: string;
  auditReport: Record<string, unknown>;
  stateDelta: Record<string, unknown>;
};

export type ChapterStageSlotPayload = {
  key: "plan" | "context" | "draft" | "delta" | "audit" | string;
  label: string;
  ready: boolean;
  status: string;
  summary: string;
};

export type CanonPayload = {
  id: number | null;
  bookId: number;
  version: number;
  content: Record<string, unknown>;
  createdAt: string | null;
};

export type RunTracePayload = {
  id: number | null;
  bookId: number | null;
  stage: string;
  promptId: string | null;
  promptVersion: string | null;
  model: string | null;
  cost: Record<string, unknown>;
  metadata: Record<string, unknown>;
  createdAt: string | null;
};

export type VolumePlanPayload = {
  id: number | null;
  bookId: number;
  volumeNumber: number;
  title: string;
  coreConflict: string;
  pacingCurve: unknown[];
  payoffDistribution: unknown[];
  keyTurns: unknown[];
  commitments: unknown[];
};

export type StyleAssetPayload = {
  id: number | null;
  bookId: number;
  name: string;
  sourceTitle: string | null;
  sourceExcerpt: string;
  fingerprint: Record<string, unknown>;
  guidance: Record<string, unknown>;
  createdAt: string | null;
};

export type DeconstructionStudyPayload = {
  id: number | null;
  bookId: number;
  sourceTitle: string;
  sourceExcerpt: string;
  beatMap: unknown[];
  craftNotes: Record<string, unknown>;
  createdAt: string | null;
};

export type QualitySnapshotPayload = {
  id: number | null;
  bookId: number;
  score: number;
  metrics: Record<string, unknown>;
  recommendations: unknown[];
  createdAt: string | null;
};

export type CostStrategyPayload = {
  mode: string;
  batch_limit: number;
  context_policy: string;
};

export type WordTargetsPayload = {
  targetWordCount: number;
  chapterWordCount: number;
};

export type BookResponse = {
  book: BookPayload;
  wordTargets: WordTargetsPayload;
  chapters: ChapterPayload[];
  latestCanon: CanonPayload | null;
  runTraces: RunTracePayload[];
  volumePlans: VolumePlanPayload[];
};

export type QualityResponse = {
  book: BookPayload;
  styleAssets: StyleAssetPayload[];
  deconstructionStudies: DeconstructionStudyPayload[];
  latestSnapshot: QualitySnapshotPayload | null;
  costStrategy: CostStrategyPayload | null;
};

export type ChapterResponse = {
  book: BookPayload;
  chapter: ChapterDetailPayload;
  siblingChapters: ChapterPayload[];
  latestCanon: CanonPayload | null;
  traces: RunTracePayload[];
  stageSlots: ChapterStageSlotPayload[];
};

export type CanonSectionPayload = {
  key: string;
  anchor: string;
  label: string;
  editable: boolean;
  locked: boolean;
  content: unknown;
};

export type CanonProposalRevisionPayload = {
  id: number | null;
  bookId: number;
  baseCanonVersion: number;
  targetSection: string;
  instruction: string;
  allowedSections: string[];
  lockedSections: string[];
  changedSections: Record<string, unknown>;
  blockedSections: unknown[];
  summary: string;
  risks: unknown[];
  status: string;
  createdAt: string | null;
  appliedAt: string | null;
};

export type TrustedStateResponse = {
  book: BookPayload;
  latestCanon: CanonPayload | null;
  canonSections: CanonSectionPayload[];
  sectionLocks: Record<string, boolean>;
  readiness: {
    complete: boolean;
    missingSections: string[];
    messages: string[];
  };
  pendingRevisions: CanonProposalRevisionPayload[];
  selectedRevision: CanonProposalRevisionPayload | null;
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
