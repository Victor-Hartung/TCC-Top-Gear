-- Ensaio local de aceleracao: quarta mantida versus subida para quinta.
-- Slot 3 MANUAL, azul ja em quarta e em movimento. Sem treino, nitro, escrita WRAM ou save.
local profile=assert(forms.openfile(nil,nil,"Perfil v3|game_profile.ini|INI|*.ini"),"Perfil cancelado")
local config_dir=assert(profile:match("^(.*)[/\\][^/\\]+$"))
local root=assert(config_dir:match("^(.*)[/\\][^/\\]+$"))
local cfg,f={},assert(io.open(profile,"r"))
for line in f:lines() do
  local k,v=line:match("^%s*([%w_]+)%s*=%s*(.-)%s*$")
  if k then cfg[k]=v end
end
f:close()
assert(cfg.profile_version=="3" and cfg.accelerate_button=="X" and cfg.brake_button=="Y" and cfg.turbo_button=="A","Exige perfil v3 e controle tipo A")
assert(tostring(gameinfo.getromhash()):upper():match("([0-9A-F]+)$")==cfg.rom_sha1:upper(),"ROM incorreta")
assert(memory.usememorydomain("WRAM")==true and memory.getcurrentmemorydomainsize()==131072,"WRAM incorreta")
local function u(a) return memory.read_u16_le(a) end
local function s(a) local v=u(a);return v>=32768 and v-65536 or v end
local function release()
  joypad.set({A=false,B=false,X=false,Y=false,L=false,R=false,Left=false,Right=false,Up=false,Down=false,Start=false,Select=false},1)
end
local function fingerprint()
  local a,b=1,0
  for address=0,131071 do
    a=(a+memory.read_u8(address))%65521;b=(b+a)%65521
  end
  return b*65536+a
end
local base=root.."/runs/diagnostics/ensaio_cambio_lancado_"..os.date("%Y%m%d_%H%M%S")
local serial=0
while true do
  local old=io.open(base.."_"..serial..".csv","r")
  if not old then break end
  old:close();serial=serial+1
end
local path=base.."_"..serial..".csv"
local out=assert(io.open(path,"w"),"Pasta runs/diagnostics ausente")
-- Parte do mesmo slot 3 em todas as rodadas; apenas a troca varia.
local capture_version,prep_frames,measure_frames=10,0,120
local expected_car=48
out:write("trial,variant,frame,emu_frame,phase,phase_frame,gear_before,gear_after,speed_before,speed_after,engine_raw,surface_before,surface_after,impact_before,impact_after,nitro_before,nitro_after,fuel_before,fuel_after,accelerate,shift_up,shift_down,slot,car_raw,reset_wram_adler32,branch_wram_adler32,capture_version,prep_frames,measure_frames\n")
local closed=false
local function close()
  if closed then return end
  closed=true;release();out:flush();out:close();console.log("ENSAIO CSV: "..path)
end
event.onexit(close,"ensaio-cambio-close")
-- ABBA: duas repeticoes por variante a partir do mesmo estado lancado.
local variants={0,1,1,0} -- 0 mantem quarta; 1 envia R para quinta.
local ok,err=pcall(function()
  for trial,variant in ipairs(variants) do
    release()
    assert(savestate.loadslot(3,true)==true,"Nao foi possivel carregar slot 3")
    assert(u(0x1E72)==3 and s(0x1E5A)>7312,"Slot 3 exige GEAR 4 e velocidade maior que a ultima faixa testada (bruta >7312)")
    assert(memory.read_u8(0x0727)==1 and math.floor(memory.read_u8(0x1EF5)/128)%2==0 and u(0x1E6C)==3,"Slot 3 exige asfalto, nenhum impacto ativo e tres nitros intactos")
    assert(u(0x1EE8)==expected_car and u(0x1F7A)==16 and u(0x1F7C)==32,"Save difere do carro/controles da coleta manual validada")
    local reset_hash,branch_hash=fingerprint(),0
    local frame=0
    local function advance(phase,phase_frame,up)
      local gear,speed=u(0x1E72),s(0x1E5A)
      local surface,impact=memory.read_u8(0x0727),memory.read_u8(0x1EF5)
      local nitro,fuel=u(0x1E6C),u(0x1E62)
      release();joypad.set({X=true,R=up},1)
      gui.text(4,4,"ENSAIO LANCADO v10 AZUL "..trial.."/4 | "..(variant==0 and "manter GEAR 4" or "subir para GEAR 5"))
      gui.text(4,18,"fase "..phase.." frame "..phase_frame.." | GEAR "..(gear+1).." | sem nitro/treino")
      emu.frameadvance()
      out:write(table.concat({trial,variant,frame,emu.framecount(),phase,phase_frame,gear,u(0x1E72),speed,s(0x1E5A),u(0x1E5E),surface,memory.read_u8(0x0727),impact,memory.read_u8(0x1EF5),nitro,u(0x1E6C),fuel,u(0x1E62),1,up and 1 or 0,0,3,u(0x1EE8),reset_hash,branch_hash,capture_version,prep_frames,measure_frames},",").."\n")
      if frame%60==0 then out:flush() end
      frame=frame+1
    end
    branch_hash=fingerprint()
    for measure=0,measure_frames-1 do advance(2,measure,variant==1 and measure<4) end
    out:flush();release()
  end
end)
close()
if not ok then error(err) end
console.log("ENSAIO CONCLUIDO. Comparar com analisar_ensaio_cambio.py; nao demonstra vantagem manual/automatico nem ponto otimo.")
