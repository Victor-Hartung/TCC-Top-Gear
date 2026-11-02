-- Diagnostico isolado, leitura de candidatos derivados da ROM. NAO valida treino.
-- Reutiliza a ponte atual em memoria; nao modifica Top Gear (USA).lua.
local source = debug.getinfo(1, "S").source or ""
local function dirname(path) return path:match("^(.*)[/\\][^/\\]+$") end
local function exists(path)
  local f = io.open(path, "rb")
  if f then f:close(); return true end
  return false
end
local function locate_bridge()
  -- NLua/BizHawk pode carregar o arquivo como [string "main"], sem caminho.
  local candidates = {"./lua/Top Gear (USA).lua", "./Top Gear (USA).lua",
    "../lua/Top Gear (USA).lua"}
  if source:sub(1,1)=="@" then
    local directory = dirname(source:sub(2))
    if directory then table.insert(candidates,1,directory .. "/Top Gear (USA).lua") end
  end
  for _,path in ipairs(candidates) do if exists(path) then return path end end
  local profile = forms.openfile(nil, nil,
    "Perfil da v3.0 (game_profile.ini)|game_profile.ini|Arquivos INI (*.ini)|*.ini")
  assert(profile and profile ~= "", "Selecao cancelada: escolha config/game_profile.ini da v3.0")
  assert(profile:match("game_profile%.ini$"), "Selecione exatamente config/game_profile.ini da v3.0")
  local config_dir = dirname(profile)
  local root = config_dir and dirname(config_dir)
  local path = root and (root .. "/lua/Top Gear (USA).lua")
  assert(path and exists(path), "Ponte nao encontrada ao lado do perfil selecionado")
  return path
end
local bridge_path = locate_bridge()
local file = assert(io.open(bridge_path, "rb"))
local code = file:read("*a"):gsub("\r\n", "\n")
file:close()

local function insert_once(needle, replacement)
  local first, last = code:find(needle, 1, true)
  assert(first and not code:find(needle, last+1, true), "Ponte mudou; atualize o diagnostico: " .. needle)
  code = code:sub(1,first-1) .. replacement .. code:sub(last+1)
end

insert_once('"opponent_count", "detector_samples"',
  '"opponent_count", "detector_samples", "finish_probe", "finish_samples"')
insert_once('local detector_history = {}', [=[
-- Todos os valores abaixo sao brutos; nao alimentam a observacao/recompensa.
local finish_history = {}
local function finish_capture()
  local values = {current_frame(), read_u16(0x1EB0), read_u16(0x1EB4),
    read_s16(0x1E58), read_u16(0x1EF2), read_u8(0x1EF3), read_u8(0x1EF5),
    read_u16(0x1EE0), read_u16(0x0118), read_s16(0x0124), read_u16(0x0128),
    read_s16(0x1E76), read_s16(0x1F00), read_u16(0x1E7A), read_s16(0x1E5A),
    read_u16(0x1E62), read_u16(0x1ED7), read_u16(0x1E56),
    read_u16(0x1EAE), read_u16(0x1F26)}
  for i=0,19 do values[#values+1] = read_u8(0x1F12+i) end
  finish_history[#finish_history+1] = table.concat(values, ",")
  while #finish_history>4 do table.remove(finish_history,1) end
end
local detector_history = {}
]=])
insert_once('  fields.detector_samples = table.concat(detector_history,";")',
  '  fields.detector_samples = table.concat(detector_history,";")\n' ..
  '  fields.finish_probe = 1\n  fields.finish_samples = table.concat(finish_history,";")')
insert_once('local function detector_capture()\n',
  'local function detector_capture()\n  finish_capture()\n')
insert_once('        detector_history = {}\n',
  '        detector_history = {}\n        finish_history = {}\n')
insert_once('if startup_command.kind ~= "hello"',
  'assert(startup_command.finish_probe == "1", "Lua apenas de diagnostico; use diagnose_finish_live.py --native-probe")\n' ..
  'if startup_command.kind ~= "hello"')
assert(load(code, "@" .. bridge_path))()
