-- Diagnostico 3/4: registra os 20 registros por 900 frames (~15 s a 60 fps).
-- Entre em uma corrida, pare os outros scripts e dirija manualmente durante o teste.

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
local function hash(raw)
  local value = tostring(raw or ""):upper()
  return value:match("([0-9A-F][0-9A-F]+)$") or value
end
local function s16(address)
  if memory.read_s16_le then return memory.read_s16_le(address) end
  local value = memory.read_u16_le(address)
  return value >= 0x8000 and value - 0x10000 or value
end
local function s8(value) return value >= 0x80 and value - 0x100 or value end

assert(hash(gameinfo.getromhash()) == assert(cfg.rom_sha1):upper(), "ROM SHA-1 incorreto")
assert(memory.usememorydomain(assert(cfg.memory_domain)) == true, "Falha selecionando WRAM")

local player_lateral_addr = num("lateral_address")
local player_speed_addr = num("speed_address")
local player_progress_addr = num("progress_address")
local player_lap_addr = num("lap_address")
local rank_addr = num("rank_address")
local collision_addr = num("collision_flags_address")
local track_length_addr = num("track_length_address")
local base = num("racer_table_base")
local stride = num("racer_record_stride")
local count = num("racer_count")
local diagnostic_frames = 900
local output_path = join(project_dir, "diagnostico_adversarios.csv")
-- Preserva coletas anteriores em vez de sobrescrever o CSV/TXT.
local original_output_path, serial = output_path, 0
while exists(output_path) do
  serial = serial + 1
  output_path = original_output_path:gsub("(%.[^%.]+)$", "_" .. os.date("%Y%m%d_%H%M%S") .. "_" .. serial .. "%1")
end
local out = assert(io.open(output_path, "w"))
out:write("sample,emu_frame,player_speed,player_lateral,player_progress,player_lap,player_rank,collision_flags,track_length,record_index,record_base,id,raw_id_flags,lateral,lateral_velocity,progress_fraction,subprogress_u16,progress,lap_raw,lap,longitudinal_motion_raw,acceleration_raw,update_timer,status_flags,delta_forward,delta_lateral\n")

console.log("DIAG adversarios: dirija e crie situacoes perto/longe/esquerda/direita.")

for sample_index = 0, diagnostic_frames - 1 do
  local frame = emu.framecount()
  local player_speed = s16(player_speed_addr)
  local player_lateral = s16(player_lateral_addr)
  local player_progress = memory.read_u16_le(player_progress_addr)
  local player_lap = s16(player_lap_addr)
  local player_rank = memory.read_u16_le(rank_addr)
  local collision_flags = memory.read_u16_le(collision_addr)
  local track_length = memory.read_u16_le(track_length_addr)
  local nearest_id, nearest_distance, nearest_lateral = -1, -1, 0

  for index = 0, count - 1 do
    local record = base + index * stride
    local raw_id = memory.read_u8(record)
    local racer_id = raw_id % 32
    local lateral = s16(record + 2)
    local lateral_velocity = s16(record + 4)
    local progress_fraction = memory.read_u8(record + 6)
    local subprogress = memory.read_u16_le(record + 6)
    -- O registro 0 acompanhou P1: byte +7 == byte baixo do progresso de P1
    -- em 900/900 frames. A posição longitudinal começa em +7.
    local progress = memory.read_u16_le(record + 7)
    local lap_raw = s8(memory.read_u8(record + 9))
    local lap = lap_raw - 1
    local longitudinal_motion = memory.read_u16_le(record + 10)
    local acceleration = s16(record + 12)
    local timer = memory.read_u16_le(record + 14)
    local status = memory.read_u16_le(record + 16)
    local delta_forward = 0
    if track_length > 0 and player_lap >= 0 then
      delta_forward = (lap - player_lap) * track_length + (progress - player_progress)
    end
    local delta_lateral = lateral - player_lateral
    if racer_id >= 2 and racer_id <= 19 and delta_forward > 0 then
      if nearest_distance < 0 or delta_forward < nearest_distance then
        nearest_id, nearest_distance, nearest_lateral = racer_id, delta_forward, delta_lateral
      end
    end
    out:write(string.format(
      "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,0x%04X,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
      sample_index, frame, player_speed, player_lateral, player_progress, player_lap,
      player_rank, collision_flags, track_length, index, record, racer_id, raw_id,
      lateral, lateral_velocity, progress_fraction, subprogress, progress, lap_raw, lap,
      longitudinal_motion, acceleration, timer, status, delta_forward, delta_lateral))
  end

  if gui and gui.text then
    gui.text(4, 4, string.format("RL DIAG | rank=%d lap=%d pos=%d lat=%d",
      player_rank, player_lap, player_progress, player_lateral))
    gui.text(4, 18, string.format("nearest id=%d dist=%d dlat=%d flags=%04X",
      nearest_id, nearest_distance, nearest_lateral, collision_flags))
  end
  if sample_index % 60 == 0 then out:flush() end
  emu.frameadvance()
end

out:close()
console.log("DIAG adversarios concluido: " .. output_path)
