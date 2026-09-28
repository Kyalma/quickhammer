// TypeScript mirrors of the backend Pydantic schemas.

export interface Player {
  id: number;
  name: string;
  is_admin: boolean;
}

export interface AdminPlayer {
  id: number;
  name: string;
  is_admin: boolean;
  unit_count: number;
}

export interface AdminGame {
  id: number;
  code: string;
  status: GameStatus;
  current_round: number;
  phase_name: string;
  player_names: string[];
  active_player: string | null;
}

export interface TokenResponse {
  token: string;
  player: Player;
}

export type WeaponKind = "ranged" | "melee";

export interface Weapon {
  id?: number;
  name: string;
  kind: WeaponKind;
  range: number;
  attacks: string; // dice notation: "2", "D6", "2D6+1"
  skill: number;   // BS/WS: 3 means 3+
  strength: number;
  ap: number;      // positive: 2 means AP-2
  damage: string;  // dice notation
  keywords: string[];
}

export interface Unit {
  id?: number;
  owner_id?: number;
  name: string;
  faction: string;
  points: number;
  image_path?: string | null;
  movement: number;
  toughness: number;
  save: number;
  invuln_save: number | null;
  wounds: number;
  leadership: number;
  oc: number;
  model_count: number;
  weapons: Weapon[];
}

export type GameStatus = "lobby" | "active" | "finished";

/** A unit as fielded in one game. `id` is the game entry, not the roster unit. */
export interface ArmyUnitSummary {
  id: number;
  unit_id: number;
  name: string;
  points: number;
  model_count: number;
  wounds: number;
  leadership: number;
  models_remaining: number;
  wounds_lost: number;
  is_destroyed: boolean;
  below_half_strength: boolean;
  is_battle_shocked: boolean;
  needs_shock_test: boolean;
}

export interface GamePlayer {
  player: Player;
  is_ready: boolean;
  turn_order: number;
  faction: string;
  army: ArmyUnitSummary[];
  army_points: number;
  command_points: number;
}

export interface BattleShockResult {
  unit_name: string;
  roll: number;
  leadership: number;
  passed: boolean;
  game: Game;
}

export interface GameArmy {
  player: Player;
  faction: string;
  units: Unit[];
}

export const UNALIGNED = "Unaligned";

/** Display label for a faction value ("" means no faction set). */
export function factionLabel(faction: string): string {
  return faction.trim() || UNALIGNED;
}

export interface Game {
  id: number;
  code: string;
  status: GameStatus;
  current_phase: number;
  phase_name: string;
  current_round: number;
  active_player_id: number | null;
  players: GamePlayer[];
}

export interface CombatStep {
  label: string;
  value: number;
  detail: string;
}

export interface CombatResult {
  attacker: string;
  weapon: string;
  defender: string;
  steps: CombatStep[];
  expected_damage: number;
  expected_models_slain: number;
  notes: string[];
}

export interface LibraryFaction {
  name: string;
  faction_type: string;
  unit_count: number;
}

export interface LibraryUnitSummary {
  id: string;
  name: string;
  faction: string;
  points: number | null;
  min_models: number | null;
  max_models: number | null;
}

export const PHASES = ["Command", "Movement", "Shooting", "Charge", "Fight"] as const;

export function emptyWeapon(): Weapon {
  return {
    name: "",
    kind: "ranged",
    range: 24,
    attacks: "1",
    skill: 3,
    strength: 4,
    ap: 0,
    damage: "1",
    keywords: [],
  };
}

export function emptyUnit(): Unit {
  return {
    name: "",
    faction: "",
    points: 0,
    movement: 6,
    toughness: 4,
    save: 3,
    invuln_save: null,
    wounds: 2,
    leadership: 6,
    oc: 1,
    model_count: 1,
    weapons: [],
  };
}
