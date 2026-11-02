/* Gunk's code home: an extra ARM9 autoload block that crt0 copies to 0x023C0000 at boot (see patches.code_home).
   The main arena's top is lowered to the same address, so the game's heaps never reach it. Functions named Gunk_*
   and tables named gGunk* are what patches.py points the game at, so they are kept although nothing here uses them. */
MEMORY { home (rwx) : ORIGIN = 0x023C0000, LENGTH = 128K }
SECTIONS {
    .text : { KEEP(*(.gunk_info)) KEEP(*(.text.Gunk_*)) KEEP(*(.rodata.gGunk*)) *(.text*) *(.rodata*) *(.data*) . = ALIGN(4); } > home
    .bss (NOLOAD) : { __bss_start = .; *(.bss*) *(COMMON) . = ALIGN(4); __bss_end = .; } > home
    /DISCARD/ : { *(.ARM.*) *(.comment) }
}
