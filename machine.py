from __future__ import annotations

import logging
import sys
from typing import Callable

from isa import (
    MAX_MEMORY,
    MAX_NUM,
    Command,
    Commands,
    Registers,
    alu_commands,
    binary_to_hex,
    branch_commands,
    get_data_line,
    is_integer,
    op_commands,
    read_code,
    registers,
    two_op_commands,
    zero_op_commands,
)

ALU_OP_HANDLERS: dict[int, Callable[[int, int], int]] = {
    op_commands.index(Commands.add): lambda left, right: left + right,
    op_commands.index(Commands.sub): lambda left, right: left - right,
    op_commands.index(Commands.mod): lambda left, right: left % right,
    op_commands.index(Commands.div): lambda left, right: left // right,
    op_commands.index(Commands.mul): lambda left, right: left * right,
    op_commands.index(Commands.xor): lambda left, right: left ^ right,
    op_commands.index(Commands.and_): lambda left, right: left & right,
    op_commands.index(Commands.or_): lambda left, right: left | right,
    op_commands.index(Commands.cmp): lambda left, right: left - right,
}


class ALU:
    def __init__(self):
        self.N = 0
        self.Z = 1
        self.OF = 0

    def __str__(self):
        return f"N: {self.N} Z: {self.Z} OF: {self.OF}"

    def perform(self, op: int, left: int, right: int) -> int:
        handler = ALU_OP_HANDLERS[op]
        value = handler(left, right)
        value = self.handle_overflow(value)
        self.set_flags(value)
        return value

    def set_flags(self, value) -> None:
        self.Z = int(value == 0)
        self.N = int(value < 0)

    def handle_overflow(self, value: int) -> int:
        if value >= MAX_NUM:
            self.OF = 1
            return value - MAX_NUM
        if value <= -MAX_NUM:
            self.OF = 1
            return value + MAX_NUM
        self.OF = 0
        return value


class DataPath:
    memory: list[str]
    alu: ALU = ALU()
    ports: dict[int, list[str | tuple[int, str]]]

    def __init__(self, data_memory, data_memory_size, ports, start_addr):
        assert data_memory_size > len(data_memory), "Data_memory size should be more"
        self.data_memory_size = data_memory_size
        self.memory = data_memory + [format(0, "020x")] * (data_memory_size - len(data_memory))
        self.ports = ports
        self.reg = {name: 0 for name in registers}
        self.set_reg(Registers.rip, start_addr)
        self.set_reg(Registers.rsp, data_memory_size - 1)
        self.prev = format(0, "020x")

    def __str__(self):
        return self.prev

    def get_reg(self, reg: Registers) -> int:
        return self.reg[reg]

    def set_reg(self, reg: Registers, val: int) -> None:
        self.reg[reg] = val

    def reg_add(self, reg: Registers, val: int) -> None:
        self.reg[reg] += val

    def wr(self, addr: int, value: int) -> None:
        self.memory[addr] = binary_to_hex(get_data_line(value))

    def wr_port(self, port: int, val: int) -> None:
        self.ports[port].append(chr(val))
        logging.info(
            "OUTPUT: "
            + str(self.ports[port][:-1])
            + " <- "
            + (str(self.ports[port][-1]) if str(self.ports[port][-1]) != "\n" else "\\n")
        )

    def rd(self, reg: Registers, addr: int) -> None:
        self.set_reg(reg, Command(self.memory[addr]).arg1_value)

    def rd_port(self, port: int, addr: int) -> None:
        if is_integer(str(self.ports[port][0][1])):
            logging.info("INPUT: " + str(self.ports[port][0][1]))
            self.memory[addr] = binary_to_hex(get_data_line(int(self.ports[port].pop(0)[1])))
        else:
            logging.info("INPUT: " + (self.ports[port][0][1] if self.ports[port][0][1] != "\n" else "\\n"))
            self.memory[addr] = binary_to_hex(get_data_line(ord(self.ports[port].pop(0)[1])))

    def latch_ip(self, value: int = -1):
        self.prev = self.memory[self.get_reg(Registers.rip)]
        if value >= 0:
            self.set_reg(Registers.rip, value - 1)
        else:
            self.set_reg(Registers.rip, self.get_reg(Registers.rip) + 1)

    def get_instruction(self) -> str:
        return self.memory[self.get_reg(Registers.rip)]

    def get_arg(self, arg_type: int, val: int = 0) -> int:
        if arg_type == 0:
            return val
        if arg_type == 1:
            return self.get_reg(registers[val])
        if arg_type == 2:
            return Command(self.memory[val]).arg1_value
        if arg_type == 4:
            return self.get_arg(2, Command(self.memory[val]).arg1_value)

        return 0

    def get_addr(self, arg_type: int, val: int) -> int:
        if arg_type == 2:
            return val
        if arg_type == 4:
            return Command(self.memory[val]).arg1_value

        return 0


