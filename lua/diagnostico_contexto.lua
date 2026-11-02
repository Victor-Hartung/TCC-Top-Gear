-- Coleta SOMENTE leitura. Nenhum endereco candidato entra no treino por este script.
-- Pare a ponte principal; jogue manualmente. Escolha o perfil da v3.0.
local profile = assert(forms.openfile(nil, nil, "Perfil v3|game_profile.ini|INI|*.ini"), "Perfil cancelado")
assert(profile ~= "", "Perfil cancelado")
local sep = package.config:sub(1, 1)
local config_dir = assert(profile:match("^(.*)[/\\][^/\\]+$"))
local root = assert(config_dir:match("^(.*)[/\\][^/\\]+$"))
local cfg, handle = {}, assert(io.open(profile, "r"))
for line in handle:lines() do
  local key, value = line:match("^%s*([%w_]+)%s*=%s*(.-)%s*$")
  if key then cfg[key] = value end
end
handle:close()
local function num(key) return assert(tonumber(assert(cfg[key])), key) end
assert(num("profile_version") == 3, "Perfil incorreto")
local actual_hash = tostring(gameinfo.getromhash()):upper():match("([0-9A-F]+)$")
assert(actual_hash == cfg.rom_sha1:upper(), "ROM incorreta")
assert(memory.usememorydomain("WRAM") == true, "WRAM indisponivel")
assert(memory.getcurrentmemorydomainsize() == 131072, "WRAM deve ter 131072 bytes")
local base_name = root .. sep .. "runs" .. sep .. "diagnostics" .. sep ..
  "contexto_" .. os.date("%Y%m%d_%H%M%S") .. "_" .. tostring(emu.framecount())
local suffix = 0
while true do
  local old = io.open(base_name .. ".csv", "r")
  if not old then break end
  old:close(); suffix=suffix+1; base_name=base_name .. "_" .. suffix
end
local states = assert(io.open(base_name .. ".csv", "w"), "Pasta runs/diagnostics ausente")
local entities = assert(io.open(base_name .. "_racers.csv", "w"))
local ram = assert(io.open(base_name .. ".wram.bin", "wb"))
local snapshots = assert(io.open(base_name .. "_snapshots.csv", "w"))
local marks = assert(io.open(base_name .. "_marks.csv", "w"))
states:write("sample,frame,speed,lateral,progress,lap,rank,final_rank,total_laps,track_length,surface_raw,collision_raw,nitro_raw,nearest_front_candidate,nearest_rear_candidate\n")
entities:write("frame,index,id,raw_id,lateral,progress,lap_raw,motion_raw,status_raw,gap_circular_candidate,lateral_delta\n")
snapshots:write("frame,byte_offset,size,reason\n")
marks:write("frame,label,note\n")
local function u8(a) return memory.read_u8(a) end
local function u16(a) return memory.read_u16_le(a) end
local function s16(a) local n=u16(a); return n>=32768 and n-65536 or n end
local offset, closed, running = 0, false, true
local function close_files()
  if closed then return end
  closed=true; running=false
  for _, f in ipairs({states,entities,ram,snapshots,marks}) do f:flush(); f:close() end
  console.log("CONTEXTO salvo: " .. base_name .. " (envie os cinco arquivos juntos em ZIP)")
end
local function snapshot(reason)
  local chunks = {}
  for first=0,131071,1024 do
    local bytes = {}
    for address=first,first+1023 do bytes[#bytes+1]=string.char(u8(address)) end
    chunks[#chunks+1]=table.concat(bytes)
  end
  ram:write(table.concat(chunks)); ram:flush()
  snapshots:write(string.format("%d,%d,131072,%s\n", emu.framecount(), offset, reason))
  snapshots:flush(); offset=offset+131072
end
local function mark(label)
  if not running then return end
  marks:write(string.format("%d,%s,rotulo_manual_no_frame_do_clique\n", emu.framecount(), label))
  marks:flush()
  snapshot(label)
end
local form = forms.newform(530, 210, "TopGear v3 - memoria candidata", close_files)
forms.label(form, "Clique apenas apos observar o evento. O rotulo pode ter atraso.", 10, 10, 490, 25)
local labels = {{"TRASEIRA", "rear_contact"}, {"FRENTE", "front_contact"},
                {"PLACA/CACTO", "obstacle_contact"}, {"TEMPO ZERO", "time_zero"},
                {"CHEGADA", "completed_finish"}, {"LADO A LADO", "alongside"}}
for index, item in ipairs(labels) do
  local label = item[2]
  forms.button(form, item[1], function() mark(label) end,
    10+((index-1)%3)*165, 45+math.floor((index-1)/3)*40, 155, 32)
end
forms.button(form, "ENCERRAR E SALVAR", close_files, 10, 135, 490, 32)
event.onexit(close_files, "contexto-v3-close")
console.log("COLETA MANUAL: " .. base_name .. ".csv")
console.log("A captura de WRAM completa pode diminuir a velocidade. Nao e benchmark de FPS.")
local ok, failure = pcall(function()
  for sample=0,7199 do
    if not running then break end
    local frame = emu.framecount()
    local p,lateral,length = u16(num("progress_address")),s16(num("lateral_address")),u16(num("track_length_address"))
    local front, rear = -1, -1
    for index=0,19 do
      local record = num("racer_table_base") + index*num("racer_record_stride")
      local rawid, position, lat = u8(record),u16(record+7),s16(record+2)
      local id=rawid%32
      local gap = 0
      if length>0 then gap=(position-p+math.floor(length/2))%length-math.floor(length/2) end
      if id>=2 and id<=19 and length>0 and math.abs(gap)<=length*.1 then
        if gap>0 and (front<0 or gap<front) then front=gap end
        if gap<0 and (rear<0 or -gap<rear) then rear=-gap end
      end
      entities:write(string.format("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
        frame,index,id,rawid,lat,position,u8(record+9),u16(record+10),u16(record+16),gap,lat-lateral))
    end
    states:write(string.format("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
      sample,frame,s16(num("speed_address")),lateral,p,s16(num("lap_address")),
      u16(num("rank_address")),s16(num("final_rank_address")),u16(num("total_laps_address")),length,
      u8(num("surface_state_address")),u8(num("collision_flags_address")),u16(num("nitro_address")),front,rear))
    if sample%60==0 then snapshot("periodic"); states:flush(); entities:flush() end
    if gui and gui.text then gui.text(4,4,"CANDIDATOS frente="..front.." atras="..rear.." frame="..frame) end
    emu.frameadvance()
  end
end)
close_files()
pcall(function() forms.destroy(form) end)
if not ok then error(failure) end
