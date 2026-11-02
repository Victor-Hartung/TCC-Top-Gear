-- Diagnostico 5/5: compara aceleracao com e sem o botao logico de turbo.
-- Salve o slot configurado durante a corrida, com pelo menos um nitro disponivel.
-- Nao pressione teclas e nao execute outro script Lua durante este teste.

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
local cfg = {}
local profile = assert(io.open(profile_path, "r"))
for line in profile:lines() do
  line = trim(line:gsub("\r", ""))
  if line ~= "" and line:sub(1, 1) ~= "#" and line:sub(1, 1) ~= ";" and line:sub(1, 1) ~= "[" then
    local key, value = line:match("^([%w_]+)%s*=%s*(.-)%s*$")
    if key then cfg[key] = value end
  end
end
profile:close()

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

assert(hash(gameinfo.getromhash()) == assert(cfg.rom_sha1):upper(), "ROM SHA-1 incorreto")
assert(memory.usememorydomain(assert(cfg.memory_domain)) == true, "Falha selecionando WRAM")

local accelerate = assert(cfg.accelerate_button)
local turbo = assert(cfg.turbo_button)
assert(accelerate ~= "", "accelerate_button vazio")
assert(turbo ~= "", "turbo_button vazio")
assert(accelerate ~= turbo, "Acelerar e turbo nao podem usar o mesmo botao logico")

local address = {
  speed = num("speed_address"),
  progress = num("progress_address"),
  lap = num("lap_address"),
  rank = num("rank_address"),
  nitro = num("nitro_address"),
  fuel = num("fuel_address"),
  gear = num("gear_address"),
  collision = num("collision_flags_address")
}
local slot = num("savestate_slot")
local reset_frames = num("post_reset_frames")
local output_path = join(project_dir, "diagnostico_turbo.csv")
-- Preserva coletas anteriores em vez de sobrescrever o CSV/TXT.
local original_output_path, serial = output_path, 0
while exists(output_path) do
  serial = serial + 1
  output_path = original_output_path:gsub("(%.[^%.]+)$", "_" .. os.date("%Y%m%d_%H%M%S") .. "_" .. serial .. "%1")
end
local out = assert(io.open(output_path, "w"))
out:write("scenario,relative_frame,emu_frame,input_accelerate,input_turbo,speed_s16,progress,lap_s16,rank_u16,nitro_u16,nitro_s16,nitro_low_u8,nitro_high_u8,nitro_low2,nitro_available_candidate,turbo_active_candidate,fuel_u16,gear_u16,collision_flags\n")

local function load_start()
  joypad.set({}, 1)
  assert(savestate.loadslot(slot, true) == true, "Falha carregando savestate slot " .. slot)
  for _ = 1, reset_frames do
    joypad.set({}, 1)
    emu.frameadvance()
  end
  assert(memory.read_u16_le(address.nitro) > 0,
    "O savestate precisa ter pelo menos um nitro disponivel em 0x1E6C")
end

local function sample(scenario, frame, accelerate_pressed, turbo_pressed)
  local nitro_raw = memory.read_u16_le(address.nitro)
  local nitro_active = nitro_raw >= 0x8000
  local nitro_low2 = nitro_raw % 4
  -- A rotina da ROM exibe um nitro a menos enquanto o temporizador negativo
  -- esta ativo. Isto ainda e candidato ate observar o retorno ao estado positivo.
  local nitro_available = nitro_low2
  if nitro_active and nitro_available > 0 then nitro_available = nitro_available - 1 end
  out:write(string.format(
    "%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
    scenario, frame, emu.framecount(), accelerate_pressed and 1 or 0,
    turbo_pressed and 1 or 0, s16(address.speed),
    memory.read_u16_le(address.progress), s16(address.lap),
    memory.read_u16_le(address.rank), nitro_raw,
    nitro_raw >= 0x8000 and nitro_raw - 0x10000 or nitro_raw,
    nitro_raw % 256, math.floor(nitro_raw / 256), nitro_low2,
    nitro_available, nitro_active and 1 or 0,
    memory.read_u16_le(address.fuel), memory.read_u16_le(address.gear),
    memory.read_u16_le(address.collision)))
end

local function branch(scenario, use_turbo)
  load_start()
  local initial_nitro = memory.read_u16_le(address.nitro)
  for frame = 0, 519 do
    -- O pulso ocorre depois da largada observada no primeiro teste. Os dois
    -- ramos continuam identicos em todos os outros frames.
    local turbo_pressed = use_turbo and frame >= 160 and frame < 164
    local buttons = {[accelerate] = true}
    if turbo_pressed then buttons[turbo] = true end
    sample(scenario, frame, true, turbo_pressed)
    joypad.set(buttons, 1)
    if gui and gui.text then
      gui.text(4, 4, string.format("TURBO | %s | frame=%d", scenario, frame))
      gui.text(4, 18, string.format("button=%s nitro=%d speed=%d",
        turbo, memory.read_u16_le(address.nitro), s16(address.speed)))
    end
    emu.frameadvance()
  end
  sample(scenario, 520, false, false)
  joypad.set({}, 1)
  return initial_nitro, memory.read_u16_le(address.nitro)
end

console.log("DIAG turbo: tecla fisica X corresponde ao botao SNES " .. turbo)
local baseline_start, baseline_end = branch("accelerate_only", false)
local turbo_start, turbo_end = branch("accelerate_plus_A", true)
out:close()
joypad.set({}, 1)
console.log(string.format("Sem turbo: nitro %d -> %d", baseline_start, baseline_end))
console.log(string.format("Com botao %s: nitro %d -> %d", turbo, turbo_start, turbo_end))
console.log("DIAG turbo concluido: " .. output_path)
