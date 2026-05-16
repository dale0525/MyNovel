import { describe, expect, test } from "vitest";

import {
  fieldEntries,
  normalizeBlueprintCandidates,
  summaryValue,
} from "@/features/open-book/blueprintCandidates";

describe("normalizeBlueprintCandidates", () => {
  test("merges candidate-specific fields over global blueprint fields", () => {
    const candidates = normalizeBlueprintCandidates({
      title_options: ["长夜档案", "禁书回声"],
      genre: "奇幻",
      audience: "成人类型小说读者",
      selling_points: ["禁书悬疑"],
      reader_promises: ["真相反转"],
      protagonist: { name: "林既明", identity: "档案员" },
      world: { summary: "禁书会吞噬记忆" },
      central_conflict: "档案员追查禁书真相。",
      chapter_directions: [{ title: "第1章", goal: "发现禁书" }],
      candidates: [
        {
          title: "长夜档案",
          genre: "都市奇幻",
          central_conflict: "档案员用禁书交易找回失踪同事。",
          selling_points: ["禁书代价", "记忆悬疑"],
        },
        {
          title: "禁书回声",
          audience: "悬疑推理读者",
          protagonist: { name: "沈回声", role: "修复师" },
          chapter_directions: [
            { title: "回声", goal: "听见第一本禁书里的求救声" },
            { title: "借阅证", goal: "发现借阅记录被篡改" },
          ],
        },
      ],
    });

    expect(candidates).toHaveLength(2);
    expect(candidates[0]).toMatchObject({
      index: 0,
      title: "长夜档案",
      genre: "都市奇幻",
      audience: "成人类型小说读者",
      centralConflict: "档案员用禁书交易找回失踪同事。",
      sellingPoints: ["禁书代价", "记忆悬疑"],
      readerPromises: ["真相反转"],
    });
    expect(candidates[1]).toMatchObject({
      index: 1,
      title: "禁书回声",
      genre: "奇幻",
      audience: "悬疑推理读者",
      protagonist: "沈回声 / 修复师",
    });
    expect(candidates[1].chapterDirections[0]).toEqual({
      number: 1,
      title: "回声",
      goal: "听见第一本禁书里的求救声",
    });
  });

  test("wraps old global-only content as one default candidate", () => {
    const candidates = normalizeBlueprintCandidates({
      title_options: ["长夜档案"],
      genre: "奇幻",
      audience: "成人",
      selling_points: ["禁书悬疑"],
      reader_promises: ["真相反转"],
      protagonist: "失意档案员",
      world: "禁书会吞噬记忆",
      central_conflict: "档案员追查禁书真相。",
      chapter_directions: ["发现禁书"],
    });

    expect(candidates).toHaveLength(1);
    expect(candidates[0]).toMatchObject({
      index: 0,
      title: "长夜档案",
      genre: "奇幻",
      audience: "成人",
      protagonist: "失意档案员",
      world: "禁书会吞噬记忆",
      centralConflict: "档案员追查禁书真相。",
    });
    expect(candidates[0].chapterDirections).toEqual([
      { number: 1, title: "第 01 章", goal: "发现禁书" },
    ]);
  });

  test("keeps unknown fields in extras for progressive disclosure", () => {
    const candidates = normalizeBlueprintCandidates({
      title_options: ["长夜档案"],
      genre: "奇幻",
      secret_sauce: "章节末尾都用禁书代价做钩子",
      candidates: [{ title: "长夜档案", market_angle: "悬疑向强钩子" }],
    });

    expect(candidates[0].extras).toEqual({
      market_angle: "悬疑向强钩子",
      secret_sauce: "章节末尾都用禁书代价做钩子",
    });
  });

  test("normalizes title-option candidates with aliases and renderable helper values", () => {
    const candidates = normalizeBlueprintCandidates({
      title_options: ["长夜档案", "禁书回声", "灰塔借阅证"],
      selected_title: "长夜档案",
      premise: "档案员追查禁书真相。",
      genre: "奇幻",
      audience: "成人",
      protagonist: { name: "林既明", identity: "档案员" },
      world: { rules: ["借书支付记忆", "逾期吞掉姓名"] },
      chapter_directions: [{ title: "旧馆", direction: "进入旧图书馆" }],
      candidates: [
        {
          selected_title: "禁书回声",
          genre: "悬疑奇幻",
          title_option: "不应覆盖匹配标题",
          book_title: "也不应覆盖匹配标题",
          market_angle: "强钩子",
        },
        {
          book_title: "灰塔借阅证",
          audience: "悬疑推理读者",
        },
      ],
    });

    expect(candidates).toHaveLength(3);
    expect(candidates[0]).toMatchObject({
      index: 0,
      title: "长夜档案",
      genre: "奇幻",
      audience: "成人",
      protagonist: "林既明 / 档案员",
      world: "借书支付记忆 / 逾期吞掉姓名",
    });
    expect(candidates[1]).toMatchObject({
      index: 1,
      title: "禁书回声",
      genre: "悬疑奇幻",
      audience: "成人",
    });
    expect(candidates[2]).toMatchObject({
      index: 2,
      title: "灰塔借阅证",
      genre: "奇幻",
      audience: "悬疑推理读者",
    });
    expect(candidates[0].chapterDirections).toEqual([
      { number: 1, title: "旧馆", goal: "进入旧图书馆" },
    ]);
    expect(candidates[1].extras).toEqual({ market_angle: "强钩子" });

    expect(summaryValue({ name: "林既明", identity: "档案员" })).toBe("林既明 / 档案员");
    expect(Object.fromEntries(fieldEntries({ name: "林既明", goal: "找回记忆" }))).toEqual({
      name: "林既明",
      goal: "找回记忆",
    });
  });

  test("falls back to index-matched candidates when title keys are missing", () => {
    const candidates = normalizeBlueprintCandidates({
      title_options: ["长夜档案", "禁书回声"],
      genre: "奇幻",
      audience: "成人",
      candidates: [{ genre: "候选A题材" }, { audience: "候选B读者" }],
    });

    expect(candidates).toHaveLength(2);
    expect(candidates[0]).toMatchObject({
      index: 0,
      title: "长夜档案",
      genre: "候选A题材",
      audience: "成人",
    });
    expect(candidates[1]).toMatchObject({
      index: 1,
      title: "禁书回声",
      genre: "奇幻",
      audience: "候选B读者",
    });
  });
});
