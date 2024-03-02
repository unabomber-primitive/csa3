from __future__ import annotations

import re
from enum import Enum
from typing import Final


class Registers(str, Enum):
    rax = "rax"
    rbx = "rbx"
    rdx = "rdx"
    rip = "rip"
    rst = "rst"
    rsp = "rsp"

    def __str__(self) -> str:
        return self.value


class Commands(str, Enum):
    jmp = "jmp"
    jz = "jz"
    jnz = "jnz"
    jn = "jn"
    jp = "jp"
    add = "add"
    sub = "sub"
    mul = "mul"
    div = "div"
    mod = "mod"
    xor = "xor"
    and_ = "and"
    or_ = "or"
    cmp = "cmp"
    mov = "mov"
    movi = "movi"
    movo = "movo"
    iret = "iret"
    di = "di"
    ei = "ei"
    hlt = "hlt"
    nop = "nop"

    def __str__(self) -> str:
        return self.value


registers: list[Registers] = [Registers.rax, Registers.rbx, Registers.rdx, Registers.rip, Registers.rst, Registers.rsp]
branch_commands: list[Commands] = [Commands.jmp, Commands.jz, Commands.jnz, Commands.jn, Commands.jp]
alu_commands: list[Commands] = [
    Commands.add,
    Commands.sub,
    Commands.mul,
    Commands.div,
    Commands.mod,
    Commands.xor,
    Commands.and_,
    Commands.or_,
    Commands.cmp,
]
two_op_commands: list[Commands] = [*alu_commands, Commands.mov, Commands.movi, Commands.movo]
one_op_commands: list[Commands] = branch_commands
zero_op_commands: list[Commands] = [Commands.iret, Commands.di, Commands.ei, Commands.hlt]
op_commands: list[Commands] = [Commands.nop, *two_op_commands, *one_op_commands, *zero_op_commands]

RE_STR: Final = r"^(\'.*\')|(\".*\")$"
SECTION_TEXT: Final = "section .text"
SECTION_DATA: Final = "section .data"
MAX_NUM: Final = 1 << 31
MAX_MEMORY: Final = 1 << 11


class Instruction:
    def __init__(self, address: int, binary_code: str, mnemonic: str):
        self.address = address
        self.binary_code = binary_code
        self.mnemonic = mnemonic

    def __str__(self):
        return f"{self.address} {binary_to_hex(self.binary_code)} {self.mnemonic}"


def get_type_address(addr_type: int, arg: int) -> str:
    if addr_type == 0:
        return str(arg)
    if addr_type == 1:
        return "%" + registers[arg]
    if addr_type == 2:
        return "#" + str(arg)
    if addr_type == 3:
        return "!" + str(arg)
    return "*" + str(arg)


class Command:
    def __init__(self, hex_string):
        self.hex_string = hex_string
        self.command_type, self.arg1_type, self.arg1_value, self.arg2_type, self.arg2_value = parse_command(hex_string)

    def __str__(self):
        if op_commands[self.command_type] in two_op_commands:
            return (
                f"{op_commands[self.command_type]} {get_type_address(self.arg1_type, self.arg1_value)} "
                f"{get_type_address(self.arg2_type, self.arg2_value)}"
            )
        if op_commands[self.command_type] in one_op_commands:
            return f"{op_commands[self.command_type]} {get_type_address(self.arg1_type, self.arg1_value)}"

        return f"{op_commands[self.command_type]}"


def is_integer(string: str) -> bool:
    return bool(re.match(r"^-?\d+$", string))


def is_string(string: str) -> bool:
    return bool(re.fullmatch(RE_STR, string))


def int_to_binary(n: int) -> str:
    if n >= 0:
        binary = format(n, "032b")
    else:
        binary = format(n & 0xFFFFFFFF, "032b")

    return binary


def binary_to_hex(binary_code: str) -> str:
    return format(int(binary_code, 2), "020x")


def get_data_line(line: int) -> str:
    return format(0, "012b") + int_to_binary(line) + format(0, "036b")


def binary_to_integer(binary: str) -> int:
    if binary[0] == "1":
        complement = "".join(["1" if x == "0" else "0" for x in binary])
        integer = -(int(complement, 2) + 1)
    else:
        integer = int(binary, 2)

    return integer


def parse_command(hex_string):
    command = hex_string[:2]
    data = hex_string[2:]

    command_type = int(command, 16)
    arg1_type = int(data[:1], 16)
    arg1_value = binary_to_integer(format(int(data[1:9], 16), "032b"))
    arg2_type = int(data[9:10], 16)
    arg2_value = binary_to_integer(format(int(data[10:18], 16), "032b"))

    return command_type, arg1_type, arg1_value, arg2_type, arg2_value


def write_code(instructions: list[Instruction], source: str):
    with open(source, "w") as file:
        for instruction in instructions:
            file.write(str(instruction) + "\n")


def read_code(filename: str):
    instr: list[str] = []

    with open(filename, encoding="utf-8") as file:
        code = file.read()

    for line in code.splitlines():
        instr.append(line.split(" ")[1])

    start_addr = parse_command(instr[0])[2]

    return start_addr, instr
