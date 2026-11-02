-- Validacao causal dos candidatos de superficie 0x0727 e 0x0A67.
-- Execute sozinho durante uma corrida e atravesse as duas bordas repetidamente.

local source = debug.getinfo(1, "S").source or ""
if source:sub(1, 1) == "@" then source = source:sub(2) end
local sep = package.config:sub(1, 1)
local function join(a, b) return a .. sep .. b end
local function dirname(path) return path:match("^(.*)[/\\][^/\\]+$") end
local function exists(path)
  local file = io.open(path, "r")
  if file then file:close(); return true end
  return false
end
local function locate_profile()
  local candidates = {
    join(".", "config" .. sep .. "game_profile.ini"),
    join("..", "config" .. sep .. "game_profile.ini"),
  }
  if source ~= "" and source:sub(1, 1) ~= "[" then
    local lua_dir = dirname(source)
    local root = lua_dir and dirname(lua_dir)
    if root then table.insert(candidates, 1, join(join(root, "config"), "game_profile.ini")) end
  end
  for _, path in ipairs(candidates) do
    if exists(path) then return path end
  end
  local chosen = forms.openfile(
    nil, nil,
    "Perfil TopGear-RL (game_profile.ini)|game_profile.ini|Arquivos INI (*.ini)|*.ini")
  assert(chosen and chosen ~= "", "Selecao cancelada: escolha config/game_profile.ini")
  assert(chosen:match("game_profile%.ini$"), "Selecione exatamente config/game_profile.ini")
  return chosen
end

local profile_path = locate_profile()
local config_dir = assert(dirname(profile_path), "Caminho do perfil invalido")
local project_dir = assert(dirname(config_dir), "Pasta do projeto nao identificada")
local function trim(value) return (value:gsub("^%s+", ""):gsub("%s+$", "")) end
local profile = assert(io.open(profile_path, "r"))
local cfg = {}
for line in profile:lines() do
  line = trim(line:gsub("\r", ""))
  if line ~= "" and line:sub(1, 1) ~= "#" and line:sub(1, 1) ~= ";" and
      line:sub(1, 1) ~= "[" then
    local key, value = line:match("^([%w_]+)%s*=%s*(.-)%s*$")
    if key then cfg[key] = value end
  end
end
profile:close()

local function number(key)
  local raw = assert(cfg[key], "Chave ausente: " .. key)
  if raw:match("^0[xX]") then return assert(tonumber(raw:sub(3), 16)) end
  return assert(tonumber(raw))
end
local function hash(raw)
  local value = tostring(raw or ""):upper()
  return value:match("([0-9A-F][0-9A-F]+)$") or value
end
local function signed_u16(value)
  return value >= 0x8000 and value - 0x10000 or value
end
local function surface_name(value)
  if value == 0 then return "FORA ESQUERDA" end
  if value == 1 then return "PISTA" end
  if value == 2 then return "FORA DIREITA" end
  return "DESCONHECIDO"
end

assert(hash(gameinfo.getromhash()) == assert(cfg.rom_sha1):upper(), "ROM SHA-1 incorreto")
assert(memory.usememorydomain(assert(cfg.memory_domain)) == true, "Falha selecionando WRAM")
assert(memory.getcurrentmemorydomainsize() >= 0x2000, "WRAM menor que a faixa esperada")

local speed_addr = number("speed_address")
local lateral_addr = number("lateral_address")
local progress_addr = number("progress_address")
local lap_addr = number("lap_address")
local rank_addr = number("rank_address")
local collision_addr = number("collision_flags_address")
local first_base = 0x0717
local second_base = 0x0A57
local center_index = 4
local output_path = join(project_dir, "diagnostico_superficie.csv")
-- Preserva coletas anteriores em vez de sobrescrever o CSV/TXT.
local original_output_path, serial = output_path, 0
while exists(output_path) do
  serial = serial + 1
  output_path = original_output_path:gsub("(%.[^%.]+)$", "_" .. os.date("%Y%m%d_%H%M%S") .. "_" .. serial .. "%1")
end
local output = assert(io.open(output_path, "w"))
output:write(
  "sample,emu_frame,speed,lateral,progress,lap,rank,collision_flags," ..
  "input_left,input_right,input_accelerate,surface_0727,surface_0A67," ..
  "mirror_equal,a0,a1,a2,a3,a4,a5,a6,b0,b1,b2,b3,b4,b5,b6\n")

local previous = memory.read_u8(first_base + center_index * 4)
local transition_count = 0
console.log("DIAG superficie iniciado: 3600 frames (~60 s).")
console.log("Atravesse: pista -> esquerda -> pista -> direita -> pista, pelo menos 3 vezes.")
console.log("Confirme visualmente se o texto na tela muda exatamente nas bordas.")

for sample = 0, 3599 do
  local frame = emu.framecount()
  local speed = signed_u16(memory.read_u16_le(speed_addr))
  local lateral = signed_u16(memory.read_u16_le(lateral_addr))
  local progress = memory.read_u16_le(progress_addr)
  local lap = signed_u16(memory.read_u16_le(lap_addr))
  local rank = memory.read_u16_le(rank_addr)
  local collision = memory.read_u16_le(collision_addr)
  local buttons = joypad.getimmediate and joypad.getimmediate(1) or joypad.get(1)
  local first, second = {}, {}
  local mirror_equal = 1
  for index = 0, 6 do
    first[index + 1] = memory.read_u8(first_base + index * 4)
    second[index + 1] = memory.read_u8(second_base + index * 4)
    if first[index + 1] ~= second[index + 1] then mirror_equal = 0 end
  end
  local surface_a = first[center_index + 1]
  local surface_b = second[center_index + 1]
  if surface_a ~= previous then
    transition_count = transition_count + 1
    console.log(string.format(
      "Transicao %d: %d -> %d no frame %d; lateral=%d progresso=%d",
      transition_count, previous, surface_a, frame, lateral, progress))
    previous = surface_a
  end

  output:write(string.format(
    "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d," ..
    "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
    sample, frame, speed, lateral, progress, lap, rank, collision,
    buttons.Left and 1 or 0, buttons.Right and 1 or 0,
    buttons[assert(cfg.accelerate_button)] and 1 or 0,
    surface_a, surface_b, mirror_equal,
    first[1], first[2], first[3], first[4], first[5], first[6], first[7],
    second[1], second[2], second[3], second[4], second[5], second[6], second[7]))

  if gui and gui.text then
    gui.text(4, 4, string.format("SUPERFICIE: %s (%d)", surface_name(surface_a), surface_a))
    gui.text(4, 18, string.format("A=%d B=%d espelho=%d lateral=%d", surface_a, surface_b,
      mirror_equal, lateral))
    gui.text(4, 32, string.format("sequencia A: %d %d %d %d %d %d %d",
      first[1], first[2], first[3], first[4], first[5], first[6], first[7]))
    gui.text(4, 46, string.format("transicoes=%d tempo=%d/3600", transition_count, sample + 1))
  end
  if sample % 60 == 0 then output:flush() end
  emu.frameadvance()
end

output:close()
console.log("DIAG superficie concluido: " .. output_path)
console.log("Agora execute: python python\\analyze_surface.py")
