-- Diagnostico 4/4: pista, impactos e adversario mais proximo.
-- Dirija manualmente; nao execute outro script Lua ao mesmo tempo.

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

local file = assert(io.open(profile_path, "r"))
local cfg = {}
for line in file:lines() do
  line = trim(line:gsub("\r", ""))
  if line ~= "" and line:sub(1, 1) ~= "#" and line:sub(1, 1) ~= ";" and line:sub(1, 1) ~= "[" then
    local key, value = line:match("^([%w_]+)%s*=%s*(.-)%s*$")
    if key then cfg[key] = value end
  end
end
file:close()

local function num(key)
  local raw = assert(cfg[key], "Chave ausente: " .. key)
  if raw:match("^0[xX]") then return assert(tonumber(raw:sub(3), 16)) end
  return assert(tonumber(raw))
end
local function hash(raw)
  local value = tostring(raw or ""):upper()
  return value:match("([0-9A-F][0-9A-F]+)$") or value
end
local function signed_u8(value) return value >= 0x80 and value - 0x100 or value end
local function safe_u8(address, size)
  if address < 0 or address >= size then return -999 end
  return memory.read_u8(address)
end
local function safe_u16(address, size)
  if address < 0 or address + 1 >= size then return -999 end
  return memory.read_u16_le(address)
end
local function safe_s16(address, size)
  local value = safe_u16(address, size)
  if value == -999 then return value end
  return value >= 0x8000 and value - 0x10000 or value
end
local function track_values(table_a, table_b, progress, track_length, size)
  local wrapped = progress % track_length
  -- A ROM faz quatro LSR e AND #$FFFE antes de acessar $7E4000/$7E7002.
  local track_index = math.floor(wrapped / 16)
  local offset = 2 * track_index
  local curve = safe_s16(table_a + offset, size)
  local bounds_word = safe_u16(table_b + offset, size)
  if bounds_word == -999 then return track_index, offset, curve, -999, -999, -999, -999, -999, -999 end
  local low_byte = signed_u8(bounds_word % 256)
  local high_byte = signed_u8(math.floor(bounds_word / 256) % 256)
  -- A ROM compara esses bytes assinados escalados com a coordenada lateral/2.
  -- Na escala original de lateral, cada unidade do byte equivale a 256.
  local bound_a = low_byte * 256
  local bound_b = high_byte * 256
  local lower = math.min(bound_a, bound_b)
  local upper = math.max(bound_a, bound_b)
  return track_index, offset, curve, low_byte, high_byte, lower, upper,
    math.floor((lower + upper) / 2), math.floor((upper - lower) / 2)
end
local function indexed_s16(table_base, progress, track_length, size)
  local offset = 2 * math.floor((progress % track_length) / 16)
  return safe_s16(table_base + offset, size)
end
local function indexed_u16(table_base, progress, track_length, size)
  local offset = 2 * math.floor((progress % track_length) / 16)
  return safe_u16(table_base + offset, size)
end

assert(hash(gameinfo.getromhash()) == assert(cfg.rom_sha1):upper(), "ROM SHA-1 incorreto")
assert(memory.usememorydomain(assert(cfg.memory_domain)) == true, "Falha selecionando WRAM")
local size = memory.getcurrentmemorydomainsize()
local speed_addr = num("speed_address")
local progress_addr = num("progress_address")
local lateral_addr = num("lateral_address")
local lap_addr = num("lap_address")
local rank_addr = num("rank_address")
local final_rank_addr = num("final_rank_address")
local total_laps_addr = num("total_laps_address")
local collision_addr = num("collision_flags_address")
local track_length = memory.read_u16_le(num("track_length_address"))
assert(track_length > 0, "Comprimento de pista invalido")
local table_a = num("geometry_table_a")
local table_b = num("geometry_table_b")
local lateral_curve_table = num("lateral_curve_table")
local road_type_table = num("road_type_table")
local racer_base = num("racer_table_base")
local racer_stride = num("racer_record_stride")
local racer_count = num("racer_count")
local sensor_range = math.max(1, math.floor(track_length * tonumber(assert(cfg.opponent_sensor_fraction))))
local same_lane_half_width = num("same_lane_half_width")
local output_path = join(project_dir, "diagnostico_pista.csv")
-- Preserva coletas anteriores em vez de sobrescrever o CSV/TXT.
local original_output_path, serial = output_path, 0
while exists(output_path) do
  serial = serial + 1
  output_path = original_output_path:gsub("(%.[^%.]+)$", "_" .. os.date("%Y%m%d_%H%M%S") .. "_" .. serial .. "%1")
end
local out = assert(io.open(output_path, "w"))
out:write("sample,emu_frame,speed,lateral,progress,progress_fraction,lap_s16,rank_u16,final_rank_s16,total_laps,finished_candidate,collision_flags,collision_level,collision_edge,input_left,input_right,input_accelerate,input_brake,track_index,track_offset,grade_s16,lateral_curve_s16,road_type_raw,road_low_byte_s8,road_high_byte_s8,road_lower_lateral,road_upper_lateral,road_center_lateral,road_half_width,road_inside_candidate,grade_lookahead64_s16,lateral_curve_lookahead64_s16,road_type_lookahead64_raw,road_lower_lookahead64,road_upper_lookahead64,grade_lookahead256_s16,lateral_curve_lookahead256_s16,road_type_lookahead256_raw,road_lower_lookahead256,road_upper_lookahead256,opponent_count,nearest_valid,nearest_id,nearest_forward,nearest_lateral_delta,nearest_motion_raw,nearest_same_lane_candidate,nearest_any_valid,nearest_any_id,nearest_any_signed_forward,nearest_any_lateral_delta,nearest_any_motion_raw\n")

