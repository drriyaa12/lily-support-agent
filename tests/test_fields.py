import unittest

from triage.fields import extract_info


class ExtractInfoTests(unittest.TestCase):
    CASES = [
        # (field, text, expected value or None)
        ("os", "edits on my MacBook (macOS 15) aren't showing", "macOS 15"),
        ("os", "Quillstack on my Windows 11 laptop", "Windows 11"),
        ("os", "Files I edit on my Mac aren't syncing", "Mac"),
        ("os", "I also tried a private window", None),
        ("invoice_number", "The invoice is INV-204518.", "INV-204518"),
        ("invoice_number", "Invoice 204518 please", None),
        ("webhook_id", "Our webhook wh_2k9d7x1p stopped", "wh_2k9d7x1p"),
        ("app_version", "I'm on version 4.8.2 now", "4.8.2"),
        ("app_version", "on macOS 15", None),
        ("account_email", "My email is priya.n@northfield-studio.example.", "priya.n@northfield-studio.example"),
    ]

    def test_table(self):
        for field, text, expected in self.CASES:
            with self.subTest(field=field, text=text):
                self.assertEqual(extract_info(text).get(field), expected)


if __name__ == "__main__":
    unittest.main()
