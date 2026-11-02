-- Diagnostico rotulado de pista/offtrack.
-- Execute sozinho e dirija manualmente. As rotulacoes sao feitas por botoes
-- em uma janela propria para nao conflitar com os atalhos do BizHawk.

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

assert(hash(gameinfo.getromhash()) == assert(cfg.rom_sha1):upper(), "ROM SHA-1 incorreto")
assert(memory.usememorydomain(assert(cfg.memory_domain)) == true, "Falha selecionando WRAM")
local domain_size = memory.getcurrentmemorydomainsize()
assert(domain_size >= 0x2000, "WRAM menor que a faixa de diagnostico")

local speed_addr = number("speed_address")
local lateral_addr = number("lateral_address")
local progress_addr = number("progress_address")
local lap_addr = number("lap_address")
local rank_addr = number("rank_address")
local collision_addr = number("collision_flags_address")
local total_laps_addr = number("total_laps_address")
local output_path = join(project_dir, "diagnostico_offtrack.csv")
-- Preserva coletas anteriores em vez de sobrescrever o CSV/TXT.
local original_output_path, serial = output_path, 0
while exists(output_path) do
  serial = serial + 1
  output_path = original_output_path:gsub("(%.[^%.]+)$", "_" .. os.date("%Y%m%d_%H%M%S") .. "_" .. serial .. "%1")
end
local output = assert(io.open(output_path, "w"))
output:write(
  "capture,label,emu_frame,address_hex,value_u8,speed,lateral,progress,lap,rank," ..
  "collision_flags,total_laps\n")

local required = 6
local counts = {on_track=0, off_left=0, off_right=0}
local capture_number = 0
local running = true
local form_handle = nil
local status_label = nil

local function complete()
  return counts.on_track >= required and counts.off_left >= required and
    counts.off_right >= required
end

local function capture(label)
  local lap = signed_u16(memory.read_u16_le(lap_addr))
  local total_laps = memory.read_u16_le(total_laps_addr)
  if lap < 0 or lap >= total_laps then
    console.log("Amostra ignorada: rotule somente durante uma volta ativa")
    return
  end
  if counts[label] >= required then
    console.log("Amostras de " .. label .. " ja estao completas")
    return
  end

  capture_number = capture_number + 1
  counts[label] = counts[label] + 1
  local frame = emu.framecount()
  local speed = signed_u16(memory.read_u16_le(speed_addr))
  local lateral = signed_u16(memory.read_u16_le(lateral_addr))
  local progress = memory.read_u16_le(progress_addr)
  local rank = memory.read_u16_le(rank_addr)
  local collision = memory.read_u16_le(collision_addr)
  for address = 0, 0x1FFF do
    output:write(string.format(
      "%d,%s,%d,0x%04X,%d,%d,%d,%d,%d,%d,%d,%d\n",
      capture_number, label, frame, address, memory.read_u8(address), speed,
      lateral, progress, lap, rank, collision, total_laps))
  end
  output:flush()
  console.log(string.format(
    "Captura %d: %s (%d/%d), lateral=%d, progresso=%d",
    capture_number, label, counts[label], required, lateral, progress))
end

console.log("DIAG offtrack iniciado; execute somente este script Lua.")
console.log("Use os tres botoes da janela OFFTRACK para rotular a imagem.")
console.log("Faca 6 amostras de cada tipo em pontos diferentes.")

local function update_status()
  if status_label then
    forms.settext(status_label, string.format(
      "Na pista: %d/%d | Fora esq.: %d/%d | Fora dir.: %d/%d",
      counts.on_track, required, counts.off_left, required,
      counts.off_right, required))
  end
end

form_handle = forms.newform(430, 150, "TopGear-RL - Rotular pista", function()
  running = false
end)
forms.label(form_handle, "Dirija, deixe o carro na situacao visivel e clique uma vez:",
  10, 8, 400, 20)
forms.button(form_handle, "NA PISTA", function()
  capture("on_track"); update_status()
end, 10, 35, 125, 32)
forms.button(form_handle, "FORA ESQUERDA", function()
  capture("off_left"); update_status()
end, 145, 35, 130, 32)
forms.button(form_handle, "FORA DIREITA", function()
  capture("off_right"); update_status()
end, 285, 35, 125, 32)
status_label = forms.label(form_handle, "", 10, 78, 400, 25, true)
update_status()

while running and not complete() do
  if gui and gui.text then
    gui.text(4, 4, "OFFTRACK: use os botoes da janela de rotulos")
    gui.text(4, 18, string.format(
      "N %d/%d | F %d/%d | G %d/%d",
      counts.on_track, required, counts.off_left, required,
      counts.off_right, required))
  end
  emu.frameadvance()
end

output:close()
if form_handle and running then forms.destroy(form_handle) end
if complete() then
  console.log("DIAG offtrack concluido: " .. output_path)
  console.log("Agora execute: python python\\analyze_offtrack.py")
else
  console.log("DIAG offtrack cancelado; o CSV parcial nao deve ser analisado")
end
