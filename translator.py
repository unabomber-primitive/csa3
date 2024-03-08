from __future__ import annotations

import re
import sys

from isa import (
    SECTION_DATA,
    SECTION_TEXT,
    Commands,
    Instruction,
    Registers,
    get_data_line,
    int_to_binary,
    is_integer,
    is_string,
    op_commands,
    registers,
    write_code,
)


def remove_comment(line: str) -> str:
    return re.sub(r";.*", "", line)


def remove_spaces(line: str) -> str:
    return re.sub(r"\s+", " ", line)


def clean_text(asm_text: str) -> str:
    lines: list[str] = asm_text.splitlines()

    remove_comments = map(remove_comment, lines)
    strip_lines = map(str.strip, remove_comments)
    remove_empty_lines = filter(bool, strip_lines)
    remove_extra_spaces = map(remove_spaces, remove_empty_lines)
    cleaned_text: str = "\n".join(remove_extra_spaces)

    return cleaned_text


def parse_data_line(line: str, variable: dict[str, int]) -> tuple[str, list[int]]:
    key, value = map(str.strip, line.split(":", 1))

    constant_mem: list[int]
    if value.startswith("buf "):
        param = value.split(" ")
        if len(param) == 3:
            constant_mem = [int(param[2]) for _ in range(int(param[1]))]
        elif len(param) == 2:
            constant_mem = [0 for _ in range(int(param[1]))]
        else:
            raise ValueError(value)
    elif is_integer(value):
        constant_mem = [int(value)]
    elif is_string(value):
        string: str = value[1:-1]
        constant_mem = [ord(char) for char in string] + [0]
    else:
        constant_mem = [variable[value]]

    return key, constant_mem


def parse_data_section(code: str) -> tuple[dict[str, int], list[int]]:
    variable: dict[str, int] = {
        "JMPS": 0,
        "INT": 1,
    }
    memory: list[int] = [
        0,
        0,
    ]

    for line in code.splitlines():
        key, constant_mem = parse_data_line(line, variable)
        if key in variable:
            raise KeyError(key)
        variable[key] = len(memory)
        memory.extend([constant for constant in constant_mem])

    return variable, memory


def get_binary_line(line: str) -> str:
    words: list[str] = line.split(" ")
    op_code = format(op_commands.index(Commands(words[0])), "08b")
    for word in words[1:]:
        arg: str
        if word.startswith("%"):
            arg = format(1, "04b") + format(registers.index(Registers(word[1:])), "032b")
        elif word.startswith("#"):
            arg = format(2, "04b") + format(int(word[1:]), "032b")
        elif word.startswith("!"):
            arg = format(3, "04b") + format(int(word[1:]), "032b")
        elif word.startswith("*"):
            arg = format(4, "04b") + format(int(word[1:]), "032b")
        else:
            arg = format(0, "04b") + int_to_binary(int(word))
        op_code += arg

    for _ in range(3 - len(words)):
        op_code += format(0, "036b")

    return op_code


def generate_binary(code: list[str], data: list[int]):
    binary_data: list[Instruction] = []
    binary_text: list[Instruction] = []
    cur: int = 0

    for line in data:
        binary_data.append(Instruction(cur, get_data_line(line), str(line)))
        cur += 1
    cur = 0
    for line1 in code:
        binary_text.append(Instruction(cur, get_binary_line(line1), line1))
        cur += 1

    return binary_data, binary_text


def address_line(lines: list[str], labels: dict[str, int], variable: dict[str, int]):
    for index, line in enumerate(lines):
        words = line.split(" ")
        if len(words) == 1:
            continue

        ans: str
        ans = words[0]
        for word in words[1:]:
            if is_integer(word) or word.startswith("%") or word.startswith("!"):
                ans += " " + word
            elif word.startswith("#"):
                ans += " #" + str(variable[word[1:]])
            elif word.startswith("."):
                ans += " " + str(labels[word])
            elif word.startswith("*"):
                ans += " *" + str(variable[word[1:]])
            else:
                name, offset = word.split("[")
                ans += " #" + str(variable[name] + int(offset[:-1]))
        lines[index] = ans

    return lines


def parse_text_section(variable: dict[str, int], code: str, cur: int):
    lines: list[str] = []
    labels: dict[str, int] = {}

    for line in code.splitlines():
        if line.startswith("."):
            name, command = map(str.strip, line.split(":", 1))
            labels[name] = cur
            line = command

        string = line.split(" ")
        if len(string) <= 3:
            lines.append(line)
        else:
            name, arg_s, *args = string
            lines.extend([name + " " + arg_s + " " + arg for arg in args])
            cur += len(args) - 1

        cur += 1

    return address_line(lines, labels, variable)


def translate(code: str):
    text_index: int = code.find(SECTION_TEXT)
    data_index: int = code.find(SECTION_DATA)

    variable, memory = parse_data_section(code[data_index + len(SECTION_DATA) + 1 : text_index])
    memory[0] = len(memory)
    text_code = parse_text_section(variable, code[text_index + len(SECTION_DATA) + 1 :], 0)
    return generate_binary(text_code, memory)


def main(source_text_file, source_data_file, target_text_file, target_data_file):
    with open(source_data_file, encoding="utf-8") as f:
        source_file = f.read()
    with open(source_text_file, encoding="utf-8") as f:
        source_file += "\n" + f.read()

    source_file = clean_text(source_file)
    data, text = translate(source_file)

    write_code(data, target_data_file)
    write_code(text, target_text_file)
    print("source LoC:", len(source_file.split("\n")), "code instr:", len(text))


if __name__ == "__main__":
    assert (
        len(sys.argv) == 5
    ), "Wrong arguments: translator.py <input_text_file> <input_data_file> <target_text_file> <target_data_file>"
    _, source_text, source_data, target_text, target_data = sys.argv
    main(source_text, source_data, target_text, target_data)
