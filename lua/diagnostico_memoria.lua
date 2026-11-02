-- Diagnostico 2/4: valida controles e memoria por ramos do mesmo savestate.
-- Gera diagnostico_memoria.csv. Pare qualquer outro script Lua antes de rodar.

local source = debug.getinfo(1, "S").source or ""
if source:sub(1, 1) == "@" then source = source:sub(2) end
local sep = package.config:sub(1, 1)
local function join(a, b) return a .. sep .. b end
local function dirname(path) return path:match("^(.*)[/\\][^/\\]+$") end
local function exists(path) local f = io.open(path, "r"); if f then f:close(); return true end; return false end
local function locate_profile()
  local candidates = {join(".", "config" .. sep .. "game_profile.ini"), join("..", "config" .. sep .. "game_profile.ini")}
  if source ~= "" and source:sub(1, 1) ~= "[" then local d = dirname(source); local r = d and dirname(d); if r then table.insert(candidates, 1, join(join(r, "config"), "game_profile.ini")) end end
  for _, path in ipairs(candidates) do if exists(path) then return path end end
  local chosen = forms.openfile(nil, nil, "Perfil TopGear-RL (game_profile.ini)|game_profile.ini|Arquivos INI (*.ini)|*.ini")
  assert(chosen and chosen ~= "", "Selecao cancelada: escolha config/game_profile.ini")
  assert(chosen:match("game_profile%.ini$"), "Selecione exatamente config/game_profile.ini")
  return chosen
end
local profile_path = locate_profile()
local config_dir = assert(dirname(profile_path), "Caminho do perfil invalido")
local project_dir = assert(dirname(config_dir), "Pasta do projeto nao identificada")
local function trim(v) return (v:gsub("^%s+", ""):gsub("%s+$", "")) end

local function load_config(path)
  local file = assert(io.open(path, "r"), "Perfil config/game_profile.ini ausente")
  local result = {}
  for line in file:lines() do
    line = trim(line:gsub("\r", ""))
    if line ~= "" and line:sub(1, 1) ~= "#" and line:sub(1, 1) ~= ";" and line:sub(1, 1) ~= "[" then
      local key, value = line:match("^([%w_]+)%s*=%s*(.-)%s*$")
      if key then result[key] = value end
    end
  end
  file:close()
  return result
end

local cfg = load_config(profile_path)
local function num(key)
  local raw = assert(cfg[key], "Chave ausente: " .. key)
  if raw:match("^0[xX]") then return assert(tonumber(raw:sub(3), 16)) end
  return assert(tonumber(raw))
end
local function normalized_hash(raw)
  local value = tostring(raw or ""):upper()
  return value:match("([0-9A-F][0-9A-F]+)$") or value
end

assert(normalized_hash(gameinfo.getromhash()) == assert(cfg.rom_sha1):upper(), "ROM SHA-1 incorreto")
assert(memory.usememorydomain(assert(cfg.memory_domain)) == true, "Falha selecionando WRAM")

local addr = {
  speed=num("speed_address"), lateral=num("lateral_address"),
  progress_fraction=num("progress_fraction_address"), progress=num("progress_address"),
  lap=num("lap_address"), rank=num("rank_address"), final_rank=num("final_rank_address"),
  collision=num("collision_flags_address"), fuel=num("fuel_address"),
  nitro=num("nitro_address"), gear=num("gear_address"),
  total_laps=num("total_laps_address"), track_length=num("track_length_address")
}
local slot = num("savestate_slot")
local accelerate = assert(cfg.accelerate_button)
local brake = assert(cfg.brake_button)
assert(accelerate ~= "", "accelerate_button vazio")
assert(brake ~= "", "brake_button vazio")

local function s16(address)
  if memory.read_s16_le then return memory.read_s16_le(address) end
  local value = memory.read_u16_le(address)
  return value >= 0x8000 and value - 0x10000 or value
end
local function collision()
  return math.floor(memory.read_u16_le(addr.collision) / 0x80) % 2
end

local output_path = join(project_dir, "diagnostico_memoria.csv")
-- Preserva coletas anteriores em vez de sobrescrever o CSV/TXT.
local original_output_path, serial = output_path, 0
while exists(output_path) do
  serial = serial + 1
  output_path = original_output_path:gsub("(%.[^%.]+)$", "_" .. os.date("%Y%m%d_%H%M%S") .. "_" .. serial .. "%1")
end
local out = assert(io.open(output_path, "w"))
out:write("scenario,relative_frame,emu_frame,speed_s16,lateral_s16,progress_fraction,progress,lap_s16,rank,final_rank_s16,collision,fuel,nitro,gear,total_laps,track_length\n")

local function sample(scenario, relative_frame)
  out:write(string.format(
    "%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
    scenario, relative_frame, emu.framecount(), s16(addr.speed), s16(addr.lateral),
    memory.read_u8(addr.progress_fraction), memory.read_u16_le(addr.progress),
    s16(addr.lap), memory.read_u16_le(addr.rank), s16(addr.final_rank), collision(),
    memory.read_u16_le(addr.fuel), memory.read_u16_le(addr.nitro),
    memory.read_u16_le(addr.gear), memory.read_u16_le(addr.total_laps),
    memory.read_u16_le(addr.track_length)))
end

local function load_start()
  joypad.set({}, 1)
  assert(savestate.loadslot(slot, true) == true, "Falha carregando savestate slot " .. slot)
  for _ = 1, num("post_reset_frames") do
    joypad.set({}, 1)
    emu.frameadvance()
  end
end

local function record(scenario, buttons, frames)
  for frame = 0, frames - 1 do
    sample(scenario, frame)
    joypad.set(buttons, 1)
    emu.frameadvance()
  end
  sample(scenario, frames)
  joypad.set({}, 1)
end

console.log("DIAG memoria: candidato acelerar=" .. accelerate .. ", frear=" .. brake)

load_start()
record("neutral_80", {}, 80)

load_start()
record("accelerate_80", {[accelerate]=true}, 80)

load_start()
record("brake_prep_accelerate", {[accelerate]=true}, 60)
record("brake_after_accelerate", {[brake]=true}, 45)

load_start()
record("coast_prep_accelerate", {[accelerate]=true}, 60)
record("coast_after_accelerate", {}, 45)

load_start()
record("lateral_prep_straight", {[accelerate]=true}, 60)
record("lateral_neutral_branch", {[accelerate]=true}, 35)

load_start()
record("lateral_prep_left", {[accelerate]=true}, 60)
record("lateral_left_branch", {Left=true, [accelerate]=true}, 35)

load_start()
record("lateral_prep_right", {[accelerate]=true}, 60)
record("lateral_right_branch", {Right=true, [accelerate]=true}, 35)

out:close()
joypad.set({}, 1)
console.log("DIAG memoria concluido: " .. output_path)
console.log("Compare left/right com o ramo neutral de MESMA duracao.")
