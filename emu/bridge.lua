-- File-based control bridge for EmuHawk.
-- emu.py writes commands to cmd.txt; this script runs them frame by frame,
-- then writes done.txt with any output lines.
--
-- Commands (one per line):
--   press <Btn+Btn> <frames>   hold buttons for N frames (then 1 frame released)
--   touch <x> <y>              tap the bottom screen
--   wait <frames>              advance N frames with no input
--   shot <path>                save a screenshot (png)
--   save <path> / load <path>  savestate to/from file
--   speed <percent>            emulation speed, e.g. 100 or 3200
--   read <addr> <len>          dump main RAM bytes as hex into done.txt

local DIR = "C:/projects/pokemon-black-gunk/emu/"
local CMD = DIR .. "cmd.txt"
local DONE = DIR .. "done.txt"

local function file_exists(p)
    local f = io.open(p, "r")
    if f then f:close() return true end
    return false
end

local function write_done(lines)
    local f = io.open(DONE .. ".tmp", "w")
    f:write(table.concat(lines, "\n"), "\n")
    f:close()
    os.remove(DONE)
    os.rename(DONE .. ".tmp", DONE)
end

local function split(s)
    local t = {}
    for w in s:gmatch("%S+") do t[#t + 1] = w end
    return t
end

local function advance(n, buttons)
    for _ = 1, n do
        if buttons then joypad.set(buttons) end
        emu.frameadvance()
    end
end

-- record the button names the core exposes, for reference
do
    local names = {}
    for k, _ in pairs(joypad.get()) do names[#names + 1] = k end
    table.sort(names)
    local f = io.open(DIR .. "buttons.txt", "w")
    f:write(table.concat(names, "\n"), "\n")
    f:close()
end

client.SetSoundOn(false)
client.speedmode(100)
client.pause()

while true do
    if file_exists(CMD) then
        local f = io.open(CMD, "r")
        local text = f:read("*a")
        f:close()
        os.remove(CMD)
        client.unpause()

        local out = {}
        local resume = false
        for line in text:gmatch("[^\r\n]+") do
            local a = split(line)
            local op = a[1]
            local ok, err = pcall(function()
                if op == "press" then
                    local b = {}
                    for name in a[2]:gmatch("[^+]+") do b[name] = true end
                    advance(tonumber(a[3] or "6"), b)
                    advance(1)
                elseif op == "touch" then
                    -- touch <x> <y> on the bottom screen (0-255, 0-191)
                    for _ = 1, 8 do
                        joypad.set({ Touch = true })
                        joypad.setanalog({ ["Touch X"] = tonumber(a[2]), ["Touch Y"] = tonumber(a[3]) })
                        emu.frameadvance()
                    end
                    local j = joypad.get()
                    out[#out + 1] = "touch state: " .. tostring(j["Touch"]) .. " " .. tostring(j["Touch X"]) .. "," .. tostring(j["Touch Y"])
                    advance(2)
                elseif op == "lua" then
                    -- lua <code>: run a Lua chunk (debugging); its return value goes to done.txt
                    local f2 = assert(load(line:sub(5)))
                    out[#out + 1] = "lua " .. tostring(f2())
                elseif op == "touchhold" then
                    -- touchhold <x> <y> <frames>: keep the stylus down on one point
                    for _ = 1, tonumber(a[4]) do
                        joypad.set({ Touch = true })
                        joypad.setanalog({ ["Touch X"] = tonumber(a[2]), ["Touch Y"] = tonumber(a[3]) })
                        emu.frameadvance()
                    end
                    advance(2)
                elseif op == "drag" then
                    -- drag <x1> <y1> <x2> <y2> <frames>: slide the stylus in a straight line
                    local x1, y1, x2, y2, n = tonumber(a[2]), tonumber(a[3]), tonumber(a[4]), tonumber(a[5]), tonumber(a[6])
                    for i = 0, n do
                        joypad.set({ Touch = true })
                        joypad.setanalog({ ["Touch X"] = math.floor(x1 + (x2 - x1) * i / n), ["Touch Y"] = math.floor(y1 + (y2 - y1) * i / n) })
                        emu.frameadvance()
                    end
                    advance(2)
                elseif op == "heaps" then
                    -- heaps <sHeapInfo addr>: "id:free:blocks" for every live game heap (expheap free list walk)
                    local D = "ARM9_System_Bus"
                    local hi = tonumber(a[2])
                    local handles = memory.read_u32_le(hi, D)
                    local nblocks = memory.read_u32_le(hi + 0x0C, D)
                    local idxs = memory.read_u32_le(hi + 0x10, D)
                    local total = memory.read_u16_le(hi + 0x14, D)
                    local maxHeaps = memory.read_u16_le(hi + 0x18, D)
                    local row = {}
                    for id = 0, total - 1 do
                        local idx = memory.read_u8(idxs + id, D)
                        if idx < maxHeaps then
                            local h = memory.read_u32_le(handles + idx * 4, D)
                            if h >= 0x02000000 and h < 0x02400000 then
                                local free, mb, guard = 0, memory.read_u32_le(h + 0x24, D), 0
                                while mb >= 0x02000000 and mb < 0x02400000 and guard < 4096 do
                                    free = free + memory.read_u32_le(mb + 4, D)
                                    mb = memory.read_u32_le(mb + 0x0C, D)
                                    guard = guard + 1
                                end
                                row[#row + 1] = id .. ":" .. free .. ":" .. memory.read_u16_le(nblocks + id * 2, D)
                            end
                        end
                    end
                    out[#out + 1] = "heaps " .. table.concat(row, " ")
                elseif op == "alive" then
                    -- alive <counter addr> <frames>: run N frames and report how far the game's own frame counter moved
                    local D = "ARM9_System_Bus"
                    local addr = tonumber(a[2])  -- a counter the main loop bumps every frame: stops on a crash or hang
                    local before = memory.read_u32_le(addr, D)
                    advance(tonumber(a[3]))
                    local pc = emu.getregisters()["ARM9 r15"] or 0
                    out[#out + 1] = "alive " .. (memory.read_u32_le(addr, D) - before) .. " pc=" .. string.format("%08X", pc & 0xFFFFFFFF)
                elseif op == "holdshots" then
                    -- holdshots <Btn|none> <frames> <every> <path prefix>: hold, screenshotting every N frames
                    local btn, frames, every, prefix = a[2], tonumber(a[3]), tonumber(a[4]), a[5]
                    for f = 0, frames - 1 do
                        if btn ~= "none" then joypad.set({ [btn] = true }) end
                        emu.frameadvance()
                        if f % every == 0 then client.screenshot(string.format("%s_%03d.png", prefix, f)) end
                    end
                elseif op == "trackobjs" then
                    -- trackobjs <Btn|none> <frames> <sFieldSystem addr> <csv path>: log player (0xFF) and follower (0xFD)
                    -- tile and fixed-point positions every frame
                    local btn, frames, fsAddr = a[2], tonumber(a[3]), tonumber(a[4])
                    local D = "ARM9_System_Bus"
                    local f2 = io.open(a[5], "a")
                    for fr = 0, frames - 1 do
                        if btn ~= "none" then joypad.set({ [btn] = true }) end
                        emu.frameadvance()
                        local fs = memory.read_u32_le(fsAddr, D)
                        local mom = memory.read_u32_le(fs + 0x38, D)
                        local maxObj = memory.read_u32_le(mom + 4, D)
                        -- outside the field (battles, menus) these pointers are stale: log nothing for the frame
                        if fs < 0x02000000 or fs >= 0x02400000 or mom < 0x02000000 or mom >= 0x02400000 or maxObj > 64 then maxObj = 0 end
                        local arr = memory.read_u32_le(mom + 0x124, D)
                        local row = { btn, fr }
                        for _, want in ipairs({ 0xFF, 0xFD }) do
                            local found = false
                            for i = 0, maxObj - 1 do
                                local o = arr + i * 0x128
                                if memory.read_u32_le(o, D) & 1 == 1 and memory.read_u32_le(o + 8, D) == want then
                                    row[#row + 1] = memory.read_s32_le(o + 0x64, D)
                                    row[#row + 1] = memory.read_s32_le(o + 0x6C, D)
                                    row[#row + 1] = memory.read_s32_le(o + 0x70, D) / 4096
                                    row[#row + 1] = memory.read_s32_le(o + 0x78, D) / 4096
                                    row[#row + 1] = memory.read_s32_le(o + 0x88, D) / 4096
                                    row[#row + 1] = memory.read_u32_le(o + 0xA4, D)
                                    row[#row + 1] = string.format("%08X", memory.read_u32_le(o, D))
                                    row[#row + 1] = memory.read_u32_le(o + 0x40, D)
                                    found = true
                                    break
                                end
                            end
                            if not found then for _ = 1, 8 do row[#row + 1] = "" end end
                        end
                        f2:write(table.concat(row, ","), "\n")
                    end
                    f2:close()
                elseif op == "resume" then
                    -- resume: leave the game running for a human player after this batch
                    resume = true
                elseif op == "wait" then
                    advance(tonumber(a[2]))
                elseif op == "shot" then
                    client.screenshot(a[2])
                elseif op == "save" then
                    savestate.save(a[2])
                elseif op == "load" then
                    savestate.load(a[2])
                elseif op == "flushsave" then
                    -- write the cart save to BizHawk's SaveRAM folder
                    client.saveram()
                elseif op == "speed" then
                    client.speedmode(tonumber(a[2]))
                elseif op == "dump" then
                    -- dump <domain> <addr> <len> <path>: raw bytes to a file
                    local addr, len = tonumber(a[3]), tonumber(a[4])
                    local f2 = io.open(a[5], "wb")
                    local bytes = memory.read_bytes_as_array(addr, len, a[2])
                    local chunk = {}
                    for i = 1, #bytes do
                        chunk[#chunk + 1] = string.char(bytes[i])
                        if #chunk == 4096 then f2:write(table.concat(chunk)); chunk = {} end
                    end
                    f2:write(table.concat(chunk))
                    f2:close()
                elseif op == "poke" then
                    -- poke <domain> <addr> <path>: write a file's raw bytes to memory
                    local f2 = io.open(a[4], "rb")
                    local data = f2:read("*a")
                    f2:close()
                    local bytes = {}
                    for i = 1, #data do bytes[i] = string.byte(data, i) end
                    memory.write_bytes_as_array(tonumber(a[3]), bytes, a[2])
                elseif op == "trace" then
                    -- trace <addr> <path>: every time the ARM9 runs <addr>, append r0-r3, lr and 24 stack words
                    local D = "ARM9 System Bus"
                    local path = a[3]
                    event.onmemoryexecute(function()
                        local r = emu.getregisters()
                        local row = { emu.framecount() }
                        for _, k in ipairs({ "r0", "r1", "r2", "r3", "r14", "r13" }) do
                            row[#row + 1] = string.format("%08X", (r["ARM9 " .. k] or 0) & 0xFFFFFFFF)
                        end
                        local sp = (r["ARM9 r13"] or 0) & 0xFFFFFFFF
                        if sp >= 0x01FF8000 and sp < 0x02400000 or sp >= 0x027E0000 and sp < 0x02800000 then
                            for i = 0, 23 do row[#row + 1] = string.format("%08X", memory.read_u32_le(sp + i * 4, "ARM9_System_Bus")) end
                        end
                        local f3 = io.open(path, "a")
                        f3:write(table.concat(row, " "), "\n")
                        f3:close()
                    end, tonumber(a[2]), "trace" .. a[2], D)
                elseif op == "watchread" then
                    -- watchread <addr> <path>: every ARM9 read of <addr>, append frame, pc and lr
                    local path = a[3]
                    event.onmemoryread(function()
                        local r = emu.getregisters()
                        local f3 = io.open(path, "a")
                        f3:write(string.format("%d %08X %08X\n", emu.framecount(), (r["ARM9 r15"] or 0) & 0xFFFFFFFF,
                            (r["ARM9 r14"] or 0) & 0xFFFFFFFF))
                        f3:close()
                    end, tonumber(a[2]), "watchr" .. a[2], "ARM9 System Bus")
                elseif op == "unwatch" then
                    -- unwatch <addr>: drop the callbacks watchread/watchwrite/trace added for <addr>
                    for _, k in ipairs({ "watchr", "watchw", "trace" }) do event.unregisterbyname(k .. a[2]) end
                elseif op == "holddump" then
                    -- holddump <Btn> <frames> <addr> <len> <path>: hold a button, dump memory while it is still held
                    advance(tonumber(a[3]), { [a[2]] = true })
                    local f2 = io.open(a[6], "wb")
                    local addr, len = tonumber(a[4]), tonumber(a[5])
                    local bytes = memory.read_bytes_as_array(addr, len, "ARM9 System Bus")
                    local chunk = {}
                    for i = 1, #bytes do chunk[#chunk + 1] = string.char(bytes[i]) end
                    f2:write(table.concat(chunk))
                    f2:close()
                    advance(1)
                elseif op == "watchwrite" then
                    -- watchwrite <addr> <path>: every ARM9 write to <addr>, append frame, pc, lr and r0-r3
                    local path = a[3]
                    event.onmemorywrite(function()
                        local r = emu.getregisters()
                        local row = { emu.framecount() }
                        for _, k in ipairs({ "r15", "r14", "r0", "r1", "r2", "r3" }) do
                            row[#row + 1] = string.format("%08X", (r["ARM9 " .. k] or 0) & 0xFFFFFFFF)
                        end
                        local f3 = io.open(path, "a")
                        f3:write(table.concat(row, " "), "\n")
                        f3:close()
                    end, tonumber(a[2]), "watch" .. a[2], "ARM9 System Bus")
                elseif op == "write16" then
                    -- write16 <domain> <addr> <value>
                    memory.write_u16_le(tonumber(a[3]), tonumber(a[4]), a[2])
                elseif op == "regs" then
                    -- regs: CPU registers (find where a frozen game is stuck)
                    local r = emu.getregisters()
                    local keys = {}
                    for k, _ in pairs(r) do keys[#keys + 1] = k end
                    table.sort(keys)
                    for _, k in ipairs(keys) do out[#out + 1] = k .. "=" .. string.format("%08X", r[k] & 0xFFFFFFFF) end
                elseif op == "domains" then
                    out[#out + 1] = table.concat(memory.getmemorydomainlist(), ", ")
                elseif op == "readdom" then
                    -- readdom <domain> <addr> <len>
                    local addr, len = tonumber(a[3]), tonumber(a[4])
                    local hex = {}
                    for i = 0, len - 1 do
                        hex[#hex + 1] = string.format("%02X", memory.read_u8(addr + i, a[2]))
                    end
                    out[#out + 1] = table.concat(hex, " ")
                elseif op == "read" then
                    local addr, len = tonumber(a[2]), tonumber(a[3])
                    local hex = {}
                    for i = 0, len - 1 do
                        hex[#hex + 1] = string.format("%02X", memory.read_u8(addr + i, "Main RAM"))
                    end
                    out[#out + 1] = table.concat(hex, " ")
                end
            end)
            if not ok then out[#out + 1] = "ERROR " .. line .. ": " .. tostring(err) end
        end
        out[#out + 1] = "frame " .. emu.framecount()
        write_done(out)
        if not resume then client.pause() end
    end
    -- idle without advancing the game so state only changes on command
    emu.yield()
end
