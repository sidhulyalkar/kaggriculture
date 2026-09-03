import tarfile

from scripts.build_v53_standalone import build


def test_v53_standalone_builder_emits_single_loader_safe_main():
    main_path, archive = build()
    source = main_path.read_text(encoding="utf-8")
    assert "__file__" not in source
    env = {}
    exec(compile(source, "main.py", "exec"), env)
    callables = [name for name, value in env.items() if callable(value)]
    assert callables[-1] == "agent"
    with tarfile.open(archive, "r:gz") as tf:
        names = [m.name for m in tf.getmembers() if m.isfile()]
    assert names == ["main.py"]
