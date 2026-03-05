import argparse  # noqa: E402
from pathlib import Path  # noqa: E402

from heybrochecklog.score import score_log  # noqa: E402
from heybrochecklog.translate import translate_log  # noqa: E402

# Type hinting
from heybrochecklog.translate import TranslationDict
from heybrochecklog.logfile import LogFileDict
from argparse import Namespace
from typing import List


class UnrecognizedException(Exception):
    pass


def parse_args() -> Namespace:
    """Parse arguments."""
    description = 'Tool to analyze, translate, and score a CD Rip Log.'

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('log', help='log file to check.', nargs='+')
    parser.add_argument(
        '-t',
        '--translate',
        help='translate a foreign log to English',
        action='store_true',
    )
    parser.add_argument(
        '-m',
        '--markup',
        help='print the marked up version of the log after analyzing',
        action='store_true',
    )
    parser.add_argument(
        '-s',
        '--score-only',
        help='Only print the score of the log.',
        action='store_true',
    )
    parser.add_argument(
        '-ei',
        '--experimental-integrity',
        help='Enable Log Integrity Checking (Experimental, EAC & XLD only)',
        action='store_true',
    )

    return parser.parse_args()


def runner() -> None:
    """Main function to handle command line usage of the heybrochecklog package."""
    args = parse_args()
    for log_path in args.log:
        log_file = Path(log_path)
        if not log_file.is_file():
            print('{} does not exist.'.format(log_path))
        elif args.translate:
            translate_(args, log_file, log_path)
        elif args.log:
            score_(args, log_file, log_path)


def score_(args: Namespace, log_file: Path, log_path: str) -> None:
    log = score_log(log_file, args.markup, args.experimental_integrity)
    if args.score_only:
        if not log['unrecognized']:
            assert 'score' in log
            print(log['score'])
        else:
            print('Log is unrecognized: {}'.format(log['unrecognized']))
    else:
        try:
            print(format_score(log_path, log, args.markup))
        except UnicodeEncodeError as error:
            print('Cannot encode logpath: {}'.format(error))


def translate_(args: Namespace, log_file: Path, log_path: str) -> None:
    log = translate_log(log_file)
    try:
        print(format_translation(log_path, log))
    except UnicodeEncodeError as error:
        print('Cannot encode logpath: {}'.format(error))


def format_score(logpath: str, log: LogFileDict, markup: bool) -> str:
    """Turn a log file JSON into a pretty string."""
    output: List[str] = []
    output.append('\nLog: ' + logpath)
    if log['unrecognized']:
        output.append('\nLog is unrecognized: {}'.format(log['unrecognized']))
    else:
        if log['flagged']:
            output.append('\nLog is flagged: {}'.format(log['flagged']))
        assert 'name' in log
        output.append('\nDisc name: {}'.format(log['name']))
        assert 'score' in log
        output.append('\nScore: {}'.format(log['score']))

        assert 'deductions' in log
        if log['deductions']:
            output.append('\nDeductions:')
            for deduction in log['deductions']:
                output.append('  >>  {}'.format(deduction[0]))

        if markup:
            output.append('\n\nStylized Log:\n\n{}'.format(log['contents']))

    return '\n'.join(output)


def format_translation(logpath: str, log: TranslationDict) -> str:
    """Turn a translated log JSON into a pretty string."""
    assert 'language' in log
    assert 'log' in log

    output: List[str] = []
    output.append('\nLog: ' + logpath)

    if log['unrecognized']:
        output.append('\nFailed to recognize log. {}'.format(log['unrecognized']))
    elif log['language'] == 'english':
        output.append('\nLog is already in English!')
    else:
        output.append('\nOriginal language: {}'.format(log['language']).title())
        output.append('\n---------------------------------------------------')
        output.append('\n' + log['log'])

    return '\n'.join(output)
