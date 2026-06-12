print("=== OLED TEST START ===")
local ok, oled = pcall(function() return require("oled") end)
if ok and oled then
  print("OLED module found")
  oled:init(4)
  oled:clear()
  oled:show()
  oled:draw_string(0, 0, "Hello", 16, 1)
  oled:draw_string(0, 20, "XiaoXi", 16, 1)
  oled:draw_string(0, 40, "Ready", 16, 1)
  oled:show()
  print("OLED DRAWN")
else
  print("OLED module NOT found")
end
print("=== OLED TEST END ===")
