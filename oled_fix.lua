local i2c = require("i2c")
local delay = require("delay")

local I2C_PORT = 0
local SDA_GPIO = 41
local SCL_GPIO = 42
local FREQ_HZ = 400000
local OLED_ADDR = 0x3C

local bus = nil
local dev = nil
local display = nil

local function cleanup()
    if display then pcall(function() display:close() end) end
    if dev then pcall(function() dev:close() end) end
    if bus then pcall(function() bus:close() end) end
end

local ok, err = pcall(function()
    print(string.format(
        "[oled] open I2C port=%d sda=%d scl=%d freq=%d addr=0x%02X",
        I2C_PORT, SDA_GPIO, SCL_GPIO, FREQ_HZ, OLED_ADDR
    ))

    bus = i2c.new(I2C_PORT, SDA_GPIO, SCL_GPIO, FREQ_HZ)
    local addrs = bus:scan()
    print("[oled] scan found " .. #addrs .. " devices")
    for _, a in ipairs(addrs) do
        print(string.format("[oled]   addr=0x%02X", a))
    end

    if #addrs == 0 then
        error("[oled] no I2C device found")
    end

    dev = bus:device(OLED_ADDR)
    print("[oled] i2c device opened")

    local ssd1306 = require("ssd1306")
    print("[oled] driver loaded")

    display = ssd1306.new(dev, {
        width = 128,
        height = 64,
        addr = OLED_ADDR,
    })

    display:init()
    print("[oled] panel initialized")

    display:clear(false)
    display:show()
    print("[oled] clear black")
    delay.delay_ms(500)

    display:clear(true)
    display:show()
    print("[oled] full white")
    delay.delay_ms(500)

    display:clear(false)
    display:draw_text(10, 10, "Hello", true)
    display:draw_text(10, 26, "XiaoXi", true)
    display:draw_text(10, 42, "Ready!", true)
    display:show()
    print("[oled] text displayed")

    print("[oled] DONE")
end)

cleanup()
if not ok then
    print("[oled] ERROR: " .. tostring(err))
end
