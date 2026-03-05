"""This module contains the LogFile class, an encapsulation of log variables."""

import re

from heybrochecklog.resources import DEDUCTIONS

# Type hinting
from heybrochecklog.resources import DeductionTuple
from typing import Optional, Literal, List, Dict, TypedDict, Union, Required, Tuple

class LogFileDict(TypedDict, total=False):
    flagged: Required[bool]
    contents: Required[str]
    unrecognized: Required[Union[str, bool]]
    deductions: List[DeductionTuple]
    score: int
    name: Optional[str]
    ripper: Optional[Literal['EAC', 'XLD', 'EAC95']]
    version: Optional[str]

class LogFile:
    """A log file class containing variables, score, deductions, etc."""

    def __init__(
        self,
        contents: List[str],
        ripper: Optional[Literal['EAC', 'XLD', 'EAC95']] = None,
    ):

        self.full_contents = contents
        self.contents = format_full_contents(contents)
        self.concat_contents = [line for line in self.contents if line.strip()]
        self.score = 100
        self.ripper: Optional[Literal['EAC', 'XLD', 'EAC95']] = ripper
        self.language: Optional[str] = None
        self.drive: Optional[str] = None
        self.version: Optional[str] = None
        self.album: Optional[str] = None
        self.unrecognized: Optional[str] = None

        # Some other log settings
        self.range = False
        self.cdr = False
        self.unindexed_drive = False
        self.htoa = False
        self.htoa_index: Union[int, Literal[False]] = False
        self.htoa_ripped = False

        # Important parts of the log
        self.checksum = False
        self.all_tracks: Optional[int] = None
        self.deductions: Dict[str, DeductionTuple] = {}
        self.crc_mismatch: List[int] = []
        self.track_errors: Dict[str, List[Union[int, Tuple[int, int]]]] = {
            "Aborted copy": [],
            "Timing problem": [],
            "Suspicious position": [],
            "Missing samples": [],
            "Read error": [],
            "Damaged sector count": [],
        }

        # Lists of data for the log
        self.toc: Dict[int, Tuple[int, int]] = {}
        self.accuraterip: List[Tuple[str, Optional[str]]] = []
        self.track_indices: List[int] = []
        self.tracks: Dict[int, Dict[str, str]] = {}

        # Indexes of log locations
        self.index_settings: Optional[int] = None
        self.index_toc: Optional[int] = None
        self.index_tracks: Optional[int] = None
        self.index_footer: Optional[int] = None

        # Flagged = auto report log
        self.flagged: bool = False

    def to_dict(self) -> LogFileDict:
        """Return a dict of the log analysis."""
        self.unrecognized
        self.flagged
        self.full_contents

        if self.unrecognized:
            return {
                'unrecognized': self.unrecognized,
                'flagged': self.flagged,
                'contents': ''.join(self.full_contents),
            }

        deductions = [deduction for deduction in self.deductions.values()]

        return {
            'deductions': deductions,
            'flagged': self.flagged,
            'name': self.album,
            'ripper': self.ripper,
            'score': self.score,
            'version': self.version,
            'unrecognized': False,
            'contents': ''.join(self.full_contents),
        }

    def add_deduction(
        self,
        deduction: str,
        multiplier: int = 1,
        track: Optional[int] = None,
        extra_phrase: Optional[str]=None, # Never used
        cap_10: bool=False,
    ):
        """Add a deduction to the log file."""
        name, score = self._get_deduction_from_dict(deduction)
        if score:
            score = score * multiplier if not cap_10 else score * min(10, multiplier)

        if track:
            name = 'Track {}: {}'.format(track, name)
        if multiplier > 1:
            name += ' ({} occurrences)'.format(multiplier)
        if score:
            name += ' (-{} points)'.format(score)
        if extra_phrase:
            name += ' ({})'.format(extra_phrase)

        self.deductions[deduction] = (name, score)

    def _get_deduction_from_dict(self, deduction: str) -> Tuple[str, Optional[int]]:
        """Get the deduction's name and score from the deductions dict."""
        if deduction not in DEDUCTIONS:
            return (deduction, None)

        deduction_entry = DEDUCTIONS[deduction]
        # Some deductions are different per-ripper and are represented
        # with an extra embedded dictionary.
        if isinstance(deduction_entry, dict):
            if self.ripper in deduction_entry:
                deduction_entry = deduction_entry[self.ripper]
            else:
                deduction_entry = deduction_entry['Default']

        return (deduction_entry[0], deduction_entry[1])

    def remove_deduction(self, deduction: str) -> None:
        """Remove a deduction from the log file."""
        if deduction in self.deductions:
            del self.deductions[deduction]

    def has_deduction(self, deduction: str) -> bool:
        """Learn whether or not the log file has a deduction."""
        return deduction in self.deductions

    def has_deductions(self, *deductions: str) -> bool:
        """Return whether or not log has every deduction in deductions."""
        return all(de in self.deductions for de in deductions)


def format_full_contents(full_contents: List[str]) -> List[str]:
    """
    Format raw contents by stripping spaces, blank lines, and filtering
    out unicode crap.
    """
    contents = [re.sub(r'\s+', ' ', c.rstrip()) for c in full_contents]
    contents = [re.sub('：', ':', c) for c in contents]
    contents = [re.sub('，', ', ', c) for c in contents]

    return contents
