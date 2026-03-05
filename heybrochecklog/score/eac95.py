"""This module contains the EAC Version <=0.95 Log Checker."""

import re

from heybrochecklog import UnrecognizedException
from heybrochecklog.markup import markup
from heybrochecklog.score.logchecker import LogChecker
from heybrochecklog.score.modules import combined, drives, parsers, validation
from heybrochecklog.shared import format_pattern as fmt_ptn

# Type hinting
from heybrochecklog.logfile import LogFile
from typing_extensions import override
from typing import Dict
from re import Pattern


class EAC95Checker(LogChecker):
    """This class analyzes <=0.95 EAC Log Files."""

    def check(self, main_log: LogFile, integrity: bool = False) -> LogFile:
        """Checks the EAC logs."""
        logs = combined.split_combined(main_log)
        for log in logs:
            if len(log.concat_contents) < 12:
                raise UnrecognizedException('Cannot parse log file; log file too short')

            log.version = 'EAC <=0.95'
            log.album = log.concat_contents[1]
            log.drive = self.check_drive(log)

            self.index_log(log, ninety_five=True)
            self.evaluate_settings(log)
            self.check_tracks(log)
            if self.markup:
                assert self.translation is not None
                markup(log, self.patterns, self.translation)

        main_log = combined.defragment(logs, eac95=True)
        validation.validate_track_settings(main_log)
        self.deduct_and_score(main_log)

        return main_log

    def check_drive(self, log: LogFile) -> str:
        """Check the drive of the log and verify it is an allowed drive."""
        regex = r' ?: (.*) Adapter:[ 0-9]+ID:[ 0-9]+$'
        return self.get_drive(regex, log.concat_contents[2])

    @override
    def all_range_index(self, log: LogFile, line: str) -> bool:
        """Match the Range Rip line in the log file."""
        assert self.patterns['range'] is not None
        if log.index_tracks is None and re.match(fmt_ptn(self.patterns['range']), line):
            return True
        return False

    @override
    def all_range_index_action(self, log: LogFile, line_num: int) -> None:
        """Action to take when the range rip line is matched."""
        log.track_indices.append(line_num)
        log.range = True

    @override
    def evaluate_settings(self, log: LogFile) -> None:
        """Evaluate the log for usage of proper rip settings.
        Overwriting the base class for different 0.95 behavior.
        """
        assert self.patterns['full line settings'] is not None
        psettings = self.patterns['settings']
        full_psettings = self.patterns['full line settings']
        proper_settings = self.patterns['proper settings']

        # Compile regex beforehand
        settings: Dict[str, Pattern[str]] = {}
        full_settings: Dict[str, Pattern[str]] = {}
        for key, regex in psettings.items():
            settings[key] = re.compile(fmt_ptn(regex))
        for key, regex in full_psettings.items():
            full_settings[key] = re.compile(fmt_ptn(regex) + ' : (.*)')

        # Iterate through line in the settings, and verify each setting in `settings` dict
        for line in log.contents[log.index_settings : log.index_tracks]:
            for key, setting in list(settings.items()):
                result = setting.search(line)
                if result:
                    if key == 'Drive offset':
                        offset = re.search(r'.+: ([-0-9]+)', line)
                        assert offset is not None
                        drives.eval_offset(log, offset.group(1))
                    del settings[key]
            for key, setting in list(full_settings.items()):
                result = setting.search(line)
                if result:
                    if not re.search(fmt_ptn(proper_settings[key]), result.group(1)):
                        log.add_deduction(key)
                    del full_settings[key]
                    break

            self.check_bad_settings(log, line)

        self.evaluate_unmatched_settings(log, settings)

    def check_offset(
        self, log: LogFile, line: str, off_settings: Dict[str, Pattern[str]]
    ) -> bool:
        """Check a log file line for proper offset."""
        found = False
        for key, setting in off_settings.items():
            result = setting.search(line)
            if result:
                if key == 'Combined offset':
                    log.add_deduction('Combined offset')
                else:
                    drives.eval_offset(log, result.group(1))
                found = True

        return found

    @override
    def check_bad_settings(self, log: LogFile, line: str) -> None:
        """Evaluate the instant -100 point deductions
        (destructive normalization and compression offset)."""
        assert self.patterns['bad settings'] is not None
        bad_settings = self.patterns['bad settings']
        for sett, pattern in bad_settings.items():
            if re.search(fmt_ptn(pattern), line):
                log.add_deduction(sett)

    @override
    def evaluate_unmatched_settings(
        self, log: LogFile, settings: Dict[str, Pattern[str]]
    ) -> None:
        """Evaluate all unmatched settings and deduct for them.
        <=0.95 is using a match/no match string algorithm, so it's a deduction if no match.
        """
        if log.has_deduction('Combined offset') and 'Drive offset' in settings:
            del settings['Drive offset']
        for key in settings:
            log.add_deduction(key)

    def check_tracks(self, log: LogFile) -> None:
        """Get track data for each track and check for errors."""
        tsettings = self.patterns['track settings']
        track_settings = {
            'filename': re.compile(r' ' + fmt_ptn(tsettings['filename']) + r' (.*)'),
            'pregap': re.compile(r' ' + fmt_ptn(tsettings['pregap']) + r' ([0-9:\.]+)'),
            'peak': re.compile(r' ' + fmt_ptn(tsettings['peak']) + r' ([0-9\.])+ %'),
            'test crc': re.compile(
                r' ' + fmt_ptn(tsettings['test crc']) + r' ([A-Z0-9]{8})'
            ),
            'copy crc': re.compile(
                r' ' + fmt_ptn(tsettings['copy crc']) + r' ([A-Z0-9]{8})'
            ),
        }

        self.analyze_tracks(
            log, track_settings, parsers.parse_errors_eac, accuraterip=False
        )

    @override
    def evaluate_tracks(self, log: LogFile) -> None:
        """Evaluate the analyzed track data for deficiencies."""
        # Deduct for a Range Rip
        if log.range:
            log.add_deduction('Range rip')

    @override
    def deduct_and_score(self, log: LogFile, integrity: bool = False) -> None:
        """Process the accumulated deductions and score the log file."""
        # EAC <=0.95 mandatory deductions.
        log.add_deduction('EAC 0.95')
        log.add_deduction('EAC <1.0 (no checksum)')
        if not log.range:
            log.add_deduction('Gap handling')
        else:
            log.add_deduction('Could not verify gap handling')

        # Deduct for all the per-track accumulated deductions.
        for error in log.track_errors:
            if log.track_errors[error]:
                log.add_deduction(error, len(log.track_errors[error]))

        super().deduct_and_score(log)
