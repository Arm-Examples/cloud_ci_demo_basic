#!/usr/bin/python3

import re

from enum import Enum
from io import StringIO
from junit_xml import TestSuite, TestCase, to_xml_report_string
from pathlib import Path
from typing import AnyStr, Tuple

from matrix_runner import main, matrix_axis, matrix_action, matrix_command, ConsoleReport, CropReport, ReportFilter

class UnityReport(ReportFilter):
    class Result(ReportFilter.Result, ReportFilter.Summary):
        @property
        def stream(self) -> StringIO:
            if not self._stream:
                try:
                    self._stream = StringIO()
                    input = self._other.stream
                    input.seek(0)
                    tcs = []
                    for line in input:
                        m = re.match('(.*):(\d+):(\w+):(PASS|FAIL)(:(.*))?', line)
                        if m:
                            tc = TestCase(m.group(3), file=Path(m.group(1)).relative_to(Path.cwd()), line=m.group(2))
                            if m.group(4) == "FAIL":
                                tc.add_failure_info(message=m.group(6).strip())
                            tcs += [tc]
                    self.ts = TestSuite("Cloud-CI basic tests", tcs)
                    self._stream.write(to_xml_report_string([self.ts]))
                except Exception as e:
                    self._stream = e
            if isinstance(self._stream, Exception):
                raise RuntimeError from self._stream
            else:
                return self._stream

        @property
        def summary(self) -> Tuple[int, int]:
            passed = len([tc for tc in self.ts.test_cases if not (tc.is_failure() or tc.is_error() or tc.is_skipped())])
            executed = len(self.ts.test_cases)
            return passed, executed

    def __init__(self, *args):
        super(UnityReport, self).__init__()
        self.args = args

@matrix_axis("target", "t", "The project target(s) to build.")
class TargetAxis(Enum):
    debug = ('debug')


@matrix_action
def cbuild(config):
    """Build the config(s) with CMSIS-Build"""
    yield run_cbuild(config)

@matrix_action
def fvp(config, results):
    """Run the config(s) with virtual hardware."""
    yield run_fvp(config)
    results[0].test_report.write(f"basic.junit")

@matrix_command(needs_shell=True)
def run_cbuild(config):
    return ["bash", "-c", f"'source $(dirname $(which cbuild.sh))/../etc/setup; cbuild.sh basic.{config.target}.cprj'"]

@matrix_command(test_report=ConsoleReport()|CropReport("---\[ UNITY BEGIN \]---", '---\[ UNITY END \]---')|UnityReport())
def run_fvp(config):
    return ["FVP_Corstone_SSE-300_Ethos-U55", "-q", "--cyclelimit", "100000000", "-f", "fvp_config.txt", "Objects/basic.axf"]

if __name__ == "__main__":
    main()
