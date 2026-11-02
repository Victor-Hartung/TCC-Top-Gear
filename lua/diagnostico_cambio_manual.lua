-- Abra pela Lua Console, sozinho. Slot 2: MANUAL/tipo A na largada.
-- Nao usa socket, nao treina, nao salva slots e nao escreve WRAM.
local profile = assert(forms.openfile(nil,nil,"Perfil v3|game_profile.ini|INI|*.ini"), "Perfil cancelado")
assert(profile ~= "", "Perfil cancelado")
local config_dir = assert(profile:match("^(.*)[/\\][^/\\]+$"))
local root = assert(config_dir:match("^(.*)[/\\][^/\\]+$"))
local cfg, f = {}, assert(io.open(profile,"r"))
for line in f:lines() do
  local k,v=line:match("^%s*([%w_]+)%s*=%s*(.-)%s*$")
  if k then cfg[k]=v end
end
f:close()
assert(cfg.profile_version=="3", "Selecione o perfil v3")
assert(cfg.accelerate_button=="X" and cfg.brake_button=="Y" and cfg.turbo_button=="A", "Teste exige controle tipo A: X/Y/A e R/L")
assert(tostring(gameinfo.getromhash()):upper():match("([0-9A-F]+)$")==cfg.rom_sha1:upper(), "ROM incorreta")
assert(memory.usememorydomain("WRAM")==true, "WRAM indisponivel")
assert(memory.getcurrentmemorydomainsize()==131072, "WRAM incorreta")
assert(client and client.screenshot, "client.screenshot indisponivel: teste exige capturas do painel")
local function u(a) return memory.read_u16_le(a) end
local function s(a) local v=u(a); return v>=32768 and v-65536 or v end
local manual_slot=2 -- Slot 1 automatico permanece preservado.
joypad.set({A=false,B=false,X=false,Y=false,L=false,R=false,Left=false,Right=false,Up=false,Down=false,Start=false,Select=false},1)
assert(savestate.loadslot(manual_slot,true)==true, "Nao foi possivel carregar o slot 2; salve nele a largada MANUAL")
assert(u(0x1E72)==0 and s(0x1E5A)<2000, "Comece na largada, primeira marcha e baixa velocidade, em MANUAL")
local path=root.."/runs/diagnostics/cambio_manual_"..os.date("%Y%m%d_%H%M%S").."_"..emu.framecount()
local suffix=0
while true do
  local check=io.open(path.."_"..suffix..".csv","r")
  if not check then break end
  check:close();suffix=suffix+1
end
path=path.."_"..suffix..".csv"
local out=assert(io.open(path,"w"), "Pasta runs/diagnostics ausente")
local image_base=path:sub(1,-5)
local shots=assert(io.open(image_base.."_hud.tsv","w"))
shots:write("relative_frame\temu_frame\tsequence_frame\tgear_raw\tfilename\n")
out:write("relative_frame,emu_frame,accelerate,shift_up,shift_down,gear_before,gear_after,speed_before,speed_after,engine_gauge_raw,up_mask_raw,down_mask_raw,lap,surface,collision_raw,nitro_raw,fuel_raw,savestate_slot,car_table_offset_raw,capture_version,phase,sequence_frame\n")
local closed=false
local function release()
  joypad.set({A=false,B=false,X=false,Y=false,L=false,R=false,Left=false,Right=false,Up=false,Down=false,Start=false,Select=false},1)
end
local function close()
  if closed then return end
  closed=true;release();out:flush();out:close();shots:flush();shots:close()
  console.log("CAMBIO CSV: "..path)
  console.log("PAINEL: "..image_base.."_hud.tsv (imagens PNG ao lado do CSV)")
end
event.onexit(close,"cambio-manual-close")
-- Velocidade bruta: apenas prontidao mecanica, nao RPM/ponto ideal de troca.
local ready_speed,ready_frames,max_launch_frames=1500,8,1200
local sequence_length=480
local pulses={{60,"R"},{120,"R"},{180,"R"},{240,"R"},{300,"L"},{360,"R"},{420,"L"}}
local frame=0
local function capture_hud(sequence_frame)
  local gear=u(0x1E72)
  local filename=image_base.."_hud_f"..(frame-1).."_raw"..gear..".png"
  client.screenshot(filename)
  local check=assert(io.open(filename,"rb"),"Captura de painel nao foi salva: "..filename)
  local signature=check:read(8);check:close()
  assert(signature=="\137PNG\r\n\26\n","Captura de painel nao e PNG: "..filename)
  shots:write(table.concat({frame-1,emu.framecount(),sequence_frame,gear,filename:match("[^/\\]+$")},"\t").."\n")
  shots:flush()
end
local function advance(phase,sequence_frame,up,down)
  local gear,speed=u(0x1E72),s(0x1E5A)
  release();joypad.set({X=true,R=up,L=down},1)
  local label=phase==0 and ("aguardando movimento "..frame.."/"..max_launch_frames)
    or ("teste "..sequence_frame.."/"..sequence_length)
  gui.text(4,4,"CAMBIO MANUAL | "..label.." | X + "..(up and "R" or down and "L" or "--"))
  gui.text(4,18,"marcha bruta="..gear.." | conta-giros candidato="..u(0x1E5E))
  emu.frameadvance()
  out:write(table.concat({frame,emu.framecount(),1,up and 1 or 0,down and 1 or 0,gear,u(0x1E72),speed,s(0x1E5A),u(0x1E5E),u(0x1F7A),u(0x1F7C),s(0x1E76),memory.read_u8(0x0727),memory.read_u8(0x1EF5),u(0x1E6C),u(0x1E62),manual_slot,u(0x1EE8),2,phase,sequence_frame},",").."\n")
  if frame%60==0 then out:flush() end
  frame=frame+1
end
console.log("CAMBIO v2 + PAINEL: aguarda movimento; depois 480 frames. Captura imagens automaticamente. Nao toque nos controles.")
local ok,err=pcall(function()
  local stable=0
  for _=1,max_launch_frames do
    advance(0,-1,false,false)
    stable=s(0x1E5A)>=ready_speed and stable+1 or 0
    if stable>=ready_frames then break end
  end
  assert(stable>=ready_frames,"Sem movimento suficiente em 1200 frames; coleta preservada. Confira a largada no slot 2.")
  console.log("Movimento observado. Iniciando pulsos R/L no frame relativo "..frame)
  for sequence_frame=0,sequence_length-1 do
    local up,down=false,false
    for _,p in ipairs(pulses) do
      if sequence_frame>=p[1] and sequence_frame<p[1]+4 then up=p[2]=="R";down=p[2]=="L" end
    end
    advance(1,sequence_frame,up,down)
    -- Espera 24 frames depois do comando para fotografar o HUD estabilizado.
    local photograph=sequence_frame==0
    for _,p in ipairs(pulses) do
      if sequence_frame==p[1]+24 then photograph=true end
    end
    if photograph then capture_hud(sequence_frame) end
  end
end)
close()
if not ok then error(err) end
console.log("COLETA CONCLUIDA. Analisar CSV e PNGs: valor bruto de marcha nao confirma sozinho o numero no GEAR.")
