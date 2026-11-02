-- Seleciona exclusivamente o experimento azul automatico no save 3.
local path = forms.openfile(nil, nil, "Perfil azul automatico|game_profile_blue_auto.ini|Arquivos INI|*.ini")
assert(path and path:match("[/\\]game_profile_blue_auto%.ini$"), "Selecione config/game_profile_blue_auto.ini")
local root = assert(path:match("^(.*)[/\\]config[/\\][^/\\]+$"), "Perfil fora da pasta config")
_G.TOPGEAR_PROFILE_OVERRIDE = path
local ok, err = pcall(dofile, root .. "/lua/Top Gear (USA).lua")
_G.TOPGEAR_PROFILE_OVERRIDE = nil
if not ok then error(err) end
