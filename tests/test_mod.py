"""Synthetic source tests; no game script or save is a test fixture."""
import hashlib
import unittest
from unittest.mock import patch

try:
    from w3save import mod
except ImportError:
    mod = None


def synthetic_source():
    lines = [f"// synthetic source line {i}\r\n" for i in range(4530)]
    lines[75] = "\t\tif(!super.Init(ownr,cStats, isFromLoad, diff))\r\n"
    lines[76] = "\t\t\treturn false;\r\n"
    lines[4525] = "}\r\n"
    return "".join(lines).encode("utf-16")


class ModTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(mod, "The guarded local mod generator is not implemented")

    def test_unknown_or_modified_script_is_refused(self):
        with self.assertRaisesRegex(ValueError, "SHA-256|recognized|supported"):
            mod.generate_mod(synthetic_source())

    def test_additions_stay_inside_class_and_preserve_every_original_line(self):
        source = synthetic_source()
        # The real dependency here is a fixed game-file fingerprint. Substitute a
        # synthetic allowed file; parsing, insertion and output remain real.
        with patch.object(mod, "SUPPORTED_SCRIPT_SHA256", hashlib.sha256(source).hexdigest()):
            outputs = mod.generate_mod(source)
        self.assertEqual(len(outputs), 2)
        generated = outputs["modCheckpointRemasterTo404/content/scripts/game/gameplay/ability/PlayerAbilityManager.ws"]
        self.assertTrue(generated.startswith(b"\xff\xfe"))
        text = generated.decode("utf-16")
        lines = text.splitlines(keepends=True)
        self.assertEqual(lines[:77], source.decode("utf-16").splitlines(keepends=True)[:77])
        self.assertIn("if(isFromLoad && skills.Size() == 167)", "".join(lines[77:86]))
        self.assertIn("private final function MigrateInspectedRemasterCheckpoint()", text)
        restored = lines[:77] + lines[86:4534] + lines[4633:]
        self.assertEqual("".join(restored).encode("utf-16"), source)
        self.assertEqual(lines[4633], "}\r\n")
        self.assertNotIn("\n", text.replace("\r\n", ""))
        diagnostics = outputs["modCheckpointRemasterTo404/content/scripts/checkpointDiagnostics.ws"].decode("utf-8")
        self.assertIn("exec function chrpopup()", diagnostics)

    def test_already_generated_source_cannot_receive_duplicate_migration(self):
        source = synthetic_source()
        with patch.object(mod, "SUPPORTED_SCRIPT_SHA256", hashlib.sha256(source).hexdigest()):
            generated = mod.generate_mod(source)["modCheckpointRemasterTo404/content/scripts/game/gameplay/ability/PlayerAbilityManager.ws"]
        with patch.object(mod, "SUPPORTED_SCRIPT_SHA256", hashlib.sha256(generated).hexdigest()):
            with self.assertRaisesRegex(ValueError, "already|duplicate"):
                mod.generate_mod(generated)

    def test_bad_source_encoding_is_refused_even_if_fingerprint_is_allowed(self):
        source = b"synthetic UTF-8 is not the verified game encoding"
        with patch.object(mod, "SUPPORTED_SCRIPT_SHA256", hashlib.sha256(source).hexdigest()):
            with self.assertRaisesRegex(ValueError, "encoding|UTF-16"):
                mod.generate_mod(source)

    def test_wrong_anchor_is_refused_instead_of_inserting_into_wrong_code(self):
        source = synthetic_source().decode("utf-16").replace("if(!super.Init", "if(!other.Init").encode("utf-16")
        with patch.object(mod, "SUPPORTED_SCRIPT_SHA256", hashlib.sha256(source).hexdigest()):
            with self.assertRaisesRegex(ValueError, "anchor|structure"):
                mod.generate_mod(source)

    def test_class_boundary_mismatch_is_refused(self):
        source = synthetic_source().decode("utf-16").splitlines(keepends=True)
        source[4525] = "// no class boundary here\r\n"
        raw = "".join(source).encode("utf-16")
        with patch.object(mod, "SUPPORTED_SCRIPT_SHA256", hashlib.sha256(raw).hexdigest()):
            with self.assertRaisesRegex(ValueError, "anchor|structure"):
                mod.generate_mod(raw)


if __name__ == "__main__":
    unittest.main()
