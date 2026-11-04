import unittest

from triage.text import sentences, tokenize


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


if __name__ == "__main__":
    unittest.main()