local previous_collision_level = math.floor(memory.read_u16_le(collision_addr) / 0x80) % 2
console.log("DIAG pista v4: dirija ate terminar a corrida (5400 frames, ~90 s).")
for sample = 0, 5399 do
  local progress = memory.read_u16_le(progress_addr)
  local speed = safe_s16(speed_addr, size)
  local lateral = safe_s16(lateral_addr, size)
  local lap = safe_s16(lap_addr, size)
  local rank = safe_u16(rank_addr, size)
  local final_rank = safe_s16(final_rank_addr, size)
  local total_laps = safe_u16(total_laps_addr, size)
  local finished = final_rank >= 0 and final_rank < racer_count and 1 or 0
  local collision_flags = safe_u16(collision_addr, size)
  local collision_level = math.floor(collision_flags / 0x80) % 2
  local collision_edge = collision_level == 1 and previous_collision_level == 0 and 1 or 0
  previous_collision_level = collision_level
  local buttons = joypad.getimmediate and joypad.getimmediate(1) or joypad.get(1)
  local input_left = buttons.Left and 1 or 0
  local input_right = buttons.Right and 1 or 0
  local input_accelerate = buttons[assert(cfg.accelerate_button)] and 1 or 0
  local input_brake = buttons[assert(cfg.brake_button)] and 1 or 0

  local track_index, track_offset, grade, low_byte, high_byte, lower, upper, center, half_width =
    track_values(table_a, table_b, progress, track_length, size)
  local lateral_curve = indexed_s16(lateral_curve_table, progress, track_length, size)
  local road_type = indexed_u16(road_type_table, progress, track_length, size)
  local _, _, grade64, _, _, lower64, upper64 =
    track_values(table_a, table_b, progress + 64, track_length, size)
  local lateral_curve64 = indexed_s16(lateral_curve_table, progress + 64, track_length, size)
  local road_type64 = indexed_u16(road_type_table, progress + 64, track_length, size)
  local _, _, grade256, _, _, lower256, upper256 =
    track_values(table_a, table_b, progress + 256, track_length, size)
  local lateral_curve256 = indexed_s16(lateral_curve_table, progress + 256, track_length, size)
  local road_type256 = indexed_u16(road_type_table, progress + 256, track_length, size)
  local inside = lower ~= -999 and lateral >= lower and lateral < upper and 1 or 0

  local opponent_count = 0
  local nearest_valid, nearest_id, nearest_forward = 0, -1, -1
  local nearest_lateral_delta, nearest_motion_raw, nearest_same_lane = 0, 0, 0
  local nearest_any_valid, nearest_any_id, nearest_any_forward = 0, -1, 0
  local nearest_any_lateral_delta, nearest_any_motion_raw = 0, 0
  if lap >= 0 then
    for index = 0, racer_count - 1 do
      local base = racer_base + index * racer_stride
      local racer_id = safe_u8(base, size) % 32
      if racer_id >= 2 and racer_id <= 19 then
        opponent_count = opponent_count + 1
        local racer_progress = safe_u16(base + 7, size)
        local racer_lap = signed_u8(safe_u8(base + 9, size)) - 1
        local forward = (racer_lap - lap) * track_length + racer_progress - progress
        if math.abs(forward) <= sensor_range and
            (nearest_any_valid == 0 or math.abs(forward) < math.abs(nearest_any_forward)) then
          local racer_lateral = safe_s16(base + 2, size)
          nearest_any_valid, nearest_any_id, nearest_any_forward = 1, racer_id, forward
          nearest_any_lateral_delta = racer_lateral - lateral
          nearest_any_motion_raw = safe_u16(base + 10, size)
        end
        if forward > 0 and forward <= sensor_range and (nearest_valid == 0 or forward < nearest_forward) then
          local racer_lateral = safe_s16(base + 2, size)
          nearest_valid, nearest_id, nearest_forward = 1, racer_id, forward
          nearest_lateral_delta = racer_lateral - lateral
          nearest_motion_raw = safe_u16(base + 10, size)
          nearest_same_lane = math.abs(nearest_lateral_delta) <= same_lane_half_width and 1 or 0
        end
      end
    end
  end

  out:write(string.format(
    "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
    sample, emu.framecount(), speed, lateral, progress, progress % 256, lap, rank,
    final_rank, total_laps, finished,
    collision_flags, collision_level, collision_edge,
    input_left, input_right, input_accelerate, input_brake,
    track_index, track_offset, grade, lateral_curve, road_type,
    low_byte, high_byte, lower, upper, center,
    half_width, inside, grade64, lateral_curve64, road_type64, lower64, upper64,
    grade256, lateral_curve256, road_type256, lower256, upper256,
    opponent_count, nearest_valid, nearest_id, nearest_forward,
    nearest_lateral_delta, nearest_motion_raw, nearest_same_lane,
    nearest_any_valid, nearest_any_id, nearest_any_forward,
    nearest_any_lateral_delta, nearest_any_motion_raw))
  if gui and gui.text then
    gui.text(4, 4, string.format("PISTA v4 | lap=%d rank=%d final=%d pos=%d", lap, rank, final_rank, progress))
    gui.text(4, 18, string.format("grade=%d curve=%d type=%04X", grade, lateral_curve, road_type))
    gui.text(4, 32, string.format("near=%d id=%d d=%d lane=%d hit=%d", nearest_valid, nearest_id, nearest_forward, nearest_same_lane, collision_edge))
  end
  if sample % 60 == 0 then out:flush() end
  emu.frameadvance()
end
out:close()
console.log("DIAG pista v4 concluido: " .. output_path)
