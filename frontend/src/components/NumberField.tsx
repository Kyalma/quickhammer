import TextField from "@mui/material/TextField";

/**
 * A bounded integer field. Backs most of the inputs in the unit editor, so the
 * min/max clamping and the numeric keypad hint live in one place.
 */
export function NumberField({
  label,
  value,
  onChange,
  min = 0,
  max = 99,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
}) {
  return (
    <TextField
      label={label}
      type="number"
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      slotProps={{ htmlInput: { min, max, inputMode: "numeric" } }}
      fullWidth
    />
  );
}
