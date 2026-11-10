/* Supplement the SDK linker script; fail before UF2 generation on overlap. */
ASSERT(__flash_binary_end <= 0x101de000, "Firmware overlaps song Flash partition");
