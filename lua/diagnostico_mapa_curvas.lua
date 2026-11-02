-- Exporta instantaneamente a geometria completa da pista ativa.
-- Pode ser executado com o jogo pausado; nao exige dirigir nem rotular trechos.

local source = debug.getinfo(1, "S").source or ""
if source:sub(1, 1) == "@" then source = source:sub(2) end
local separator = package.config:sub(1, 1)

local function join(a, b) return a .. separator .. b end
local function dirname(path) return path:match("^(.*)[/\\][^/\\]+$") end
local function exists(path)
  local file = io.open(path, "r")
  if file then file:close(); return true end
  return false
end

local function locate_profile()
  local candidates = {
    join(".", "config" .. separator .. "game_profile.ini"),
    join("..", "config" .. separator .. "game_profile.ini")
  }
  if source ~= "" and source:sub(1, 1) ~= "[" then
    local script_dir = dirname(source)
    local root = script_dir and dirname(script_dir)
    if root then
      table.insert(candidates, 1, join(join(root, "config"), "game_profile.ini"))
    end
  end
  for _, path in ipairs(candidates) do
    if exists(path) then return path end
  end
  local chosen = forms.openfile(nil, nil,
    "Perfil TopGear-RL (game_profile.ini)|game_profile.ini|Arquivos INI (*.ini)|*.ini")
  assert(chosen and chosen ~= "", "Selecao cancelada: escolha config/game_profile.ini")
  assert(chosen:match("game_profile%.ini$"), "Selecione exatamente config/game_profile.ini")
  return chosen
end

local function trim(value)
  return (value:gsub("^%s+", ""):gsub("%s+$", ""))
end

local profile_path = locate_profile()
local config_dir = assert(dirname(profile_path), "Caminho do perfil invalido")
local project_dir = assert(dirname(config_dir), "Pasta do projeto nao identificada")
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

local function normalized_hash(raw)
  local value = tostring(raw or ""):upper()
  return value:match("([0-9A-F][0-9A-F]+)$") or value
end

local function signed_u8(value)
  return value >= 0x80 and value - 0x100 or value
end

local function signed_u16(value)
  return value >= 0x8000 and value - 0x10000 or value
end

assert(normalized_hash(gameinfo.getromhash()) == assert(cfg.rom_sha1):upper(),
  "ROM SHA-1 incorreto")
assert(memory.usememorydomain(assert(cfg.memory_domain)) == true,
  "Falha selecionando WRAM")

local track_length = memory.read_u16_le(number("track_length_address"))
assert(track_length > 0, "Comprimento da pista invalido")
-- A ROM faz (posicao >> 4) & 0xFFFE. Zerar o bit inferior depois do
-- deslocamento equivale a uma entrada de 2 bytes para cada 32 unidades.
local entry_count = math.floor((track_length + 31) / 32)
local curve_table = number("lateral_curve_table")
local grade_table = number("geometry_table_a")
local road_table = number("road_type_table")
local progress = memory.read_u16_le(number("progress_address"))
local runtime_progress = memory.read_u16_le(0x0046)
local output_path = join(project_dir, "diagnostico_mapa_curvas.csv")
-- Preserva coletas anteriores em vez de sobrescrever o CSV/TXT.
local original_output_path, serial = output_path, 0
while exists(output_path) do
  serial = serial + 1
  output_path = original_output_path:gsub("(%.[^%.]+)$", "_" .. os.date("%Y%m%d_%H%M%S") .. "_" .. serial .. "%1")
end
local output = assert(io.open(output_path, "w"))

output:write("track_length,entry_count,live_progress,runtime_progress,index,progress_start,progress_end,offset,curve_word_u16,curve_word_s16,curve_low_u8,curve_low_s8,curve_high_u8,curve_high_s8,grade_word_u16,grade_word_s16,road_word_u16,road_low_u8,road_high_u8\n")
for index = 0, entry_count - 1 do
  local offset = 2 * index
  local curve_word = memory.read_u16_le(curve_table + offset)
  local curve_low = memory.read_u8(curve_table + offset)
  local curve_high = memory.read_u8(curve_table + offset + 1)
  local grade_word = memory.read_u16_le(grade_table + offset)
  local road_word = memory.read_u16_le(road_table + offset)
  output:write(string.format(
    "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
    track_length, entry_count, progress, runtime_progress, index,
    index * 32, math.min(track_length - 1, index * 32 + 31), offset,
    curve_word, signed_u16(curve_word), curve_low, signed_u8(curve_low),
    curve_high, signed_u8(curve_high), grade_word, signed_u16(grade_word),
    road_word, road_word % 0x100, math.floor(road_word / 0x100)))
end
output:close()

console.log(string.format(
  "Mapa exportado: %d entradas para %d unidades de pista", entry_count, track_length))
console.log("Arquivo: " .. output_path)
console.log("Envie diagnostico_mapa_curvas.csv para analise; nao precisa dirigir.")
