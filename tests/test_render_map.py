import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import render_map as rm


class TestExtractMermaid(unittest.TestCase):
    def test_extracts_single_block(self):
        text = "글\n```mermaid\ngraph TD\n A-->B\n```\n끝\n"
        blocks = rm.extract_mermaid(text)
        self.assertEqual(len(blocks), 1)
        self.assertIn("graph TD", blocks[0])

    def test_extracts_multiple_blocks(self):
        text = "```mermaid\nA\n```\n```mermaid\nB\n```\n"
        self.assertEqual(len(rm.extract_mermaid(text)), 2)

    def test_no_block_returns_empty(self):
        self.assertEqual(rm.extract_mermaid("그냥 글"), [])


class TestBuildHtml(unittest.TestCase):
    def test_html_contains_mermaid_div_and_cdn(self):
        html = rm.build_html(["graph TD\n A-->B"])
        self.assertIn('class="mermaid"', html)
        self.assertIn("graph TD", html)
        self.assertIn("mermaid", html.lower())
        self.assertIn("<!doctype html>", html.lower())

    def test_empty_blocks_still_valid_html(self):
        html = rm.build_html([])
        self.assertIn("<!doctype html>", html.lower())


if __name__ == "__main__":
    unittest.main()
