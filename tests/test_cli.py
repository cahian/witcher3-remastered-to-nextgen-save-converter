"""CLI safety checks using temporary synthetic files only."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'w3save', *map(str, args)],
                              capture_output=True, text=True)

    def test_help_exposes_documented_workflow(self):
        result = self.run_cli('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in ('inspect', 'prepare', 'make-mod', 'finalize', 'audit'):
            self.assertIn(command, result.stdout)

    def test_invalid_input_fails_cleanly_without_creating_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source.sav'
            output = Path(directory)/'candidate.sav'
            source.write_bytes(b'not a save')
            result = self.run_cli('prepare', source, '--output', output)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertFalse(output.exists())
            self.assertEqual(source.read_bytes(), b'not a save')

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source.sav'
            output = Path(directory)/'candidate.sav'
            source.write_bytes(b'source')
            output.write_bytes(b'valuable existing save')
            result = self.run_cli('prepare', source, '--output', output)
            self.assertEqual(result.returncode, 2)
            self.assertIn('exist', result.stderr.lower())
            self.assertEqual(output.read_bytes(), b'valuable existing save')

    def test_output_symlink_is_never_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source.sav'
            output = Path(directory)/'candidate.sav'
            source.write_bytes(b'valuable source')
            try:
                output.symlink_to(source)
            except OSError:
                self.skipTest('symlinks unavailable')
            result = self.run_cli('prepare', source, '--output', output)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(source.read_bytes(), b'valuable source')
            self.assertTrue(output.is_symlink())

    def test_missing_file_is_a_clean_error(self):
        result = self.run_cli('inspect', '/a-nonexistent-save-fixture.sav')
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Traceback', result.stderr)

    def test_bad_game_script_does_not_leave_a_generated_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'script.ws'
            output = Path(directory)/'generated'
            source.write_text('unrecognized game script')
            result = self.run_cli('make-mod', '--game-script', source, '--output-dir', output)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())

    def test_fact_audit_reports_loss_additions_and_changes(self):
        from w3save.cli import compare_facts
        def fact(value, created=1.0):
            return {'flag': 0, 'total': value,
                    'entries': [{'value': value, 'created': created, 'expires': -1.0}]}
        before = {'missing': fact(1), 'changed': fact(2), 'time': fact(1)}
        after = {'added': fact(1), 'changed': fact(3), 'time': fact(1, 2.0)}
        report = compare_facts(before, after)
        self.assertEqual(report['missing'], {'missing': fact(1)})
        self.assertEqual(report['added'], {'added': fact(1)})
        self.assertEqual(set(report['changed']), {'changed', 'time'})
        self.assertEqual(report['changed']['changed']['before']['total'], 2)
        self.assertEqual(report['changed']['changed']['after']['total'], 3)
        self.assertFalse(report['all_original_records_unchanged'])

    def test_fact_audit_does_not_certify_absent_fact_data(self):
        from w3save.cli import compare_facts
        report = compare_facts({}, {})
        self.assertFalse(report['data_available'])
        self.assertFalse(report['all_original_records_unchanged'])

    def test_fact_audit_distinguishes_preservation_from_native_additions(self):
        from w3save.cli import compare_facts
        fact = {'flag': 0, 'total': 1, 'entries': []}
        report = compare_facts({'old': fact}, {'old': fact, 'new': fact})
        self.assertTrue(report['all_original_records_unchanged'])
        self.assertEqual(report['original_count'], 1)
        self.assertEqual(report['candidate_count'], 2)
        self.assertEqual(report['added'], {'new': fact})


if __name__ == '__main__':
    unittest.main()
