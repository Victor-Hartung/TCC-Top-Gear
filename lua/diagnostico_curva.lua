-- Diagnostico rotulado de curva atual e look-ahead.
-- Dirija manualmente e use somente os botoes desta janela para rotular.

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

local function signed_u16(value)
  return value >= 0x8000 and value - 0x10000 or value
end

assert(normalized_hash(gameinfo.getromhash()) == assert(cfg.rom_sha1):upper(),
  "ROM SHA-1 incorreto")
assert(memory.usememorydomain(assert(cfg.memory_domain)) == true,
  "Falha selecionando WRAM")
assert(forms and forms.newform and forms.button and forms.label,
  "API forms indisponivel")

local speed_address = number("speed_address")
local lateral_address = number("lateral_address")
local progress_address = number("progress_address")
local lap_address = number("lap_address")
local total_laps_address = number("total_laps_address")
local surface_address = number("surface_state_address")
local curve_table = number("lateral_curve_table")
local track_length = memory.read_u16_le(number("track_length_address"))
assert(track_length > 0, "Comprimento da pista invalido")

-- A rotina da ROM usa o acumulador suavizado em direct page $46 para indexar
-- 0x4C00. O alvo em 0x1ED7 alimenta $46, mas nao e necessariamente identico
-- a ele durante movimento. A multiplicacao usa o byte baixo do word carregado.
local runtime_progress_address = 0x0046
local lookaheads = {0, 128, 256, 512, 768, 1024, 1536, 2048}
local required = 6
local counts = {straight=0, left=0, right=0}
local captures = {}
local running = true
local finish_without_right = false
local form_handle
local status_label
local last_capture_frame = -1000

local function curve_s8_at(progress, ahead)
  local wrapped = (progress + ahead) % track_length
  local offset = 2 * math.floor(wrapped / 32)
  local value = memory.read_u8(curve_table + offset)
  return value >= 0x80 and value - 0x100 or value
end

local function curve_word_at(progress)
  local wrapped = progress % track_length
  local offset = 2 * math.floor(wrapped / 32)
  return memory.read_u16_le(curve_table + offset)
end

local function signed_track_delta(target, runtime)
  local delta = (target - runtime) % track_length
  if delta > track_length / 2 then delta = delta - track_length end
  return delta
end

local function complete()
  return counts.straight >= required and counts.left >= required and
    (counts.right >= required or finish_without_right)
end

local function update_status()
  if status_label then
    forms.settext(status_label, string.format(
      "Reta: %d/%d | Esquerda: %d/%d | Direita: %d/%d",
      counts.straight, required, counts.left, required, counts.right, required))
  end
end

local function capture(label)
  local frame = emu.framecount()
  if frame - last_capture_frame < 20 then
    console.log("Amostra ignorada: espere pelo menos 20 frames entre cliques")
    return
  end
  local lap = signed_u16(memory.read_u16_le(lap_address))
  local total_laps = memory.read_u16_le(total_laps_address)
  if lap < 0 or lap >= total_laps then
    console.log("Amostra ignorada: rotule somente durante uma volta ativa")
    return
  end
  local surface = memory.read_u8(surface_address)
  if surface ~= 1 then
    console.log("Amostra ignorada: coloque o carro no asfalto antes de rotular a curva")
    return
  end
  if counts[label] >= required then
    console.log("Amostras de " .. label .. " ja estao completas")
    return
  end

  local progress = memory.read_u16_le(progress_address)
  local runtime_progress = memory.read_u16_le(runtime_progress_address)
  local row = {
    capture=#captures + 1,
    label=label,
    emu_frame=frame,
    speed=signed_u16(memory.read_u16_le(speed_address)),
    lateral=signed_u16(memory.read_u16_le(lateral_address)),
    surface_state=surface,
    progress=progress,
    runtime_progress=runtime_progress,
    progress_delta=signed_track_delta(progress, runtime_progress),
    lap=lap,
    total_laps=total_laps,
    track_index=math.floor((progress % track_length) / 32),
    runtime_track_index=math.floor((runtime_progress % track_length) / 32),
    runtime_word_0=curve_word_at(runtime_progress),
    target_word_0=curve_word_at(progress),
    runtime_curve_s8_0=curve_s8_at(runtime_progress, 0),
    runtime_curve_s8_128=curve_s8_at(runtime_progress, 128),
    runtime_curve_s8_256=curve_s8_at(runtime_progress, 256),
    runtime_curve_s8_512=curve_s8_at(runtime_progress, 512),
    runtime_curve_s8_768=curve_s8_at(runtime_progress, 768),
    runtime_curve_s8_1024=curve_s8_at(runtime_progress, 1024),
    runtime_curve_s8_1536=curve_s8_at(runtime_progress, 1536),
    runtime_curve_s8_2048=curve_s8_at(runtime_progress, 2048),
    target_curve_s8_0=curve_s8_at(progress, 0),
    target_curve_s8_128=curve_s8_at(progress, 128),
    target_curve_s8_256=curve_s8_at(progress, 256),
    target_curve_s8_512=curve_s8_at(progress, 512),
    target_curve_s8_768=curve_s8_at(progress, 768),
    target_curve_s8_1024=curve_s8_at(progress, 1024),
    target_curve_s8_1536=curve_s8_at(progress, 1536),
    target_curve_s8_2048=curve_s8_at(progress, 2048)
  }
  table.insert(captures, row)
  counts[label] = counts[label] + 1
  last_capture_frame = frame
  console.log(string.format(
    "Curva %d: %s (%d/%d), alvo=%d, runtime=%d, s8=%d, +1024=%d",
    row.capture, label, counts[label], required, progress, runtime_progress,
    row.runtime_curve_s8_0, row.runtime_curve_s8_1024))
