import contextlib
import io
import logging
import os
import tempfile

import machine
import pytest
import translator


@pytest.mark.golden_test("../golden/*.yml")
def test_translator_and_machine(golden, caplog):
    caplog.set_level(logging.INFO)

    # with tempfile.TemporaryDirectory() as tmp_dir_name:
    #     source = os.path.join(tmp_dir_name, "source.myasm")
    #     input_stream = os.path.join(tmp_dir_name, "test.txt")
    #     target = os.path.join(tmp_dir_name, "target.0")

    #     with open(source, "w", encoding="utf-8") as file:
    #         file.write(golden["in_source"])
    #     with open(input_stream, "w", encoding="utf-8") as file:
    #         file.write(golden["in_stdin"])

    #     with contextlib.redirect_stdout(io.StringIO()) as stdout:
    #         translator.main(source, target)
    #         print("============================================================")
    #         machine.main(target, input_stream)

    #     with open(target, encoding="utf-8") as file:
    #         code = file.read()

    #     assert code == golden.out["out_code"]
    #     assert stdout.getvalue() == golden.out["out_stdout"]
    #     assert caplog.text == golden.out["out_log"]

    with tempfile.TemporaryDirectory() as tmp_dir_name:
        source_text = os.path.join(tmp_dir_name, "source.text")
        source_data = os.path.join(tmp_dir_name, "source.data")
        input_stream = os.path.join(tmp_dir_name, "test.txt")
        target_t = os.path.join(tmp_dir_name, "target_t.0")
        target_d = os.path.join(tmp_dir_name, "target_d.0")

        with open(source_text, "w", encoding="utf-8") as file:
            file.write(golden["in_source_text"])
        with open(source_data, "w", encoding="utf-8") as file:
            file.write(golden["in_source_data"])
        with open(input_stream, "w", encoding="utf-8") as file:
            file.write(golden["in_stdin"])

        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            translator.main(source_text, source_data, target_t, target_d)
            print("============================================================")
            machine.main(target_t, target_d, input_stream)

        with open(target_t, encoding="utf-8") as file:
            code = file.read()
        with open(target_d, encoding="utf-8") as file:
            data = file.read()

        assert code == golden.out["out_code"]
        assert data == golden.out["out_data"]
        assert stdout.getvalue() == golden.out["out_stdout"]
        assert caplog.text == golden.out["out_log"]