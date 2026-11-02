-- Leituras derivadas da rotina nativa; sem escrita em RAM ou controle automatico.
-- O Python verifica identidade, consistencia e validade antes de usar os valores.
local M = {}

local function valid_offset(offset)
  return offset >= 0 and offset <= 342 and offset % 18 == 0
end

function M.capture(frame, read_u8, read_u16, read_s16)
  local p1_offset, p2_offset = read_u16(0x0204), read_u16(0x0206)
  local p1_progress, length = read_u16(0x1ED7), read_u16(0x0200)
  local p1_record_progress, p1_record_lateral = 0, 0
  local p2_record_progress, p2_record_lateral = 0, 0
  if valid_offset(p1_offset) and valid_offset(p2_offset) and p1_offset ~= p2_offset then
    local p1_base, p2_base = 0x0212 + p1_offset, 0x0212 + p2_offset
    p1_record_progress, p1_record_lateral = read_u16(p1_base + 7), read_s16(p1_base + 2)
    p2_record_progress, p2_record_lateral = read_u16(p2_base + 7), read_s16(p2_base + 2)
  end
  local index = 2 * math.floor(p1_progress / 32)
  local corridor_raw = read_u16(0x7002 + index)
  local ahead_raw, curve_ahead = 0, 0
  if length > 0 then
    local ahead_index = 2 * math.floor(((p1_progress + 128) % length) / 32)
    ahead_raw = read_u16(0x7002 + ahead_index)
    curve_ahead = read_u8(0x4C00 + ahead_index)
    if curve_ahead >= 128 then curve_ahead = curve_ahead - 256 end
  end
  return table.concat({frame, p1_offset, p2_offset,
    p1_record_progress, p1_record_lateral,
    read_u16(0x1EDA), read_s16(0x1E8C),
    p2_record_progress, p2_record_lateral,
    corridor_raw, ahead_raw, curve_ahead,
    read_u16(0x1EF3), read_u16(0x1F04)}, ",")
end

return M
