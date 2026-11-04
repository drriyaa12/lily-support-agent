import unittest

from lily.fields import extract_info


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
        # Review finding: an OS version is not the app version, and "browser windows" is not an OS.
        ("app_version", "I'm on macOS 14.2.1 and the app crashes", None),
        ("os", "I'm on macOS 14.2.1 and the app crashes", "macOS 14.2"),
        ("app_version", "Quillstack 4.6.2 on macOS 14.2.1", "4.6.2"),
        ("os", "I have too many browser windows open", None),
        ("os", "the desktop app on Windows keeps crashing", "Windows"),
        # Final check: a capitalised Windows is the OS; a codename between OS and version is still the OS.
        ("os", "Windows here, and the desktop app won't sync", "Windows"),
        ("app_version", "macOS Sonoma 14.2.1, and the app keeps crashing", None),
    ]

    def test_table(self):
        for field, text, expected in self.CASES:
            with self.subTest(field=field, text=text):
                self.assertEqual(extract_info(text).get(field), expected)


if __name__ == "__main__":
    unittest.main()
