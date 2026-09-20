import { useEffect, useRef, useState, type ReactNode } from "react";

type MultiSelectDropdownProps = {
  label: string;
  summary: string;
  children: ReactNode;
};

export function MultiSelectDropdown({
  label,
  summary,
  children,
}: MultiSelectDropdownProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    function handlePointerDown(event: PointerEvent) {
      if (rootRef.current?.contains(event.target as Node)) {
        return;
      }
      setOpen(false);
    }
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [open]);

  return (
    <div className="toolbar__field">
      <span>{label}</span>
      <details
        ref={rootRef}
        className="multi-select"
        aria-label={label}
        open={open}
        onToggle={(event) => setOpen(event.currentTarget.open)}
      >
        <summary>{summary}</summary>
        <div className="multi-select__menu">{children}</div>
      </details>
    </div>
  );
}
