import { useState } from "react";

import { ApiError, postJson } from "@/lib/api";

type OpenBookResponse = {
  blueprintId: number;
  redirectTo: string;
};

const ideaPresets = [
  "失意档案员重建禁书图书馆",
  "退役机甲师在废土开一家维修铺",
  "被流放的巡夜人继承一座会说话的城",
];

export function OpenBookPage() {
  const [idea, setIdea] = useState("");
  const [genre, setGenre] = useState("");
  const [audience, setAudience] = useState("");
  const [sellingPoints, setSellingPoints] = useState("");
  const [constraints, setConstraints] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const response = await postJson<OpenBookResponse>("/api/open-book", {
        idea,
        genre,
        audience,
        selling_points: sellingPoints,
        constraints,
      });
      window.history.pushState(null, "", response.redirectTo);
    } catch (submitError) {
      setError(submitError instanceof ApiError ? submitError.message : "开书请求失败。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="workbench-page open-book-page" aria-labelledby="open-book-title">
      <div className="workbench-hero open-book-hero">
        <p className="eyebrow">Open Book</p>
        <h1 id="open-book-title">开一本新书</h1>
        <p className="lede">输入一句有效灵感，系统会生成可修订的开书蓝图。</p>
      </div>

      <form className="workbench-panel open-book-form" onSubmit={handleSubmit}>
        {error && (
          <p className="setup-message" role="alert">
            {error}
          </p>
        )}
        <label className="provider-field open-book-idea">
          故事灵感
          <textarea
            onChange={(event) => setIdea(event.target.value)}
            placeholder="一个失意档案员重建禁书图书馆"
            required
            value={idea}
          />
        </label>

        <div className="open-book-presets" aria-label="灵感预设">
          {ideaPresets.map((preset) => (
            <button key={preset} onClick={() => setIdea(preset)} type="button">
              {preset}
            </button>
          ))}
        </div>

        <div className="provider-form-grid">
          <label className="provider-field">
            题材
            <input onChange={(event) => setGenre(event.target.value)} value={genre} />
          </label>
          <label className="provider-field">
            目标读者
            <input onChange={(event) => setAudience(event.target.value)} value={audience} />
          </label>
        </div>

        <label className="provider-field">
          爽点偏好
          <input
            onChange={(event) => setSellingPoints(event.target.value)}
            value={sellingPoints}
          />
        </label>
        <label className="provider-field">
          写作禁区
          <input onChange={(event) => setConstraints(event.target.value)} value={constraints} />
        </label>

        <button className="workbench-action-button" disabled={isSubmitting} type="submit">
          {isSubmitting ? "生成中..." : "生成蓝图"}
        </button>
      </form>
    </section>
  );
}
