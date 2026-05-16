import { useRef, useState } from "react";

import { ApiError, postJson } from "@/lib/api";
import { navigateTo } from "@/lib/navigation";

type OpenBookResponse = {
  blueprintId: number;
  redirectTo: string;
};

const ideaPresets = [
  "失意档案员重建禁书图书馆",
  "退役机甲师在废土开一家维修铺",
  "被流放的巡夜人继承一座会说话的城",
];

const genrePresets = [
  "玄幻升级",
  "都市异能",
  "仙侠修真",
  "科幻机甲",
  "废土生存",
  "悬疑推理",
  "古代言情",
  "穿越重生",
  "无限流",
  "奇幻冒险",
  "历史架空",
  "赛博朋克",
];

const audiencePresets = [
  "男频网文读者",
  "女频网文读者",
  "轻小说读者",
  "悬疑推理读者",
  "科幻读者",
  "成长冒险读者",
  "成人类型小说读者",
  "泛娱乐爽文读者",
];

const sellingPointPresets = [
  "逆袭反转",
  "智商碾压",
  "打脸爽感",
  "群像高燃",
  "升级成长",
  "强情绪拉扯",
  "悬念钩子",
  "经营建设",
];

const constraintPresets = [
  "不写虐主",
  "不写恋爱线",
  "不写后宫",
  "不写低智反派",
  "不写重口暴力",
  "不写现实政治",
  "不写未成年人危险内容",
];

type PresetFieldProps = {
  label: string;
  mode?: "append" | "replace";
  onChange: (value: string) => void;
  placeholder: string;
  presets: string[];
  value: string;
};

export function OpenBookPage() {
  const [idea, setIdea] = useState("");
  const [genre, setGenre] = useState("");
  const [audience, setAudience] = useState("");
  const [sellingPoints, setSellingPoints] = useState("");
  const [constraints, setConstraints] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isSubmittingRef = useRef(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmittingRef.current) {
      return;
    }
    isSubmittingRef.current = true;
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
      navigateTo(response.redirectTo);
    } catch (submitError) {
      setError(submitError instanceof ApiError ? submitError.message : "开书请求失败。");
    } finally {
      isSubmittingRef.current = false;
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
          <PresetField
            label="题材"
            onChange={setGenre}
            placeholder="留空：交给 AI 判断；也可手填"
            presets={genrePresets}
            value={genre}
          />
          <PresetField
            label="目标读者"
            onChange={setAudience}
            placeholder="留空：交给 AI 判断；也可手填"
            presets={audiencePresets}
            value={audience}
          />
        </div>

        <PresetField
          label="爽点偏好"
          mode="append"
          onChange={setSellingPoints}
          placeholder="留空：交给 AI 判断；也可手填或点多个预设"
          presets={sellingPointPresets}
          value={sellingPoints}
        />
        <PresetField
          label="写作禁区"
          mode="append"
          onChange={setConstraints}
          placeholder="留空：交给 AI 判断；也可手填或点多个预设"
          presets={constraintPresets}
          value={constraints}
        />

        <button className="workbench-action-button" disabled={isSubmitting} type="submit">
          {isSubmitting ? "生成中..." : "生成蓝图"}
        </button>
      </form>
    </section>
  );
}

function PresetField({
  label,
  mode = "replace",
  onChange,
  placeholder,
  presets,
  value,
}: PresetFieldProps) {
  function applyPreset(preset: string) {
    onChange(mode === "append" ? appendPresetValue(value, preset) : preset);
  }

  return (
    <div className="open-book-preset-field">
      <label className="provider-field">
        {label}
        <input
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          value={value}
        />
      </label>
      <div className="open-book-presets open-book-presets--compact">
        {presets.map((preset) => (
          <button key={preset} onClick={() => applyPreset(preset)} type="button">
            {preset}
          </button>
        ))}
      </div>
    </div>
  );
}

function appendPresetValue(currentValue: string, preset: string) {
  const trimmedValue = currentValue.trim();
  if (!trimmedValue) {
    return preset;
  }

  const existingValues = trimmedValue
    .split(/[、,，;；\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (existingValues.includes(preset)) {
    return trimmedValue;
  }
  return `${trimmedValue}、${preset}`;
}
