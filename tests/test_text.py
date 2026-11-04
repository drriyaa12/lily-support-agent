import unittest

from lily.text import sentences, tokenize


class TokenizeTests(unittest.TestCase):
    def test_drops_stopwords_and_stems(self):
        # Attempt matching relies on "updated" and "update" becoming the same token.
        self.assertEqual(tokenize("I updated the app"), ["updat"])
        self.assertEqual(tokenize("Update to the latest version"), ["updat", "latest", "version"])

    def test_synonyms_map_to_one_token(self):
        # "logged out" must match a step titled "Sign out and back in".
        self.assertEqual(tokenize("I logged out"), tokenize("I signed out"))
        self.assertEqual(tokenize("logged out"), ["sign"])

    def test_contractions_do_not_leave_fragments(self):
        self.assertEqual(tokenize("I can't and didn't, it's broken"), ["broken"])

    def test_keeps_numbers_and_units(self):
        self.assertEqual(tokenize("a 180 MB video"), ["180", "mb", "video"])


class SentenceTests(unittest.TestCase):
    def test_splits_on_terminal_punctuation_and_newlines(self):
        text = "First one. Second one? Third!\nFourth"
        self.assertEqual(sentences(text), ["First one.", "Second one?", "Third!", "Fourth"])


class LogPhraseTests(unittest.TestCase):
    """Review finding: the synonym log -> sign turned "sync log" into "sign"."""

    def test_log_in_and_out_mean_sign(self):
        self.assertEqual(tokenize("I logged in"), ["sign"])
        self.assertEqual(tokenize("log out and back in"), ["sign"])

    def test_a_log_file_is_not_signing_in(self):
        self.assertNotIn("sign", tokenize("I attached the sync log"))


if __name__ == "__main__":
    unittest.main()
