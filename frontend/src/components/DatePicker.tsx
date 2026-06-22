import { useEffect, useRef, useState } from "react";

interface Props {
  value: string; // "YYYY-MM-DD"
  onChange: (v: string) => void;
}

function parse(value: string): Date {
  const [y, m, d] = (value || "").split("-").map(Number);
  if (y && m && d) return new Date(y, m - 1, d);
  return new Date();
}
function fmt(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

/** 自定义日期选择器：点整个输入框即弹出大号日历，尺寸可控（不依赖原生控件）。 */
export default function DatePicker({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState(() => parse(value)); // 当前显示的月份
  const ref = useRef<HTMLDivElement>(null);

  // 外部值变化时，跟随定位到对应月份
  useEffect(() => {
    setView(parse(value));
  }, [value]);

  // 点击组件外部时关闭
  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const year = view.getFullYear();
  const month = view.getMonth();
  const firstWeekday = new Date(year, month, 1).getDay(); // 0=周日
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells: (number | null)[] = [];
  for (let i = 0; i < firstWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  function pick(d: number) {
    onChange(fmt(new Date(year, month, d)));
    setOpen(false);
  }

  return (
    <div className="datepicker" ref={ref}>
      <div className="datepicker-field" onClick={() => setOpen((o) => !o)}>
        <span>{value || "选择日期"}</span>
        <span className="datepicker-icon">📅</span>
      </div>

      {open && (
        <div className="datepicker-pop">
          <div className="datepicker-head">
            <button type="button" className="dp-nav" onClick={() => setView(new Date(year, month - 1, 1))}>
              ‹
            </button>
            <span className="dp-title">
              {year} 年 {month + 1} 月
            </span>
            <button type="button" className="dp-nav" onClick={() => setView(new Date(year, month + 1, 1))}>
              ›
            </button>
          </div>
          <div className="datepicker-grid">
            {WEEKDAYS.map((w) => (
              <span key={w} className="dp-wd">
                {w}
              </span>
            ))}
            {cells.map((d, i) =>
              d === null ? (
                <span key={`e${i}`} />
              ) : (
                <button
                  type="button"
                  key={d}
                  className={"dp-day" + (fmt(new Date(year, month, d)) === value ? " sel" : "")}
                  onClick={() => pick(d)}
                >
                  {d}
                </button>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}
