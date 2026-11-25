-- Perfil azul automatico com caminhos relativos a este arquivo.
local source = debug.getinfo(1, "S").source
assert(source:sub(1, 1) == "@", "Execute este script a partir do arquivo Lua")
local lua_dir = assert(source:sub(2):match("^(.*)[/\\][^/\\]+$"), "Pasta Lua nao encontrada")
local project_dir = assert(lua_dir:match("^(.*)[/\\][^/\\]+$"), "Pasta do projeto nao encontrada")
_G.TOPGEAR_PROFILE_OVERRIDE = project_dir .. "/config/game_profile_blue_auto.ini"
local ok, err = pcall(dofile, lua_dir .. "/Top Gear (USA).lua")
_G.TOPGEAR_PROFILE_OVERRIDE = nil
if not ok then error(err) end
