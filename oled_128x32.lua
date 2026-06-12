-- SSD1306 OLED Display - 0.91寸 128x32
-- I2C: SDA=GPIO41, SCL=GPIO42, Addr=0x3C

local i2c = require("i2c")
local ssd1306 = require("ssd1306")
local delay = require("delay")

local I2C_PORT = 0
local SDA_GPIO = 41
local SCL_GPIO = 42
local FREQ_HZ = 400000
local OLED_ADDR = 0x3C
local WIDTH = 128
local HEIGHT = 32

local bus = nil
local dev = nil
local display = nil

local function cleanup()
    if display then pcall(function() display:close() end); display = nil end
    if dev then pcall(function() dev:close() end); dev = nil end
    if bus then pcall(function() bus:close() end); bus = nil end
end

local ok, err = pcall(function()
    print("[oled] I2C port=" .. I2C_PORT .. " sda=" .. SDA_GPIO .. " scl=" .. SCL_GPIO)
    bus = i2c.new(I2C_PORT, SDA_GPIO, SCL_GPIO, FREQ_HZ)

    local addrs = bus:scan()
    print("[oled] scan: " .. #addrs .. " devices")
    for _, addr in ipairs(addrs) do
        print("[oled]   0x" .. string.format("%02X", addr))
    end

    if #addrs == 0 then
        error("no I2C device found")
    end

    dev = bus:device(OLED_ADDR)
    display = ssd1306.new(dev, { width = WIDTH, height = HEIGHT, addr = OLED_ADDR })
    display:init()
    print("[oled] init OK")

    -- 全白测试
    display:clear(true)
    display:show()
    print("[oled] full white")
    delay.delay_ms(500)

    -- 清屏
    display:clear(false)
    display:show()
    print("[oled] clear black")
    delay.delay_ms(300)

    -- 显示文字
    display:draw_text(10, 3, "Hello", true)
    display:draw_text(10, 15, "XiaoXi", true)
    display:show()
    print("[oled] text DONE")
end)

cleanup()
if not ok then
    print("[oled] ERROR: " .. tostring(err))
end
