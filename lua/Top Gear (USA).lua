-- TopGear-RL v3.0: ponte causal BizHawk <-> Python por TCP local.
-- Execute somente este script durante test_connection, smoke test, treino ou play.
local function run_bridge()

local source = debug.getinfo(1, "S").source or ""
if source:sub(1, 1) == "@" then source = source:sub(2) end
local separator = package.config:sub(1, 1)

local function join(a, b)
  return a .. separator .. b
end

local function dirname(path) return path:match("^(.*)[/\\][^/\\]+$") end
local function exists(path) local f = io.open(path, "r"); if f then f:close(); return true end; return false end
local function locate_profile()
  local override = rawget(_G, "TOPGEAR_PROFILE_OVERRIDE")
  _G.TOPGEAR_PROFILE_OVERRIDE = nil
  if override then assert(exists(override), "Perfil manual nao encontrado"); return override end
  local candidates = {join(".", "config" .. separator .. "game_profile.ini"), join("..", "config" .. separator .. "game_profile.ini")}
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
local native_navigation = dofile(join(join(project_dir, "lua"), "native_navigation.lua"))

local function trim(value)
  return (value:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function optional_metadata(fn)
  if not fn then return "unavailable" end
  local ok, value = pcall(fn)
  if not ok then return "unavailable" end
  return tostring(value):gsub("[|%c]", "_")
end

local function load_config(path)
  local file, err = io.open(path, "r")
  if not file then error("Nao foi possivel abrir o perfil: " .. tostring(err)) end
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

local config_path = profile_path
local cfg = load_config(config_path)
assert(tonumber(cfg.profile_version) == 3, "Selecione o perfil da v3.0")
local function adler32(text)
  local a, b = 1, 0
  for i=1,#text do a=(a+text:byte(i))%65521; b=(b+a)%65521 end
  return b*65536+a
end
local profile_file = assert(io.open(config_path, "rb"))
local profile_crc = adler32(profile_file:read("*a"):gsub("\r\n", "\n"))
profile_file:close()
local function neutral_buttons()
  return {A=false, B=false, X=false, Y=false, L=false, R=false,
    Left=false, Right=false, Up=false, Down=false, Start=false, Select=false}
end

local function required(key)
  local value = cfg[key]
  if value == nil then error("Chave ausente no perfil: " .. key) end
  return value
end

local function number(key)
  local value = required(key)
  local parsed
  if value:match("^0[xX][0-9A-Fa-f]+$") then
    parsed = tonumber(value:sub(3), 16)
  else
    parsed = tonumber(value)
  end
  if parsed == nil then error("Numero invalido no perfil: " .. key .. "=" .. value) end
  return parsed
end

local function boolean(key)
  local value = required(key):lower()
  if value == "true" or value == "yes" or value == "1" or value == "on" then return true end
  if value == "false" or value == "no" or value == "0" or value == "off" then return false end
  error("Booleano invalido no perfil: " .. key .. "=" .. value)
end

local protocol_version = number("protocol_version")
if protocol_version ~= 2 then error("Este Lua exige protocol_version=2") end

local expected_sha1 = required("rom_sha1"):upper()
local memory_domain = required("memory_domain")
local profile_validated = boolean("profile_validated")
local opponent_telemetry_validated = boolean("opponent_telemetry_validated")
local surface_telemetry_validated = boolean("surface_telemetry_validated")
local curve_telemetry_validated = boolean("curve_telemetry_validated")
local controls_validated = boolean("controls_validated")
local enable_turbo = boolean("enable_turbo")
local manual_mode = cfg.manual_transmission ~= nil and boolean("manual_transmission")
local blue_auto_expected = cfg.blue_auto_expected ~= nil and boolean("blue_auto_expected")
if manual_mode then
  assert(enable_turbo and required("accelerate_button")=="X" and required("brake_button")=="Y" and required("turbo_button")=="A", "Manual exige Type A")
  assert(number("savestate_slot")==2 and number("frame_repeat")==4, "Manual exige slot 2 / quatro frames")
end
if blue_auto_expected then
  assert(not manual_mode and number("savestate_slot")==3 and number("frame_repeat")==4, "Azul automatico exige slot 3 / quatro frames")
end

local function sanitize(value)
  return tostring(value):gsub("[|=\r\n]", "_")
end

local state_order = {
  "status", "episode", "ack", "frame", "reset_ok", "error",
  "protocol_version", "rom_hash", "rom_ok", "domain_ok", "domain_size",
  "bridge_revision", "profile_crc", "race_ended", "race_completed",
  "profile_validated", "opponent_telemetry_validated", "surface_telemetry_validated",
  "curve_telemetry_validated",
  "controls_validated", "load_events",
  "speed", "lateral", "progress_fraction", "progress", "lap", "rank",
  "final_rank", "finished", "collision", "collision_events", "offtrack",
  "surface_raw", "surface_unknown", "surface_state", "surface_direction", "fuel", "nitro",
  "nitro_raw", "turbo_active", "gear", "total_laps", "track_length",
  "curve_progress", "curve_current", "curve_ahead_512", "curve_ahead_1024",
  "curve_ahead_2048", "nearest_valid", "nearest_id",
  "nearest_distance", "nearest_lateral", "nearest_motion_raw",
  "lane_negative_distance", "lane_center_distance", "lane_positive_distance",
  "opponent_count", "detector_samples", "navigation_samples",
  "engine_gauge_raw", "manual_mode", "car_table_offset_raw", "upshift_mask_raw", "downshift_mask_raw"
}

local function publish_fields(fields)
  local parts = { "TGSTATE2" }
  for _, key in ipairs(state_order) do
    if fields[key] ~= nil then
      table.insert(parts, key .. "=" .. sanitize(fields[key]))
    end
  end
  local sent = comm.socketServerSend(table.concat(parts, "|"))
  if not sent or sent <= 0 then error("Falha enviando estado ao Python pelo socket") end
end

local function current_frame()
  if emu and emu.framecount then return emu.framecount() end
  return -1
end

local function normalize_hash(raw)
  local value = tostring(raw or ""):upper()
  return value:match("([0-9A-F][0-9A-F]+)$") or value
end

local rom_hash = normalize_hash(gameinfo and gameinfo.getromhash and gameinfo.getromhash() or "")
local rom_ok = rom_hash == expected_sha1

if not memory or not memory.usememorydomain then
  publish_fields({status="error", episode=0, ack=-1, frame=current_frame(), reset_ok=0,
    error="API memory indisponivel", protocol_version=2, rom_hash=rom_hash,
    rom_ok=rom_ok and 1 or 0, domain_ok=0})
  error("API memory indisponivel")
end

local selected = memory.usememorydomain(memory_domain)
local domain_ok = selected == true
local domain_size = memory.getcurrentmemorydomainsize and memory.getcurrentmemorydomainsize() or -1

if not rom_ok then
  publish_fields({status="error", episode=0, ack=-1, frame=current_frame(), reset_ok=0,
    error="ROM_SHA1_incorreto", protocol_version=2, rom_hash=rom_hash,
    rom_ok=0, domain_ok=domain_ok and 1 or 0, domain_size=domain_size})
  error("ROM incorreta. Esperado SHA-1 " .. expected_sha1 .. ", recebido " .. rom_hash)
end
if not domain_ok or domain_size ~= 131072 then
  publish_fields({status="error", episode=0, ack=-1, frame=current_frame(), reset_ok=0,
    error="dominio_WRAM_indisponivel", protocol_version=2, rom_hash=rom_hash,
    rom_ok=1, domain_ok=0, domain_size=domain_size})
  error("Nao foi possivel selecionar o dominio " .. memory_domain)
end

local function read_u8(address)
  local value = memory.read_u8(address)
  if value == nil then error(string.format("Falha lendo u8 em %04X", address)) end
  return value
end

local function read_u16(address)
  local value = memory.read_u16_le(address)
  if value == nil then error(string.format("Falha lendo u16 em %04X", address)) end
  return value
end

local function read_s16(address)
  if memory.read_s16_le then
    local value = memory.read_s16_le(address)
    if value == nil then error(string.format("Falha lendo s16 em %04X", address)) end
    return value
  end
  local value = read_u16(address)
  return value >= 0x8000 and value - 0x10000 or value
end

local function signed_u8(value)
  return value >= 0x80 and value - 0x100 or value
end

local addresses = {
  speed=number("speed_address"), lateral=number("lateral_address"),
  progress_fraction=number("progress_fraction_address"), progress=number("progress_address"),
  curve_progress=number("curve_progress_address"), curve_table=number("lateral_curve_table"),
  lap=number("lap_address"), rank=number("rank_address"), final_rank=number("final_rank_address"),
  collision=number("collision_flags_address"), surface=number("surface_state_address"),
  fuel=number("fuel_address"),
  nitro=number("nitro_address"), gear=number("gear_address"), total_laps=number("total_laps_address"),
  track_length=number("track_length_address"), table_base=number("racer_table_base")
}
local racer_stride = number("racer_record_stride")
local racer_count = number("racer_count")
local lateral_center = number("lateral_center")
local track_half_width = number("track_half_width")
local surface_left_value = number("surface_left_value")
local surface_road_value = number("surface_road_value")
local surface_right_value = number("surface_right_value")
local same_lane_half_width = number("same_lane_half_width")
local sensor_fraction = number("opponent_sensor_fraction")
local max_repeat_frames = number("max_repeat_frames")
local post_reset_frames = number("post_reset_frames")
local savestate_slot = number("savestate_slot")

local load_events = 0
if event and event.onloadstate then
  event.onloadstate(function() load_events = load_events + 1 end, "TopGearRL-v2-load")
end
if event and event.onexit then
  event.onexit(function()
    if joypad and joypad.set then joypad.set(neutral_buttons(), 1) end
    if client and client.pause then client.pause() end
  end,
    "TopGearRL-v2-neutralize")
end

local function collision_active(flags)
  return math.floor(flags / 0x80) % 2 == 1
end

-- 0x1E6C e um estado composto. Em repouso, os dois bits baixos guardam
-- as cargas restantes. Durante o impulso, o bit 15 fica ativo e a ROM ainda
-- preserva nos bits baixos a contagem anterior; nesse intervalo, uma carga ja
-- foi comprometida e precisa ser subtraida para obter o inventario disponivel.
local function decode_nitro(raw)
  local active = raw >= 0x8000
  local available = raw % 4
  if active and available > 0 then available = available - 1 end
  return available, active and 1 or 0
end

local function curve_at(position, ahead, track_length)
  if track_length <= 0 then return 0 end
  local wrapped = (position + ahead) % track_length
  -- A rotina da ROM faz (posicao >> 4) & 0xFFFE, equivalente a
  -- duas bytes por entrada e uma entrada a cada 32 unidades da pista.
  local offset = 2 * math.floor(wrapped / 32)
  return signed_u8(read_u8(addresses.curve_table + offset))
end

local collision_events_total = 0
local collision_level_previous = collision_active(read_u16(addresses.collision))
local last_surface_direction = 0

local function read_telemetry(collision_window_events)
  local speed = read_s16(addresses.speed)
  local lateral = read_s16(addresses.lateral)
  local progress_fraction = read_u8(addresses.progress_fraction)
  local progress = read_u16(addresses.progress)
  local lap = read_s16(addresses.lap)
  local rank_raw = read_u16(addresses.rank)
  local rank = rank_raw <= 19 and rank_raw or -1
  local final_rank_raw = read_s16(addresses.final_rank)
  local final_rank = final_rank_raw >= 0 and final_rank_raw <= 19 and final_rank_raw or -1
  local track_length = read_u16(addresses.track_length)
  local curve_progress = read_u16(addresses.curve_progress)
  local curve_current = curve_at(curve_progress, 0, track_length)
  local curve_ahead_512 = curve_at(curve_progress, 512, track_length)
  local curve_ahead_1024 = curve_at(curve_progress, 1024, track_length)
  local curve_ahead_2048 = curve_at(curve_progress, 2048, track_length)
  local nitro_raw = read_u16(addresses.nitro)
  local nitro_available, turbo_active = decode_nitro(nitro_raw)
  -- collision representa um evento observado durante a ultima janela de acao.
  -- collision_events e cumulativo e impede a perda de pulsos menores que frame_repeat.
  local collision = (collision_window_events or 0) > 0 and 1 or 0
  local surface_raw = read_u8(addresses.surface)
  local surface_state = surface_raw
  local surface_unknown = 0
  local surface_direction
  if surface_raw == surface_left_value then
    surface_direction = -1
    last_surface_direction = -1
  elseif surface_raw == surface_road_value then
    surface_direction = 0
    last_surface_direction = 0
  elseif surface_raw == surface_right_value then
    surface_direction = 1
    last_surface_direction = 1
  else
    -- O treino real observou 0xFF ao bater num cacto longe da pista. O valor
    -- bruto permanece publicado; para a rede, o estado continua offtrack e a
    -- direção vem do último lado conhecido ou, sem histórico, da lateral de P1.
    surface_unknown = 1
    if last_surface_direction ~= 0 then
      surface_direction = last_surface_direction
    elseif lateral < lateral_center then
      surface_direction = -1
    else
      surface_direction = 1
    end
    surface_state = surface_direction < 0 and surface_left_value or surface_right_value
  end
  local offtrack = surface_direction == 0 and 0 or 1

  local nearest_valid, nearest_id, nearest_distance = 0, -1, -1
  local nearest_lateral, nearest_motion_raw = 0, 0
  local lane_negative_distance, lane_center_distance, lane_positive_distance = -1, -1, -1
  local opponent_count = 0
  local sensor_range = math.max(1, math.floor(track_length * sensor_fraction))
  local seen_ids = {}

  if track_length > 0 and lap >= 0 then
    for index = 0, racer_count - 1 do
      local base = addresses.table_base + index * racer_stride
      local racer_id = read_u8(base) % 32
      if racer_id >= 2 and racer_id <= 19 then
        if final_rank < 0 and seen_ids[racer_id] then error("ID_adversario_duplicado_" .. racer_id) end
        seen_ids[racer_id] = true
        opponent_count = opponent_count + 1
        local racer_lateral = read_s16(base + 2)
        -- O acumulador fracionário começa em +6; a posição comparável com
        -- track_length é o u16 little-endian iniciado em +7.
        local racer_progress = read_u16(base + 7)
        -- A tabela conta a primeira volta como 1; a telemetria global de P1
        -- conta a mesma volta como 0.
        local racer_lap = signed_u8(read_u8(base + 9)) - 1
        -- Campo +10: movimento longitudinal candidato. A escala ainda não foi
        -- validada e, por isso, ele não é chamado de velocidade nem usado na rede.
        local racer_motion_raw = read_u16(base + 10)
        local forward = (racer_lap - lap) * track_length + (racer_progress - progress)
        if forward > 0 and forward <= sensor_range then
          local lateral_delta = racer_lateral - lateral
          if nearest_valid == 0 or forward < nearest_distance then
            nearest_valid, nearest_id, nearest_distance = 1, racer_id, forward
            nearest_lateral, nearest_motion_raw = lateral_delta, racer_motion_raw
          end
          if lateral_delta < -same_lane_half_width then
            if lane_negative_distance < 0 or forward < lane_negative_distance then
              lane_negative_distance = forward
            end
          elseif lateral_delta > same_lane_half_width then
            if lane_positive_distance < 0 or forward < lane_positive_distance then
              lane_positive_distance = forward
            end
          else
            if lane_center_distance < 0 or forward < lane_center_distance then
              lane_center_distance = forward
            end
          end
        end
      end
    end
  end
  if lap >= 0 and final_rank < 0 and opponent_count ~= 18 then
    error("Tabela_adversarios_incompleta_" .. opponent_count)
  end

  return {
    protocol_version=2, bridge_revision=manual_mode and 6 or 5, profile_crc=profile_crc,
    engine_gauge_raw=manual_mode and read_s16(0x1E5E) or nil,
    manual_mode=(manual_mode or blue_auto_expected) and (manual_mode and 1 or 0) or nil,
    car_table_offset_raw=(manual_mode or blue_auto_expected) and read_u16(0x1EE8) or nil,
    upshift_mask_raw=(manual_mode or blue_auto_expected) and read_u16(0x1F7A) or nil,
    downshift_mask_raw=(manual_mode or blue_auto_expected) and read_u16(0x1F7C) or nil,
    bizhawk_version=optional_metadata(client and client.getversion),
    system_id=optional_metadata(emu and emu.getsystemid),
    display_type=optional_metadata(emu and emu.getdisplaytype),
    lua_version=tostring(_VERSION),
    race_ended=final_rank >= 0 and 1 or 0,
    race_completed=(final_rank >= 0 and lap == read_u16(addresses.total_laps) and lap > 0) and 1 or 0,
    rom_hash=rom_hash, rom_ok=1, domain_ok=1, domain_size=domain_size,
    profile_validated=profile_validated and 1 or 0,
    opponent_telemetry_validated=opponent_telemetry_validated and 1 or 0,
    surface_telemetry_validated=surface_telemetry_validated and 1 or 0,
    curve_telemetry_validated=curve_telemetry_validated and 1 or 0,
    controls_validated=controls_validated and 1 or 0, load_events=load_events,
    speed=speed, lateral=lateral, progress_fraction=progress_fraction, progress=progress,
    lap=lap, rank=rank, final_rank=final_rank, finished=final_rank >= 0 and 1 or 0,
    collision=collision, collision_events=collision_events_total,
    offtrack=offtrack, surface_raw=surface_raw, surface_unknown=surface_unknown,
    surface_state=surface_state, surface_direction=surface_direction,
    fuel=read_u16(addresses.fuel),
    nitro=nitro_available, nitro_raw=nitro_raw, turbo_active=turbo_active,
    gear=read_u16(addresses.gear),
    total_laps=read_u16(addresses.total_laps), track_length=track_length,
    curve_progress=curve_progress, curve_current=curve_current,
    curve_ahead_512=curve_ahead_512, curve_ahead_1024=curve_ahead_1024,
    curve_ahead_2048=curve_ahead_2048,
    nearest_valid=nearest_valid, nearest_id=nearest_id, nearest_distance=nearest_distance,
    nearest_lateral=nearest_lateral, nearest_motion_raw=nearest_motion_raw,
    lane_negative_distance=lane_negative_distance, lane_center_distance=lane_center_distance,
    lane_positive_distance=lane_positive_distance, opponent_count=opponent_count
  }
end

local detector_history = {}
local navigation_history = {}

local function publish(episode, ack, status, reset_ok, error_message, collision_window_events)
  local fields = read_telemetry(collision_window_events)
  fields.detector_samples = table.concat(detector_history,";")
  fields.navigation_samples = table.concat(navigation_history,";")
  fields.status, fields.episode, fields.ack = status, episode, ack
  fields.frame, fields.reset_ok = current_frame(), reset_ok or 0
  if error_message then fields.error = error_message end
  publish_fields(fields)
end

local function parse_action(text)
  if #text > 4096 or text:find("||", 1, true) or text:sub(-1) == "|" or text:find("[%c]") then
    return nil, "formato_ou_tamanho_invalido"
  end
  local parts = {}
  for token in tostring(text):gmatch("[^|]+") do table.insert(parts, token) end
  if parts[1] ~= "TGACT2" then return nil, "prefixo_invalido" end
  local result = {}
  for index = 2, #parts do
    local key, value = parts[index]:match("^([^=]+)=(.*)$")
    if not key or result[key] ~= nil then return nil, "campo_invalido_ou_duplicado" end
    result[key] = value
  end
  for _, key in ipairs({"episode", "seq", "kind", "action", "frames"}) do
    if result[key] == nil then return nil, "campo_ausente_" .. key end
  end
  result.episode = tonumber(result.episode)
  result.seq = tonumber(result.seq)
  result.action = tonumber(result.action)
  result.frames = tonumber(result.frames)
  if not result.episode or not result.seq or not result.action or not result.frames then
    return nil, "campo_numerico_invalido"
  end
  for _, key in ipairs({"episode", "seq", "action", "frames"}) do
    local value = result[key]
    if value ~= value or value < 0 or value > 9007199254740991 or value % 1 ~= 0 then
      return nil, "inteiro_invalido_" .. key
    end
  end
  return result
end

local function receive_action()
  local text = comm.socketServerResponse()
  if not text or text == "" then return nil, "socket_encerrado_ou_timeout" end
  return parse_action(text)
end

local function set_button(buttons, name)
  if name and name ~= "" then buttons[name] = true end
end

local function buttons_for(action)
  local buttons = neutral_buttons()
  if manual_mode then
    if action < 0 or action >= 30 then error("acao_manual_fora_do_espaco") end
    local shift = math.floor(action / 10)
    if shift == 1 then buttons.R = true elseif shift == 2 then buttons.L = true end
    action = action % 10
  end
  local accelerate = required("accelerate_button")
  local brake = required("brake_button")
  local turbo = required("turbo_button")
  if action == 1 then set_button(buttons, accelerate)
  elseif action == 2 then set_button(buttons, brake)
  elseif action == 3 then set_button(buttons, "Left"); set_button(buttons, accelerate)
  elseif action == 4 then set_button(buttons, "Right"); set_button(buttons, accelerate)
  elseif action == 5 then set_button(buttons, "Left")
  elseif action == 6 then set_button(buttons, "Right")
  elseif action == 7 then set_button(buttons, "Left"); set_button(buttons, brake)
  elseif action == 8 then set_button(buttons, "Right"); set_button(buttons, brake)
  elseif action == 9 then
    if not enable_turbo or turbo == "" then error("turbo_nao_configurado") end
    local inventory, active = decode_nitro(read_u16(addresses.nitro))
    if inventory > 0 and active == 0 then set_button(buttons, turbo) end
    set_button(buttons, accelerate)
  elseif action ~= 0 then error("acao_fora_do_espaco") end
  return buttons
end

-- Amostras reais por frame, inclusive antes da primeira volta valida.
local function detector_capture()
  local values = {current_frame(), read_u16(addresses.progress), read_s16(addresses.lateral), read_u16(addresses.track_length)}
  local records, count = {}, 0
  for index=0,racer_count-1 do
    local base=addresses.table_base+index*racer_stride
    local id=read_u8(base)%32
    if id>=2 and id<=19 then
      if records[id] then error("detector_ID_duplicado") end
      records[id]={id,read_u16(base+7),read_s16(base+2)}; count=count+1
    end
  end
  if count~=18 then error("detector_tabela_incompleta") end
  for id=2,19 do for _,v in ipairs(records[id]) do values[#values+1]=v end end
  detector_history[#detector_history+1]=table.concat(values,",")
  while #detector_history>4 do table.remove(detector_history,1) end
  navigation_history[#navigation_history+1] = native_navigation.capture(
    current_frame(), read_u8, read_u16, read_s16)
  while #navigation_history>4 do table.remove(navigation_history,1) end
end

local function advance(buttons, frames, count_collision_events)
  local collision_window_events = 0
  for _ = 1, frames do
    joypad.set(buttons, 1)
    local target_frame = current_frame() + 1
    repeat
      -- Recomendacao da API client.unpause do BizHawk 2.11.1: para forcar
      -- continuacao, combine unpause com emu.yield (nao frameadvance).
      client.unpause()
      emu.yield()
    until current_frame() >= target_frame
    if current_frame() ~= target_frame then error("salto_de_frame_durante_acao") end
    local collision_level = collision_active(read_u16(addresses.collision))
    if count_collision_events and collision_level and not collision_level_previous then
      collision_events_total = collision_events_total + 1
      collision_window_events = collision_window_events + 1
    end
    collision_level_previous = collision_level
    detector_capture()
  end
  joypad.set(neutral_buttons(), 1)
  return collision_window_events
end

if not emu or not emu.yield then
  error("BizHawk sem emu.yield; protocolo causal indisponivel")
end
if not client or not client.pause or not client.unpause then
  error("BizHawk sem client.pause/unpause; protocolo causal indisponivel")
end
if not joypad or not joypad.set then
  error("BizHawk sem joypad.set; controle indisponivel")
end
if not comm or not comm.socketServerIsConnected or not comm.socketServerSend
    or not comm.socketServerResponse then
  error("BizHawk sem API comm.socket*; inicie-o com --socket-ip e --socket-port")
end
if not comm.socketServerIsConnected() then
  error("Socket indisponivel; reinicie o BizHawk com --socket-ip 127.0.0.1 --socket-port 55355")
end
-- A recepcao bloqueante do socket segura o loop principal entre comandos.
-- O emulador precisa estar despausado para produzir os frames solicitados por
-- advance(); o socket bloqueia o loop principal entre comandos.
client.unpause()
console.log("TopGear-RL v3.0 iniciado; perfil: " .. config_path)
console.log("ROM SHA-1: " .. rom_hash)
console.log("Dominio: " .. memory_domain .. " / tamanho: " .. tostring(domain_size))
console.log("Perfil validado: " .. tostring(profile_validated))
console.log("Adversarios validados: " .. tostring(opponent_telemetry_validated))
console.log("Superficie validada: " .. tostring(surface_telemetry_validated))
console.log("Curvas de Las Vegas validadas: " .. tostring(curve_telemetry_validated))
console.log("Transporte: TCP local; aguardando HELLO do Python")

local startup_command, startup_error = receive_action()
if not startup_command then error("Falha no HELLO: " .. tostring(startup_error)) end
if startup_command.kind ~= "hello" or startup_command.frames ~= 0 then
  error("Primeiro comando deve ser HELLO com frames=0")
end

local last_seq = startup_command.seq
local current_episode = startup_command.episode
local first_step = true
local function validate_track()
  local length = read_u16(addresses.track_length)
  if length ~= number("track_length_expected") then error("pista_comprimento_incompativel") end
  local bytes = {}
  for index=0,math.ceil(length/32)-1 do
    bytes[#bytes+1] = string.char(read_u8(addresses.curve_table + 2*index))
  end
  if adler32(table.concat(bytes)) ~= number("curve_table_adler32") then
    error("tabela_curva_diferente_de_Las_Vegas_validada")
  end
end
-- A identidade da pista e verificada no reset. HELLO pode ocorrer nos menus.
publish(current_episode, last_seq, "ready", 0)
console.log("HELLO confirmado; ponte pronta")

while true do
  local command, parse_error = receive_action()
  if not command then
    joypad.set(neutral_buttons(), 1)
    client.pause()
    error("Conexao Python encerrada: " .. tostring(parse_error))
  end
  if command then
    local should_close = command.kind == "close"
    local ok, error_message = pcall(function()
      if command.seq <= last_seq then error("sequencia_repetida_ou_regressiva") end
      local expected_episode = command.kind == "reset" and current_episode + 1 or current_episode
      if command.episode ~= expected_episode then error("episodio_fora_de_sequencia") end
      if command.kind ~= "step" and (command.frames ~= 0 or command.action ~= 0) then
        error("reset_close_exigem_frames_e_action_zero")
      end
      current_episode = command.episode
      if command.kind == "reset" then
        local loaded = savestate and savestate.loadslot and savestate.loadslot(savestate_slot, true)
        if loaded ~= true then error("falha_carregando_savestate_slot_" .. savestate_slot) end
        assert(memory.usememorydomain(memory_domain) == true, "WRAM perdida apos reset")
        collision_events_total = 0
        last_surface_direction = 0
        collision_level_previous = collision_active(read_u16(addresses.collision))
        detector_history = {}
        navigation_history = {}
        detector_capture()
        advance(neutral_buttons(), post_reset_frames, false)
        validate_track()
        publish(current_episode, command.seq, "ok", 1)
      elseif command.kind == "step" then
        if command.frames < 1 or command.frames > max_repeat_frames then
          error("frames_fora_do_intervalo")
        end
        if first_step then
          console.log("Primeiro STEP recebido: " .. tostring(command.frames) .. " frames")
        end
        local collision_window_events = advance(buttons_for(command.action), command.frames, true)
        publish(current_episode, command.seq, "ok", 0, nil, collision_window_events)
        if first_step then
          console.log("Primeiro STEP concluido no frame " .. tostring(current_frame()))
          first_step = false
        end
      elseif command.kind == "close" then
        joypad.set(neutral_buttons(), 1)
        client.pause()
        publish(current_episode, command.seq, "closed", 0)
      else
        error("kind_desconhecido")
      end
    end)
    last_seq = command.seq
    if not ok then
      joypad.set(neutral_buttons(), 1)
      client.pause()
      local safe_error = sanitize(error_message)
      console.log("TopGear-RL erro no comando: " .. safe_error)
      local fields = {
        status="error", episode=command.episode, ack=command.seq, frame=current_frame(),
        reset_ok=0, error=safe_error, protocol_version=2, rom_hash=rom_hash,
        rom_ok=1, domain_ok=1, domain_size=domain_size,
        profile_validated=profile_validated and 1 or 0,
        opponent_telemetry_validated=opponent_telemetry_validated and 1 or 0,
        surface_telemetry_validated=surface_telemetry_validated and 1 or 0,
        curve_telemetry_validated=curve_telemetry_validated and 1 or 0,
        controls_validated=controls_validated and 1 or 0
      }
      publish_fields(fields)
      break -- nao aceite novos comandos sobre uma transicao parcial/ambigua
    end
    if should_close then
      console.log("Ponte encerrada pelo Python")
      break
    end
  else
    joypad.set({}, 1)
    error("Sequencia repetida ou regressiva recebida")
  end
end
end -- run_bridge

local ok, failure = pcall(run_bridge)
if not ok then
  pcall(function() joypad.set({A=false,B=false,X=false,Y=false,L=false,R=false,
    Left=false,Right=false,Up=false,Down=false,Start=false,Select=false}, 1) end)
  pcall(function() client.pause() end)
  local message = tostring(failure):gsub("[|=\r\n]", "_")
  pcall(function() comm.socketServerSend("TGSTATE2|status=error|episode=0|ack=-1|frame=" ..
    tostring(emu.framecount()) .. "|reset_ok=0|error=" .. message) end)
  console.log("TopGear-RL v3 erro: " .. message)
end
