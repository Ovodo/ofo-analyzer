# OFO Analyzer test report — 2026-11-01

Executed on the development machine (Linux, Python 3.13.12, pytest 9.2.0)
with PortAudio installed and a USB audio interface present. Verbatim output:

```
============================= test session starts ==============================
platform linux -- Python 3.13.12, pytest-9.2.0, pluggy-1.7.0
rootdir: /home/ovd/projects/ofo-analyzer
configfile: pyproject.toml
testpaths: tests
collected 49 items

tests/test_device.py ......                                              [ 12%]
tests/test_export.py ..                                                  [ 16%]
tests/test_level.py ....                                                 [ 24%]
tests/test_metadata.py ....                                              [ 32%]
tests/test_recording.py .....                                            [ 42%]
tests/test_spectrogram.py .......                                        [ 57%]
tests/test_spectrum.py ...........                                       [ 79%]
tests/test_synthetic.py .....                                            [ 89%]
tests/test_ui_smoke.py ..                                                [ 93%]
tests/test_windows.py ...                                                [100%]

============================== 49 passed in 7.82s ==============================
```