class ControlUnit:
    def __init__(self, data_path, limit):
        self.data_path = data_path
        self.instr_counter = 0
        self._tick = 0
        self.limit = limit
        self.command = Commands.nop
        self.mode = ""

    def tick(self):
        self._tick += 1

    def current_tick(self):
        return self._tick

    def command_cycle(self):
        logging.info("%s", self)
        try:
            while self.instr_counter < self.limit:
                self.decode_and_execute_instruction()
                self.data_path.latch_ip()
                logging.info("%s", self)
                self.instr_counter += 1
                self.interruption_cycle()
        except EOFError:
            logging.warning("Input buffer is empty!")
        except StopIteration:
            logging.info("%s", self)

        if self.instr_counter >= self.limit:
            logging.warning("Limit exceeded!")

    def update_interruption_state(self):
        input_port = self.data_path.ports[0]
        if len(input_port) and input_port[0][0] <= self.current_tick():
            self.data_path.set_reg(Registers.rst, self.data_path.get_reg(Registers.rst) | 2)

    def execute_interruption(self):
        self.mode = "TRAP:"
        self.data_path.set_reg(Registers.rst, 0)
        self.tick()

        self.data_path.wr(self.data_path.get_reg(Registers.rsp), self.data_path.get_reg(Registers.rip))
        self.data_path.reg_add(Registers.rsp, -1)
        self.tick()

        self.data_path.wr(self.data_path.get_reg(Registers.rsp), self.data_path.get_reg(Registers.rax))
        self.data_path.reg_add(Registers.rsp, -1)
        self.tick()

        self.data_path.rd(Registers.rip, 1)
        self.tick()

    def decode_and_execute_control_zero_arg_instruction(self, opcode):
        if opcode == Commands.ei:
            self.data_path.set_reg(Registers.rst, self.data_path.get_reg(Registers.rst) | 1)
            self.tick()
        if opcode == Commands.di:
            self.data_path.set_reg(Registers.rst, self.data_path.get_reg(Registers.rst) & ~1)
            self.tick()
        if opcode == Commands.iret:
            self.mode = ""
            self.data_path.reg_add(Registers.rsp, 1)
            self.data_path.rd(Registers.rax, self.data_path.get_reg(Registers.rsp))
            self.tick()

            self.data_path.reg_add(Registers.rsp, 1)
            self.data_path.rd(Registers.rip, self.data_path.get_reg(Registers.rsp))
            self.data_path.reg_add(Registers.rip, -1)
            self.tick()

            self.data_path.set_reg(Registers.rst, self.data_path.get_reg(Registers.rst) | 1)
            self.tick()

    def decode_and_execute_control_two_arg_instruction(self, instr, opcode):
        if opcode in alu_commands:
            if instr.arg1_type == 1:
                left = self.data_path.get_arg(instr.arg1_type, instr.arg1_value)
                right = self.data_path.get_arg(instr.arg2_type, instr.arg2_value)

                res = self.data_path.alu.perform(instr.command_type, left, right)
                if opcode != Commands.cmp:
                    self.data_path.set_reg(registers[instr.arg1_value], res)
                    self.tick()
            else:
                left = self.data_path.get_arg(instr.arg1_type, instr.arg1_value)
                self.tick()
                right = self.data_path.get_arg(instr.arg2_type, instr.arg2_value)
                self.tick()

                res = self.data_path.alu.perform(instr.command_type, left, right)
                if opcode != Commands.cmp:
                    self.data_path.wr(instr.arg1_value, res)
                    self.tick()
        if opcode == Commands.mov:
            if instr.arg1_type == 1:
                right = self.data_path.get_arg(instr.arg2_type, instr.arg2_value)
                self.data_path.alu.set_flags(right)
                self.data_path.set_reg(registers[instr.arg1_value], right)
                self.tick()
            elif instr.arg2_type == 1:
                right = self.data_path.get_arg(instr.arg2_type, instr.arg2_value)
                self.data_path.wr(instr.arg1_value, right)
                self.tick()
            else:
                right = self.data_path.get_arg(instr.arg2_type, instr.arg2_value)
                self.tick()

                self.data_path.wr(self.data_path.get_addr(instr.arg1_type, instr.arg1_value), right)
                self.tick()
        if opcode == Commands.movo:
            self.data_path.wr_port(instr.arg1_value, self.data_path.get_arg(instr.arg2_type, instr.arg2_value))
            self.tick()
        if opcode == Commands.movi:
            self.data_path.rd_port(instr.arg2_value, instr.arg1_value)
            self.tick()

    def decode_and_execute_control_flow_instruction(self, instr, opcode):
        if opcode == Commands.jmp:
            self.data_path.latch_ip(instr.arg1_value)
            self.tick()

        if opcode == Commands.jz:
            if self.data_path.alu.Z:
                self.data_path.latch_ip(instr.arg1_value)
            self.tick()

        if opcode == Commands.jnz:
            if not self.data_path.alu.Z:
                self.data_path.latch_ip(instr.arg1_value)
            self.tick()

        if opcode == Commands.jn:
            if self.data_path.alu.N:
                self.data_path.latch_ip(instr.arg1_value)
            self.tick()

        if opcode == Commands.jp:
            if not self.data_path.alu.N:
                self.data_path.latch_ip(instr.arg1_value)
            self.tick()

    def decode_and_execute_instruction(self):
        instr = Command(self.data_path.get_instruction())
        opcode = op_commands[instr.command_type]
        self.tick()
        self.command = instr

        if opcode == Commands.hlt:
            raise StopIteration()

        if opcode in branch_commands:
            self.decode_and_execute_control_flow_instruction(instr, opcode)

        if opcode in two_op_commands:
            self.decode_and_execute_control_two_arg_instruction(instr, opcode)

        if opcode in zero_op_commands:
            self.decode_and_execute_control_zero_arg_instruction(opcode)

    def interruption_cycle(self):
        self.update_interruption_state()
        if self.data_path.get_reg(Registers.rst) & 1 and self.data_path.get_reg(Registers.rst) >> 1 & 1:
            self.execute_interruption()

    def __repr__(self):
        register_values = ", ".join(f"{name}: {value}" for name, value in self.data_path.reg.items())
        return (
            f"{self.mode}Tick: {self.current_tick()} | Registers: {register_values} "
            f"Flags: {self.data_path.alu} | Instruction: {self.command}"
        )


def simulation(code, input_tokens, memory_size, limit, start_addr):
    data_path = DataPath(code, memory_size, {0: input_tokens, 1: []}, start_addr)
    control_unit = ControlUnit(data_path, limit)
    control_unit.command_cycle()
    logging.info("output_buffer: %s", repr("".join(data_path.ports[1])))
    return "".join(data_path.ports[1]), control_unit.instr_counter, control_unit.current_tick()


def main(codes_file, inputs_file):
    with open(inputs_file, encoding="utf-8") as file:
        input_text = file.read()
        if not input_text:
            input_token = []
        else:
            input_token = eval(input_text)

    start_addr, code = read_code(codes_file)
    output, instr_counter, ticks = simulation(
        code, input_tokens=input_token, memory_size=MAX_MEMORY, limit=20000, start_addr=start_addr
    )

    print("".join(output))
    print("instr_counter: ", instr_counter, "ticks:", ticks)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    assert len(sys.argv) == 3, "Wrong arguments: machine.py <code_file> <input_file>"
    _, code_file, input_file = sys.argv
    main(code_file, input_file)
