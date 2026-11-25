-- O launcher fornece a raiz do clone ao processo do BizHawk.
local project_dir = assert(os.getenv("TOPGEAR_PROJECT_ROOT"), "Abra com scripts/abrir_bizhawk_pacote.ps1")
_G.TOPGEAR_PROFILE_OVERRIDE = project_dir .. "/config/game_profile_blue_auto.ini"
dofile(project_dir .. "/lua/Top Gear (USA).lua")
