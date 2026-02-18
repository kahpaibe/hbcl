"""This module contains functions which parse lines for data."""

import re

from heybrochecklog import UnrecognizedException
from heybrochecklog.resources import VERSIONS
from heybrochecklog.shared import format_pattern as fmt_ptn

# Type hinting
from typing import List, ItemsView, Tuple
from heybrochecklog.logfile import LogFile


def index_toc(log):
    """Index the ToC data of the log."""
    re_toc = re.compile(r' ([0-9]+) \| [0-9:\.]+ \| [0-9:\.]+ \| ([0-9]+) \| ([0-9]+)')
    for line in log.contents[log.index_toc : log.index_tracks]:
        result = re_toc.search(line)
        if result:
            log.toc[int(result.group(1))] = [int(result.group(2)), int(result.group(3))]


def get_track_number(log, index, track_word) -> int:
    """Get the track number from the header line of a track block."""
    result = re.search(r'{} ([0-9]+)'.format(fmt_ptn(track_word)), log.contents[index])
    if result:
        return int(result.group(1))
    elif log.range:  # EAC range rip has no track number
        return 0
    else:
        raise UnrecognizedException('A track has an invalid block header')


def parse_settings(track_data, track_settings, line):
    """Loop through and parse the settings used in the rip."""
    for setting, reg in track_settings.items():
        result = reg.match(line)
        if result:
            track_data[setting] = result.group(1)


def parse_accuraterip(log, ar_patterns, line):
    """Parse line for an AccurateRip result."""
    for status, re_accurip in ar_patterns:
        result = re.search(fmt_ptn(re_accurip), line)
        if result and isinstance(result.lastindex, int) and result.lastindex >= 1:
            log.accuraterip.append([status, result.group(result.lastindex)])
        elif result and result.lastindex is None:
            log.accuraterip.append([status, None])


def parse_range_accuraterip(log, ar_rr_patterns):
    """Parse range rip footer for AccurateRip results."""
    for line in log.contents[log.index_footer :]:
        parse_accuraterip(log, ar_rr_patterns, line)


def parse_errors_eac(
    log: LogFile, err_patterns: ItemsView[str, List[str]], track_num: int, line: str
) -> None:
    """Parse line of an EAC log for a ripping error."""
    for error, re_err in err_patterns:
        if track_num not in log.track_errors[error] and re.match(
            r' ' + fmt_ptn(re_err), line
        ):
            log.track_errors[error].append(track_num)


def parse_errors_xld(
    log: LogFile, err_patterns: ItemsView[str, List[str]], track_num: int, line: str
) -> None:
    """Parse line of a XLD log for a ripping error."""
    for error, re_err in err_patterns:
        if track_num not in log.track_errors[error]:
            result = re.search(r' ' + fmt_ptn(re_err) + r' : ([0-9]+)', line)
            if result and result.group(1) != "0":
                log.track_errors[error].append([track_num, int(result.group(1))])


def parse_checksum(
    log: LogFile,
    regex: List[str],
    imp_version: str,
    deduc_line: str,
) -> None:
    """Parse line(s) for presence of a checksum."""
    imp_version_: Tuple[str, str] | str = (
        imp_version  # WARNING: Typing shenanigans, perhaps an artifact.
    )
    re_checksum = re.compile(fmt_ptn(regex))
    for line in log.contents[log.index_footer :]:
        if re_checksum.match(line):
            log.checksum = True
            break
    else:  # If checksum not found
        # Compare version numbers to see if Log is older than checksums.
        assert log.ripper is not None
        for version in VERSIONS[log.ripper]:
            if version[0] == log.version:
                log_version = version
            if version[0] == imp_version_:
                imp_version_ = version
        if VERSIONS[log.ripper].index(log_version) <= VERSIONS[log.ripper].index(
            imp_version_
        ):
            log.add_deduction('Checksum')
        else:
            log.add_deduction(deduc_line + ' (no checksum)')
