-- SSD1306 OLED 控制脚本
-- 引脚: SDA=GPIO41, SCL=GPIO42

print("=== SSD1306 OLED 控制脚本 ===")
print("初始化 I2C...")

-- 初始化 I2C
local i2c = require("i2c")
local dev = i2c.new(0, 41, 42, 400000, true, true)

if not dev then
  print("错误: I2C 初始化失败")
  return
end

print("I2C 初始化成功")

-- 初始化 SSD1306
print("初始化 SSD1306...")
local ssd = require("ssd1306")
local oled = ssd.new(dev, 0x3C)

if not oled then
  print("错误: SSD1306 初始化失败")
  return
end

print("SSD1306 初始化成功")

-- 清屏
print("清屏...")
oled:clear()
oled:show()

-- 显示文字
print("显示文字...")
oled:draw_string(0, 0, "Hello", 16, 1)
oled:draw_string(0, 20, "XiaoXi", 16, 1)
oled:draw_string(0, 40, "Ready", 16, 1)
oled:show()

print("=== 完成 ===")
print("屏幕应该显示: Hello XiaoXi Ready")
