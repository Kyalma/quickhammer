import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { emptyUnit, emptyWeapon, type Unit, type Weapon } from "../api/types";
import { NumberField } from "../components/NumberField";
import { useConfirm } from "../hooks/useConfirm";

/** Fields that sit side by side on a tablet and stack on a phone. */
function FieldRow({ children }: { children: React.ReactNode }) {
  return (
    <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 1.5 }}>
      {children}
    </Stack>
  );
}

export function UnitEditorPage() {
  const { unitId } = useParams();
  const navigate = useNavigate();
  const isNew = unitId === "new";
  const [unit, setUnit] = useState<Unit>(emptyUnit());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pictureName, setPictureName] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [confirm, confirmDialog] = useConfirm();

  useEffect(() => {
    if (!isNew) {
      api.get<Unit>(`/api/units/${unitId}`).then(setUnit).catch((e) => setError(e.message));
    }
  }, [unitId, isNew]);

  function patch(partial: Partial<Unit>) {
    setUnit((u) => ({ ...u, ...partial }));
  }

  function patchWeapon(index: number, partial: Partial<Weapon>) {
    setUnit((u) => ({
      ...u,
      weapons: u.weapons.map((w, i) => (i === index ? { ...w, ...partial } : w)),
    }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      // Clean up in-progress typing: trim keywords, drop empties.
      const payload: Unit = {
        ...unit,
        keywords: unit.keywords.map((k) => k.trim()).filter(Boolean),
        weapons: unit.weapons.map((w) => ({
          ...w,
          keywords: w.keywords.map((k) => k.trim()).filter(Boolean),
        })),
      };
      let saved: Unit;
      if (isNew) {
        saved = await api.post<Unit>("/api/units", payload);
      } else {
        saved = await api.put<Unit>(`/api/units/${unitId}`, payload);
      }
      // Upload the picture if one was chosen.
      const file = fileInput.current?.files?.[0];
      if (file) {
        saved = await api.upload<Unit>(`/api/units/${saved.id}/image`, file);
      }
      navigate("/roster");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    const ok = await confirm({
      title: `Delete ${unit.name || "this unit"}?`,
      message: "The unit is removed from your roster and from any army it was fielded in.",
    });
    if (!ok) return;
    await api.delete(`/api/units/${unitId}`);
    navigate("/roster");
  }

  return (
    <form onSubmit={save}>
      {confirmDialog}
      <Typography variant="h5" gutterBottom>
        {isNew ? "New unit" : `Edit ${unit.name}`}
      </Typography>
      {error && <Typography color="error">{error}</Typography>}

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <TextField
            label="Unit name"
            value={unit.name}
            onChange={(e) => patch({ name: e.target.value })}
            required
            placeholder="e.g. Intercessor Squad"
            fullWidth
            sx={{ mb: 1.5 }}
          />
          <FieldRow>
            <TextField
              label="Faction"
              value={unit.faction}
              onChange={(e) => patch({ faction: e.target.value })}
              placeholder="e.g. Space Marines"
              fullWidth
              sx={{ flex: 2 }}
            />
            <Box sx={{ flex: 1 }}>
              <NumberField
                label="Points"
                value={unit.points}
                onChange={(v) => patch({ points: v })}
                max={10000}
              />
            </Box>
          </FieldRow>
          <TextField
            label="Keywords (comma-separated)"
            helperText="MONSTER and VEHICLE may fire pistols alongside their other weapons."
            value={unit.keywords.join(",")}
            onChange={(e) => patch({ keywords: e.target.value.split(",") })}
            placeholder="Infantry, Battleline, Imperium"
            fullWidth
            sx={{ mb: 1.5 }}
          />

          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", mb: 1.5 }}>
            {unit.image_path && (
              <Box
                component="img"
                src={unit.image_path}
                alt={unit.name}
                sx={{ width: 96, height: 96, objectFit: "cover", borderRadius: 1 }}
              />
            )}
            <Box>
              <Button component="label" variant="outlined">
                {unit.image_path ? "Replace picture" : "Choose picture"}
                <input
                  ref={fileInput}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  hidden
                  onChange={(e) => setPictureName(e.target.files?.[0]?.name ?? null)}
                />
              </Button>
              {pictureName && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  {pictureName} — uploads when you save
                </Typography>
              )}
            </Box>
          </Stack>

          <Typography variant="h6" gutterBottom>
            Statline
          </Typography>
          <FieldRow>
            <NumberField
              label={'Movement (")'}
              value={unit.movement}
              onChange={(v) => patch({ movement: v })}
              max={30}
            />
            <NumberField
              label="Toughness"
              value={unit.toughness}
              onChange={(v) => patch({ toughness: v })}
              min={1}
              max={16}
            />
            <NumberField
              label="Save (X+)"
              value={unit.save}
              onChange={(v) => patch({ save: v })}
              min={2}
              max={7}
            />
          </FieldRow>
          <FieldRow>
            <TextField
              label="Invulnerable save (X++)"
              helperText="Blank means none"
              type="number"
              value={unit.invuln_save ?? ""}
              onChange={(e) =>
                patch({ invuln_save: e.target.value === "" ? null : Number(e.target.value) })
              }
              slotProps={{ htmlInput: { min: 2, max: 6, inputMode: "numeric" } }}
              fullWidth
            />
            <NumberField
              label="Wounds / model"
              value={unit.wounds}
              onChange={(v) => patch({ wounds: v })}
              min={1}
              max={40}
            />
            <NumberField
              label="Models"
              value={unit.model_count}
              onChange={(v) => patch({ model_count: v })}
              min={1}
              max={30}
            />
          </FieldRow>
          <FieldRow>
            <NumberField
              label="Leadership"
              value={unit.leadership}
              onChange={(v) => patch({ leadership: v })}
              min={4}
              max={10}
            />
            <NumberField label="OC" value={unit.oc} onChange={(v) => patch({ oc: v })} max={10} />
          </FieldRow>
        </CardContent>
      </Card>

      <Typography variant="h6" gutterBottom>
        Weapons
      </Typography>
      {unit.weapons.map((weapon, index) => (
        <Card key={index} sx={{ mb: 2 }}>
          <CardContent>
            <FieldRow>
              <TextField
                label="Weapon name"
                value={weapon.name}
                onChange={(e) => patchWeapon(index, { name: e.target.value })}
                required
                placeholder="e.g. Bolt rifle"
                fullWidth
                sx={{ flex: 2 }}
              />
              <TextField
                select
                label="Type"
                value={weapon.kind}
                onChange={(e) =>
                  patchWeapon(index, { kind: e.target.value as Weapon["kind"] })
                }
                fullWidth
                sx={{ flex: 1 }}
              >
                <MenuItem value="ranged">Ranged</MenuItem>
                <MenuItem value="melee">Melee</MenuItem>
              </TextField>
            </FieldRow>
            <FieldRow>
              <NumberField
                label={'Range (")'}
                value={weapon.range}
                onChange={(v) => patchWeapon(index, { range: v })}
                max={120}
              />
              <TextField
                label="Attacks"
                helperText="e.g. 2, D6, D6+1"
                value={weapon.attacks}
                onChange={(e) => patchWeapon(index, { attacks: e.target.value })}
                placeholder="D6+1"
                required
                fullWidth
              />
              <NumberField
                label={weapon.kind === "ranged" ? "BS (X+)" : "WS (X+)"}
                value={weapon.skill}
                onChange={(v) => patchWeapon(index, { skill: v })}
                min={2}
                max={6}
              />
            </FieldRow>
            <FieldRow>
              <NumberField
                label="Strength"
                value={weapon.strength}
                onChange={(v) => patchWeapon(index, { strength: v })}
                min={1}
                max={24}
              />
              <TextField
                label="AP (0 to -6)"
                type="number"
                value={weapon.ap === 0 ? 0 : -weapon.ap}
                onChange={(e) =>
                  // Displayed in 40k notation (-2); stored as a positive number.
                  patchWeapon(index, { ap: Math.min(6, Math.abs(Number(e.target.value))) })
                }
                slotProps={{ htmlInput: { min: -6, max: 0, inputMode: "numeric" } }}
                fullWidth
              />
              <TextField
                label="Damage"
                helperText="e.g. 1, D3, D6+2"
                value={weapon.damage}
                onChange={(e) => patchWeapon(index, { damage: e.target.value })}
                placeholder="D3"
                required
                fullWidth
              />
            </FieldRow>
            <TextField
              label="Keywords (comma-separated)"
              helperText="SUSTAINED HITS 1, LETHAL HITS, TORRENT, PISTOL"
              value={weapon.keywords.join(",")}
              onChange={(e) =>
                // Split without trimming so a trailing comma survives while
                // typing; keywords are cleaned up on save.
                patchWeapon(index, { keywords: e.target.value.split(",") })
              }
              fullWidth
              sx={{ mb: 1.5 }}
            />
            <Box sx={{ mb: 1.5, maxWidth: { sm: 280 } }}>
              <NumberField
                label="Models carrying this (0 = all)"
                value={weapon.carrier_count}
                onChange={(v) => patchWeapon(index, { carrier_count: v })}
                max={30}
              />
            </Box>
            <Button
              type="button"
              color="error"
              onClick={() =>
                setUnit((u) => ({ ...u, weapons: u.weapons.filter((_, i) => i !== index) }))
              }
            >
              Remove weapon
            </Button>
          </CardContent>
        </Card>
      ))}
      <Button
        type="button"
        onClick={() => setUnit((u) => ({ ...u, weapons: [...u.weapons, emptyWeapon()] }))}
        sx={{ mb: 2 }}
      >
        Add weapon
      </Button>

      <Stack direction="row" spacing={1.5}>
        <Button variant="contained" type="submit" disabled={busy}>
          {busy ? "Saving…" : "Save unit"}
        </Button>
        {!isNew && (
          <Button type="button" color="error" onClick={remove}>
            Delete unit
          </Button>
        )}
      </Stack>
    </form>
  );
}
