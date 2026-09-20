import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";

export default function LibraryDropdown<T extends string>({ value, onChange, options, label }: {
  value: T;
  onChange: (value: T) => void;
  options: readonly { value: T; label: string }[];
  label: string;
}) {
  const menuId = useId();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const items = useRef<(HTMLButtonElement | null)[]>([]);
  useEffect(() => {
    if (!open) return;
    items.current[options.findIndex((option) => option.value === value)]?.focus();
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open, value, options]);
  return <div className="library-sort" ref={root}
    onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
    }}>
    <button ref={trigger} type="button" className="library-sort-trigger"
      aria-label={`${label}: ${options.find((option) => option.value === value)?.label}`}
      aria-haspopup="menu" aria-expanded={open} aria-controls={menuId}
      onClick={() => setOpen(!open)}
      onKeyDown={(event) => {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault(); setOpen(true);
        }
      }}>
      {options.find((option) => option.value === value)?.label}<ChevronDown size={14} />
    </button>
    {open && <div id={menuId} role="menu" aria-label={label} className="library-sort-menu">
      {options.map((option, index) => <button key={option.value} type="button"
        ref={(element) => { items.current[index] = element; }}
        role="menuitemradio" aria-checked={value === option.value}
        onClick={() => { onChange(option.value); setOpen(false); trigger.current?.focus(); }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault(); setOpen(false); trigger.current?.focus();
          } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
            event.preventDefault();
            const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1
              : (index + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
            items.current[next]?.focus();
          }
        }}>
        {option.label}<Check size={14} style={{ visibility: value === option.value ? "visible" : "hidden" }} />
      </button>)}
    </div>}
  </div>;
}
