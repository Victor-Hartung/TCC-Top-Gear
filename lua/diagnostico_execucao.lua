-- Diagnostico 1/4: identidade da ROM, dominio WRAM e candidatos principais.
-- Pare qualquer outro script Lua antes de executar.

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
  local candidates = {join(".", "config" .. sep .. "game_profile.ini"), join("..", "config" .. sep .. "game_profile.ini")}
  if source ~= "" and source:sub(1, 1) ~= "[" then
    local script_dir = dirname(source)
    local root = script_dir and dirname(script_dir)
    if root then table.insert(candidates, 1, join(join(root, "config"), "game_profile.ini")) end
  end
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
  if memory.read_s16_le then return assert(memory.read_s16_le(address)) end
  local value = assert(memory.read_u16_le(address))
  return value >= 0x8000 and value - 0x10000 or value
end

local expected = assert(cfg.rom_sha1):upper()
local actual = hash(gameinfo.getromhash())
local domain_list = memory.getmemorydomainlist()
local domain_list_text
if type(domain_list) == "table" then
  domain_list_text = table.concat(domain_list, ",")
else
  domain_list_text = tostring(domain_list or ""):gsub("\r\n", ","):gsub("\n", ",")
end
local selected = memory.usememorydomain(assert(cfg.memory_domain))
assert(selected == true, "Nao foi possivel selecionar WRAM")
local domain_size = memory.getcurrentmemorydomainsize()

local output_path = join(project_dir, "diagnostico_execucao.txt")
-- Preserva coletas anteriores em vez de sobrescrever o CSV/TXT.
local original_output_path, serial = output_path, 0
while exists(output_path) do
  serial = serial + 1
  output_path = original_output_path:gsub("(%.[^%.]+)$", "_" .. os.date("%Y%m%d_%H%M%S") .. "_" .. serial .. "%1")
end
local out = assert(io.open(output_path, "w"))
local function line(label, value)
  local text = label .. "=" .. tostring(value)
  out:write(text .. "\n")
  console.log(text)
end

line("diagnostic_version", 2)
line("rom_name", gameinfo.getromname())
line("rom_status", gameinfo.getstatus())
line("rom_hash", actual)
line("expected_sha1", expected)
line("rom_ok", actual == expected and 1 or 0)
line("domain", memory.getcurrentmemorydomain())
line("domain_size", domain_size)
line("domain_selection_ok", selected and 1 or 0)
line("emu_frame", emu.framecount())
line("domain_list", domain_list_text)

local candidates = {
  {"speed_s16", "speed_address", "s16"},
  {"lateral_s16", "lateral_address", "s16"},
  {"progress_fraction", "progress_fraction_address", "u8"},
  {"progress", "progress_address", "u16"},
  {"lap_s16", "lap_address", "s16"},
  {"rank", "rank_address", "u16"},
  {"final_rank_s16", "final_rank_address", "s16"},
  {"collision_flags", "collision_flags_address", "u16"},
  {"fuel", "fuel_address", "u16"},
  {"nitro", "nitro_address", "u16"},
  {"gear", "gear_address", "u16"},
  {"total_laps", "total_laps_address", "u16"},
  {"track_length", "track_length_address", "u16"}
}

for _, item in ipairs(candidates) do
  local address = num(item[2])
  assert(address >= 0 and address + 1 < domain_size,
    string.format("Endereco fora do dominio: %s=%04X", item[2], address))
  local value
  if item[3] == "u8" then value = memory.read_u8(address)
  elseif item[3] == "s16" then value = s16(address)
  else value = memory.read_u16_le(address) end
  line(string.format("candidate_%s_0x%04X", item[1], address), value)
end

local base = num("racer_table_base")
local stride = num("racer_record_stride")
local count = num("racer_count")
assert(base + count * stride <= domain_size, "Tabela de corredores fora do dominio")
for index = 0, count - 1 do
  local record = base + index * stride
  line(string.format("racer_%02d_base", index), string.format("0x%04X", record))
  line(string.format("racer_%02d_id", index), memory.read_u8(record) % 32)
end

out:close()
joypad.set({}, 1)

if actual ~= expected then
  error("ROM incorreta. Nao execute os outros scripts.")
end
console.log("Diagnostico concluido: " .. output_path)
