-- Ponte manual separada: selecione config/game_profile_manual.ini da v3.0.
local path = forms.openfile(nil, nil, "Perfil manual|game_profile_manual.ini|Arquivos INI|*.ini")
assert(path and path:match("[/\\]game_profile_manual%.ini$"), "Selecione config/game_profile_manual.ini")
local root = assert(path:match("^(.*)[/\\]config[/\\][^/\\]+$"), "Perfil fora da pasta config")
_G.TOPGEAR_PROFILE_OVERRIDE = path
local ok, err = pcall(dofile, root .. "/lua/Top Gear (USA).lua")
_G.TOPGEAR_PROFILE_OVERRIDE = nil
if not ok then error(err) end