end

form_handle = forms.newform(490, 245, "TopGear-RL - Rotular curvas", function()
  running = false
end)
forms.label(form_handle,
  "Mantenha o foco no jogo: C=RETA, V=ESQUERDA, B=DIREITA.",
  10, 8, 465, 20)
forms.button(form_handle, "RETA", function()
  capture("straight"); update_status()
end, 10, 35, 135, 32)
forms.button(form_handle, "CURVA ESQUERDA", function()
  capture("left"); update_status()
end, 160, 35, 140, 32)
forms.button(form_handle, "CURVA DIREITA", function()
  capture("right"); update_status()
end, 315, 35, 140, 32)
status_label = forms.label(form_handle, "", 10, 80, 440, 25, true)
forms.label(form_handle,
  "Use pontos diferentes. N finaliza Las Vegas sem curva direita.",
  10, 110, 440, 20)
forms.button(form_handle, "FINALIZAR: ESTA PISTA NAO TEM CURVA DIREITA", function()
  if counts.straight < required or counts.left < required then
    console.log("Antes de finalizar, complete 6 retas e 6 curvas esquerdas")
    return
  end
  finish_without_right = true
  console.log("Curva direita marcada como ausente nesta pista")
end, 55, 140, 380, 32)
forms.label(form_handle,
  "Os botoes sao alternativa; as teclas evitam tirar o foco da corrida.",
  10, 182, 465, 20)
update_status()

console.log("DIAG curva iniciado; execute somente este script Lua.")
console.log("Com o jogo em foco: C=reta, V=esquerda, B=direita, N=finalizar Las Vegas.")

local previous_keys = {C=false, V=false, B=false, N=false}
local function pressed(keys, name)
  return keys[name] == true and previous_keys[name] ~= true
end

while running and not complete() do
  local progress = memory.read_u16_le(progress_address)
  local runtime_progress = memory.read_u16_le(runtime_progress_address)
  local keys = input.get()
  if pressed(keys, "C") then capture("straight"); update_status() end
  if pressed(keys, "V") then capture("left"); update_status() end
  if pressed(keys, "B") then capture("right"); update_status() end
  if pressed(keys, "N") then
    if counts.straight >= required and counts.left >= required then
      finish_without_right = true
      console.log("Curva direita marcada como ausente em Las Vegas")
    else
      console.log("Antes de finalizar, complete 6 retas e 6 curvas esquerdas")
    end
  end
  previous_keys = {
    C=keys.C == true, V=keys.V == true, B=keys.B == true, N=keys.N == true
  }
  if gui and gui.text then
    gui.text(4, 4, string.format("CURVA s8 runtime=%d alvo=%d",
      curve_s8_at(runtime_progress, 0), curve_s8_at(progress, 0)))
    gui.text(4, 18, string.format("runtime pos=%d delta=%d", runtime_progress,
      signed_track_delta(progress, runtime_progress)))
    gui.text(4, 32, "C reta | V esquerda | B direita | N finalizar")
  end
  emu.frameadvance()
end

if form_handle and running then forms.destroy(form_handle) end
if complete() then
  local output_path = join(project_dir, "diagnostico_curva.csv")
  -- Preserva coletas anteriores em vez de sobrescrever o CSV/TXT.
  local original_output_path, serial = output_path, 0
  while exists(output_path) do
    serial = serial + 1
    output_path = original_output_path:gsub("(%.[^%.]+)$", "_" .. os.date("%Y%m%d_%H%M%S") .. "_" .. serial .. "%1")
  end
  local output = assert(io.open(output_path, "w"))
  output:write("capture,label,emu_frame,speed,lateral,surface_state,progress,runtime_progress,progress_delta,lap,total_laps,track_index,runtime_track_index,runtime_word_0,target_word_0,runtime_curve_s8_0,runtime_curve_s8_128,runtime_curve_s8_256,runtime_curve_s8_512,runtime_curve_s8_768,runtime_curve_s8_1024,runtime_curve_s8_1536,runtime_curve_s8_2048,target_curve_s8_0,target_curve_s8_128,target_curve_s8_256,target_curve_s8_512,target_curve_s8_768,target_curve_s8_1024,target_curve_s8_1536,target_curve_s8_2048\n")
  for _, row in ipairs(captures) do
    output:write(string.format(
      "%d,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
      row.capture, row.label, row.emu_frame, row.speed, row.lateral,
      row.surface_state, row.progress, row.runtime_progress, row.progress_delta,
      row.lap, row.total_laps, row.track_index, row.runtime_track_index,
      row.runtime_word_0, row.target_word_0,
      row.runtime_curve_s8_0, row.runtime_curve_s8_128,
      row.runtime_curve_s8_256, row.runtime_curve_s8_512,
      row.runtime_curve_s8_768, row.runtime_curve_s8_1024,
      row.runtime_curve_s8_1536, row.runtime_curve_s8_2048,
      row.target_curve_s8_0, row.target_curve_s8_128,
      row.target_curve_s8_256, row.target_curve_s8_512,
      row.target_curve_s8_768, row.target_curve_s8_1024,
      row.target_curve_s8_1536, row.target_curve_s8_2048))
  end
  output:close()
  console.log("DIAG curva concluido: " .. output_path)
  if finish_without_right and counts.right < required then
    console.log("Cobertura parcial: esta pista nao forneceu 6 curvas direitas")
  end
  console.log("Agora execute: python python\\analyze_curve.py")
else
  console.log("DIAG curva cancelado; nenhum CSV novo foi gravado")
end
